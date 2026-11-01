"""
Comparador de escenarios de Retiro Programado.

Sirve para que el actuario vea, sobre una base real de polizas, que pasa con
la proyeccion de la mesada de Retiro Programado bajo distintas
configuraciones -- y decida cual adoptar. Las 2 palancas que se comparan
son las que quedaron abiertas como decision de negocio:

1. CASTIGO por riesgo de mercado (`castigo_riesgo_mercado_cai`): reduce
   sistematicamente la rentabilidad esperada de la CAI, de modo que el
   fondo crezca mas despacio y la mesada de Retiro Programado quede por
   debajo de la de Renta Vitalicia de forma ORGANICA (por la economia del
   fondo, no por una regla impuesta).

2. CONDICION COMERCIAL (`aplicar_condicion_rv_mayor`): topa explicitamente
   la mesada de RP contra la de RV a partir de un año dado. Es una regla
   de negocio impuesta, no un resultado economico.

Para cada escenario y cada cedula se reporta:
- anios_proyectados: cuantos años dura la proyeccion (horizonte dinamico).
- anio_cruce: año (1-indexado) en que la mesada de RP queda por debajo de
  la de RV; None si nunca ocurre dentro del horizonte.
- motivo_corte: por que termino la proyeccion ("RP<RV", "Control de Saldos"
  o "Tope de años").
- rp_final / rv_final: mesadas del ultimo año proyectado.
"""

from dataclasses import replace
from typing import List, Optional

import pandas as pd

from . import config
from .base_masiva import procesar_base, proyeccion_mesada_por_anio
from .retiro_programado import resolver_y_proyectar_rp_para_fila


def _analizar_cedula(fila, mesada_rv, params) -> dict:
    """Corre la proyeccion de una cedula y resume lo que paso."""
    # detener_al_cruzar_rv=True: el comparador mide justamente EN QUE AÑO
    # la mesada de RP cruza por debajo de la de RV, asi que necesita el
    # corte dinamico. En el resto de la app el horizonte ya es fijo (20
    # años, ver config.MAX_ANIOS_PROYECCION_RP_TOPE).
    proy_rp, _ = resolver_y_proyectar_rp_para_fila(
        fila, params, mesada_rv_encontrada=mesada_rv, detener_al_cruzar_rv=True
    )
    n = len(proy_rp)
    if n == 0:
        return {
            "anios_proyectados": 0, "anio_cruce": None,
            "motivo_corte": "sin proyeccion", "rp_final": None, "rv_final": None,
            "rp_menor_rv_al_final": None,
        }

    proy_rv = proyeccion_mesada_por_anio(
        fila, mesada_rv, params, max_anios=max(n, 1)
    )
    rp = proy_rp["Mesada_Pensional_proyectada"].tolist()
    rv = proy_rv["Mesada_Pensional_proyectada"].tolist()[:n]

    anio_cruce = None
    for j in range(n):
        if j < len(rv) and rp[j] < rv[j]:
            anio_cruce = j + 1
            break

    convergio_final = bool(proy_rp["Convergio"].iloc[-1])
    saldo_final = float(proy_rp["Saldo_CAI_inicio_anio"].iloc[-1])
    total_pagado_ultimo = rp[-1] * int(getattr(fila, "no_mesada", 13) or 13)

    if not convergio_final:
        # El calculo actuarial dejo de encontrar una mesada >= SMLV: la CAI
        # ya no puede garantizar el minimo legal.
        motivo = "Control de Saldos"
    elif anio_cruce is not None and anio_cruce == n:
        # La proyeccion se corto justo el año en que RP quedo bajo RV.
        motivo = "RP<RV"
    elif n >= params.max_anios_proyeccion_rp_tope:
        motivo = "Tope de años"
    elif saldo_final - total_pagado_ultimo <= 0:
        # El saldo se agoto materialmente tras pagar el ultimo año.
        motivo = "CAI agotada"
    else:
        motivo = "CAI agotada"

    return {
        "anios_proyectados": n,
        "anio_cruce": anio_cruce,
        "motivo_corte": motivo,
        "rp_final": rp[-1],
        "rv_final": rv[-1] if rv else None,
        "rp_menor_rv_al_final": (rp[-1] < rv[-1]) if rv else None,
    }


def comparar_escenarios(
    base: pd.DataFrame,
    params_base: "config.ParametrosActuariales",
    escenarios: List[dict],
) -> "tuple":
    """
    Corre la base completa bajo cada escenario y devuelve (detalle, resumen).

    `escenarios` es una lista de dicts con las llaves:
      - "nombre": etiqueta a mostrar
      - "castigo": castigo por riesgo de mercado (decimal, ej 0.03)
      - "condicion": bool, si se activa la condicion comercial RV>RP
      - "anio_condicion": int, desde que año aplica la condicion

    `detalle` tiene una fila por (escenario, cedula).
    `resumen` agrega por escenario: cuantas cedulas cruzan, año promedio de
    cruce, y en cuantas la proyeccion termino en Control de Saldos.
    """
    filas_detalle = []

    for esc in escenarios:
        params = replace(
            params_base,
            castigo_riesgo_mercado_cai=esc["castigo"],
            aplicar_condicion_rv_mayor=esc["condicion"],
            anio_inicio_condicion_rv=esc.get("anio_condicion", 3),
        )
        # La mesada de RV NO depende del castigo ni de la condicion (son
        # parametros exclusivos de RP), pero se recalcula por escenario
        # para que cada uno sea autocontenido y auditable.
        resultados_rv = procesar_base(base, params)

        for i in range(len(base)):
            fila = base.iloc[i]
            mesada_rv = float(resultados_rv.iloc[i]["mesada_encontrada"] or 0)
            if mesada_rv <= 0:
                continue
            try:
                analisis = _analizar_cedula(fila, mesada_rv, params)
            except Exception as exc:  # noqa: BLE001
                analisis = {
                    "anios_proyectados": 0, "anio_cruce": None,
                    "motivo_corte": f"error: {exc}", "rp_final": None,
                    "rv_final": None, "rp_menor_rv_al_final": None,
                }
            filas_detalle.append({
                "escenario": esc["nombre"],
                "cedula": str(fila.get("id_0", "") or ""),
                "id_cotizacion": str(fila.get("id_cotizacion", "")),
                "mesada_rv": mesada_rv,
                **analisis,
            })

    detalle = pd.DataFrame(filas_detalle)
    if detalle.empty:
        return detalle, pd.DataFrame()

    resumen = detalle.groupby("escenario", sort=False).apply(
        lambda g: pd.Series({
            "cedulas": len(g),
            "cruzan_RP<RV": int(g["anio_cruce"].notna().sum()),
            "% cruzan": round(g["anio_cruce"].notna().mean() * 100, 1),
            "año cruce (promedio)": round(g["anio_cruce"].dropna().mean(), 1)
                if g["anio_cruce"].notna().any() else None,
            "Control de Saldos": int((g["motivo_corte"] == "Control de Saldos").sum()),
            "CAI agotada": int((g["motivo_corte"] == "CAI agotada").sum()),
            "años proyectados (promedio)": round(g["anios_proyectados"].mean(), 1),
        }),
        include_groups=False,
    ).reset_index()

    return detalle, resumen
