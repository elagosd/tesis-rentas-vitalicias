"""
Calcula y guarda en el historial (data/historial.db, tabla
proyecciones_mesada) la proyeccion de mesada por año, para AMBOS productos
(Renta Vitalicia y Retiro Programado), de CADA cedula de una corrida
masiva -- no solo de la cedula que el usuario elige ver en el grafico.

La comparacion con Retiro Programado es OPCIONAL (peticion del usuario
2026-08-21): el usuario la activa o desactiva con una casilla en cada
pagina de corrida masiva, y se propaga hasta aca via el parametro
`incluir_rp`. Desactivada, solo se calcula y guarda Renta Vitalicia, lo
que hace la corrida notoriamente mas rapida.

La mesada de Retiro Programado se topa cada año al techo de la mesada de
Renta Vitalicia de ese mismo año, con un margen que CRECE con el tiempo
(ver core/retiro_programado.py::MARGEN_RP_ANIO1 / MARGEN_RP_FINAL): el año
1 arranca parecido a RV, y la brecha se va abriendo en los años
siguientes -- es un requisito de negocio, no una propiedad que emerja sola
del calculo actuarial (ver VALIDACION.md).

Se corre en paralelo (core/paralelo.py, nucleos del equipo - 1) porque el
calculo de Retiro Programado ahora es dinamico (recalcula la mesada cada
año simulando la Cuenta de Ahorro Individual, ver
core/retiro_programado.py::proyectar_rp_dinamico_cai), lo que implica
correr el motor completo varias veces por cedula en vez de una sola vez.
"""

import uuid
from typing import Callable, Optional

import pandas as pd

from . import config, persistencia
from .base_masiva import _fila_a_datos_poliza, proyeccion_mesada_por_anio
from .paralelo import ejecutar_en_paralelo
from .retiro_programado import (
    TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP,
    primer_anio_bajo_smlv,
    proyectar_rp_dinamico_cai,
)

# Horizonte por defecto si no se pasa uno explicito NI se puede leer de la
# parametrizacion. En la practica siempre se usa
# params.max_anios_proyeccion_rp_tope (20 años); esto es solo un respaldo.
MAX_ANIOS_PROYECCION_DEFECTO = config.MAX_ANIOS_PROYECCION_RP_TOPE


def _calcular_proyecciones_fila(
    fila: pd.Series,
    cedula: str,
    id_cotizacion: str,
    mesada_rv: float,
    params: "config.ParametrosActuariales",
    max_anios: int,
    incluir_rp: bool = True,
    proyeccion_rv_precalculada: "Optional[list]" = None,
) -> dict:
    """
    Funcion a nivel de modulo (picklable) que calcula la proyeccion RV y RP
    de UNA fila, para correr en un proceso worker aparte. Devuelve un dict
    con:
    - "filas_db": lista de tuplas (cedula, id_cotizacion, producto, anio,
      mesada, convergio), lista para guardar en la base de datos.
    - "cedula", "id_cotizacion", "anio_critico_rp": resumen para mostrar en
      la tabla de resultados masivos.

    Si `incluir_rp` es False, se calcula UNICAMENTE la proyeccion de Renta
    Vitalicia y "anio_critico_rp" queda en None. Esto es lo que permite que
    la corrida masiva sea mucho mas rapida cuando no se necesita la
    comparacion: RP recalcula la mesada año a año simulando la CAI, o sea
    que corre el motor actuarial completo una vez por año proyectado, y es
    con diferencia la parte mas costosa de la corrida.
    """
    filas_resultado = []
    mesada_rv_por_anio = None

    if mesada_rv and mesada_rv > 0:
        try:
            if proyeccion_rv_precalculada:
                # Camino normal: la proyeccion de Renta Vitalicia ya salio
                # de la evaluacion que hizo el metodo de iteracion al
                # encontrar la mesada (ver core/base_masiva.py::
                # _resolver_mesada_con_flujos). No se vuelve a correr el
                # motor: se reusa tal cual.
                pares_rv = [(int(a), float(m)) for a, m in proyeccion_rv_precalculada][:max_anios]
            else:
                # Respaldo: sin proyeccion precalculada (por ejemplo si se
                # llama a este modulo por fuera de procesar_base), se
                # calcula como antes.
                proy_rv = proyeccion_mesada_por_anio(fila, mesada_rv, params, max_anios=max_anios)
                pares_rv = [
                    (int(r["Anio"]), float(r["Mesada_Pensional_proyectada"]))
                    for _, r in proy_rv.iterrows()
                ]

            mesada_rv_por_anio = dict(pares_rv)
            for anio, mesada in pares_rv:
                filas_resultado.append(
                    (cedula, id_cotizacion, "renta_vitalicia", anio, mesada, True)
                )
        except Exception:  # noqa: BLE001
            pass

    anio_critico_rp = None
    if not incluir_rp:
        return {
            "filas_db": filas_resultado,
            "cedula": cedula,
            "id_cotizacion": id_cotizacion,
            "anio_critico_rp": None,
        }

    try:
        datos = _fila_a_datos_poliza(fila)
        datos.smlv = params.smlv
        # Factor de ajuste NI: se activa cuando la mesada de RV YA
        # CALCULADA (correctamente, sin cambios) coincide -- dentro de
        # una tolerancia RELATIVA, ver TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP
        # en core/retiro_programado.py -- con la columna "Mesada_Actual_RP"
        # de la base. Ver params.factor_ajuste_ni.
        if (
            mesada_rv and mesada_rv > 0
            and datos.mesada_actual_rp is not None and datos.mesada_actual_rp > 0
            and abs(mesada_rv - datos.mesada_actual_rp) / datos.mesada_actual_rp
            < TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP
        ):
            datos.aplicar_factor_ajuste_ni = True
        capital_objetivo = float(fila["capital_renta"])
        proy_rp = proyectar_rp_dinamico_cai(
            datos, capital_objetivo, params, max_anios=max_anios, mesada_rv_por_anio=mesada_rv_por_anio
        )
        anio_critico_rp = primer_anio_bajo_smlv(proy_rp)
        for _, r in proy_rp.iterrows():
            filas_resultado.append(
                (cedula, id_cotizacion, "retiro_programado", int(r["Anio"]), float(r["Mesada_Pensional_proyectada"]), bool(r["Convergio"]))
            )
    except Exception:  # noqa: BLE001
        pass

    return {
        "filas_db": filas_resultado,
        "cedula": cedula,
        "id_cotizacion": id_cotizacion,
        "anio_critico_rp": anio_critico_rp,
    }


