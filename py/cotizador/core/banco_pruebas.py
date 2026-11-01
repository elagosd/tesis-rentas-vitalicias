# -*- coding: utf-8 -*-
"""
Banco de pruebas: aplica TODO el catalogo de metodos iterativos a TODOS los
escenarios actuariales y produce las tablas de resultados de la tesis.

Protocolo de comparacion (identico para todos los metodos, para que la
comparacion sea justa):

  * Intervalo de encaje       [SMLV, 25 SMLV], el mismo que usa el
                              cotizador en produccion.
  * Punto inicial abierto     el punto medio del intervalo.
  * Dos puntos (secante)      los dos extremos del intervalo.
  * Tres puntos (Muller)      extremos y punto medio.
  * Criterio de parada        |f| < eps_f  o  |x_k - x_{k-1}| < eps_x.
  * Costo reportado           numero de EVALUACIONES de f, no de
                              iteraciones (ver ContadorFuncion).

La raiz de referencia de cada escenario se conoce EXACTAMENTE por
construccion (ver `problema_tesis.escenarios_estandar`), de modo que los
errores reportados son errores verdaderos y no diferencias contra otra
aproximacion numerica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from . import config
from .metodos_iterativos import (
    CriterioParada, ORDEN_TEORICO, ResultadoIteracion,
    aitken_steffensen, anderson_bjorck, biseccion, brent, halley, illinois,
    itp, muller, newton_analitico, newton_diferencias, newton_salvaguardado,
    newton_semisuave, pegasus, punto_fijo, regula_falsi, ridders, secante,
    steffensen, steffensen_escalado,
)
from .problema_tesis import Escenario, constructor_objetivo


def ejecutar_catalogo(escenario: Escenario,
                      params: "config.ParametrosActuariales",
                      crit: Optional[CriterioParada] = None,
                      usar_rp: bool = False) -> Dict[str, ResultadoIteracion]:
    """Corre los 19 metodos con un objetivo independiente para cada uno."""
    crit = crit or CriterioParada(epsilon_f=1.0, epsilon_x=1e-8,
                                  max_iteraciones=200, paso_derivada=1.0)
    a = params.smlv
    b = params.smlv * 25.0
    medio = 0.5 * (a + b)

    def relajacion(df):
        d0 = df(medio)
        return -1.0 / d0 if d0 else -1e-3

    catalogo = [
        ("Biseccion", False, lambda f, df: biseccion(f, a, b, crit)),
        ("Regula Falsi", False, lambda f, df: regula_falsi(f, a, b, crit)),
        ("Illinois", False, lambda f, df: illinois(f, a, b, crit)),
        ("Pegasus", False, lambda f, df: pegasus(f, a, b, crit)),
        ("Anderson-Bjorck", False, lambda f, df: anderson_bjorck(f, a, b, crit)),
        ("Ridders", False, lambda f, df: ridders(f, a, b, crit)),
        ("Brent", False, lambda f, df: brent(f, a, b, crit)),
        ("ITP", False, lambda f, df: itp(f, a, b, crit)),
        ("Secante", False, lambda f, df: secante(f, a, b, crit, lo=a, hi=b)),
        ("Newton (dif. finitas)", False, lambda f, df: newton_diferencias(f, medio, crit, lo=a, hi=b)),
        ("Newton (derivada analitica)", True, lambda f, df: newton_analitico(f, df, medio, crit, lo=a, hi=b)),
        ("Steffensen", False, lambda f, df: steffensen(f, medio, crit, lo=a, hi=b)),
        ("Steffensen escalado", False, lambda f, df: steffensen_escalado(f, medio, lambda: df(medio), crit, lo=a, hi=b)),
        ("Muller", False, lambda f, df: muller(f, a, medio, b, crit, lo=a, hi=b)),
        ("Halley", False, lambda f, df: halley(f, medio, crit, lo=a, hi=b)),
        ("Punto fijo relajado", False, lambda f, df: punto_fijo(f, medio, lambda: relajacion(df), crit, lo=a, hi=b)),
        ("Aitken-Steffensen", False, lambda f, df: aitken_steffensen(f, medio, lambda: relajacion(df), crit, lo=a, hi=b)),
        ("Newton semisuave", True, lambda f, df: newton_semisuave(f, df, medio, crit, lo=a, hi=b)),
        ("Newton salvaguardado", True, lambda f, df: newton_salvaguardado(f, df, a, b, crit)),
    ]
    resultados: Dict[str, ResultadoIteracion] = {}
    for nombre, conjunta, resolver in catalogo:
        f, df_der, _ = constructor_objetivo(
            escenario.datos, escenario.capital, params, usar_rp,
            derivada_conjunta=conjunta,
        )
        resultados[nombre] = resolver(f, df_der)
    return resultados


def tabla_resultados(escenarios: List[Escenario],
                     params: "config.ParametrosActuariales",
                     crit: Optional[CriterioParada] = None) -> pd.DataFrame:
    """DataFrame largo con una fila por (escenario, metodo)."""
    filas = []
    for esc in escenarios:
        ref = esc.mesada_teorica
        res = ejecutar_catalogo(esc, params, crit)
        for nombre, r in res.items():
            err_abs = abs(r.raiz - ref) if ref else float("nan")
            filas.append({
                "escenario": esc.codigo,
                "region": esc.region,
                "metodo": nombre,
                "familia": r.familia,
                "convergio": r.convergio,
                "iteraciones": r.iteraciones,
                "evaluaciones": r.evaluaciones_funcion,
                "evaluaciones_valor": r.evaluaciones_valor,
                "evaluaciones_con_derivada": r.evaluaciones_con_derivada,
                "tiempo_ms": r.tiempo_segundos * 1000,
                "raiz": r.raiz,
                "error_abs": err_abs,
                "error_rel": err_abs / abs(ref) if ref else float("nan"),
                "residuo": abs(r.historial[-1].fx) if r.historial else float("nan"),
                "orden_empirico": r.estimar_orden(ref) if ref else None,
                "razon_lineal": r.razon_lineal(ref) if ref else None,
                "razon_intervalo": r.razon_ancho_intervalo(),
                "orden_teorico": ORDEN_TEORICO.get(nombre),
                "indice_eficiencia": r.indice_eficiencia(ref) if ref else None,
                "mensaje": r.mensaje,
                "estado": r.estado,
                "cota_error": r.cota_error,
            })
    return pd.DataFrame(filas)


def resumen_por_metodo(tabla: pd.DataFrame) -> pd.DataFrame:
    """Agregado por metodo sobre todos los escenarios: la tabla maestra."""
    g = tabla.groupby(["metodo", "familia"], as_index=False).agg(
        tasa_exito=("convergio", "mean"),
        iteraciones_medias=("iteraciones", "mean"),
        evaluaciones_medias=("evaluaciones", "mean"),
        evaluaciones_max=("evaluaciones", "max"),
        tiempo_medio_ms=("tiempo_ms", "mean"),
        error_mediano=("error_abs", "median"),
        error_max=("error_abs", "max"),
        orden_empirico=("orden_empirico", "median"),
        indice_eficiencia=("indice_eficiencia", "median"),
    )
    g["orden_teorico"] = g["metodo"].map(ORDEN_TEORICO)
    return g.sort_values(["evaluaciones_medias", "error_mediano"]).reset_index(drop=True)