def calcular_y_guardar_proyecciones_masivo(
    pagina: str,
    base: pd.DataFrame,
    resultados: pd.DataFrame,
    params: "config.ParametrosActuariales",
    max_anios: Optional[int] = None,
    callback_progreso: Optional[Callable[[int, int], None]] = None,
    incluir_rp: bool = True,
    proyecciones_rv: Optional[dict] = None,
) -> "tuple":
    """
    Calcula (en paralelo) y guarda en el historial la proyeccion de mesada
    por año de Renta Vitalicia y Retiro Programado, para CADA cedula de
    `base` (no solo la que se ve en el grafico).

    `max_anios`: horizonte en años. Si no se pasa, se usan los
    `params.max_anios_proyeccion_rp_tope` (20 por defecto) -- los mismos
    años que se grafican, para que lo guardado en el historial y lo que ve
    el usuario en pantalla coincidan.

    `proyecciones_rv`: dict {indice_de_fila: [(año, mesada), ...]} con la
    proyeccion de Renta Vitalicia ya calculada por procesar_base durante la
    iteracion. Si se pasa, NO se vuelve a correr el motor para Renta
    Vitalicia (que era una duplicacion exacta del calculo ya hecho al
    encontrar la mesada). Si no se pasa, se calcula como antes.

    `incluir_rp`: si es False, se calcula y guarda SOLO la proyeccion de
    Renta Vitalicia (el usuario no pidio la comparacion con Retiro
    Programado) y la columna anio_critico_rp del resumen queda vacia.

    Devuelve (corrida_id, df_resumen), donde df_resumen tiene columnas
    cedula, id_cotizacion, anio_critico_rp (año en que el saldo de la CAI
    ya no alcanza para sostener el SMLV, o None si nunca pasa en el
    horizonte proyectado) -- para poder agregarlo a la tabla de resultados
    masivos.
    """
    corrida_id = uuid.uuid4().hex[:12]
    if max_anios is None:
        max_anios = params.max_anios_proyeccion_rp_tope

    # Atajo: si no se pide Retiro Programado Y la proyeccion de Renta
    # Vitalicia ya viene calculada desde la iteracion, aqui NO queda nada
    # que calcular -- solo hay que darle formato de filas y guardarlas. En
    # ese caso se hace en linea, sin levantar el pool de procesos: crear
    # procesos y serializarles la base para que no corran ni una sola vez
    # el motor actuarial es puro sobrecosto, y ademas hacia aparecer una
    # barra de progreso que sugeria un recalculo que ya no ocurre.
    if not incluir_rp and proyecciones_rv:
        todas_las_filas = []
        for i in range(len(base)):
            fila_resultado = resultados.iloc[i]
            cedula = str(fila_resultado.get("cedula", ""))
            id_cotizacion = str(fila_resultado.get("id_cotizacion", ""))
            mesada_rv = float(fila_resultado.get("mesada_encontrada", 0) or 0)
            if mesada_rv <= 0:
                continue
            for anio, mesada in (proyecciones_rv.get(i) or [])[:max_anios]:
                todas_las_filas.append(
                    (cedula, id_cotizacion, "renta_vitalicia", int(anio), float(mesada), True)
                )
            if callback_progreso is not None:
                callback_progreso(i + 1, len(base))
        persistencia.registrar_proyecciones_mesada(pagina, corrida_id, todas_las_filas)
        df_resumen = pd.DataFrame([
            {
                "cedula": str(resultados.iloc[i].get("cedula", "")),
                "id_cotizacion": str(resultados.iloc[i].get("id_cotizacion", "")),
                "anio_critico_rp": None,
            }
            for i in range(len(base))
        ])
        return corrida_id, df_resumen

    argumentos = []
    for i in range(len(base)):
        fila = base.iloc[i]
        fila_resultado = resultados.iloc[i]
        cedula = str(fila_resultado.get("cedula", ""))
        id_cotizacion = str(fila_resultado.get("id_cotizacion", ""))
        mesada_rv = float(fila_resultado.get("mesada_encontrada", 0) or 0)
        proy_rv = proyecciones_rv.get(i) if proyecciones_rv else None
        argumentos.append(
            (fila, cedula, id_cotizacion, mesada_rv, params, max_anios, incluir_rp, proy_rv)
        )

    resultados_por_fila = ejecutar_en_paralelo(_calcular_proyecciones_fila, argumentos, callback_progreso)

    todas_las_filas = [fila for r in resultados_por_fila for fila in r["filas_db"]]
    persistencia.registrar_proyecciones_mesada(pagina, corrida_id, todas_las_filas)

    df_resumen = pd.DataFrame([
        {"cedula": r["cedula"], "id_cotizacion": r["id_cotizacion"], "anio_critico_rp": r["anio_critico_rp"]}
        for r in resultados_por_fila
    ])

    return corrida_id, df_resumen
