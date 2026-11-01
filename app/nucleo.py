# -*- coding: utf-8 -*-
"""
Capa de acceso al motor actuarial para la aplicación de la defensa.

Aísla a la presentación de los detalles del motor y concentra aquí todo el
cacheo, que es lo que hace que la aplicación sea usable: cada llamada al motor
cuesta unos milisegundos (depende del equipo), de modo que trazar una curva de
300 puntos lleva uno o varios segundos. Con el cacheo de Streamlit esa espera se
paga una sola vez por combinación de parámetros.

Las cifras consolidadas que la presentación cita del documento (tablas del banco
de pruebas y macros numéricas) se leen de tex/, la copia del proyecto de
Overleaf: así la presentación no puede citar una cifra distinta de la tesis.
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# El paquete `core` vive en py/cotizador dentro del repositorio de la tesis.
_RAIZ = Path(__file__).resolve().parent.parent
for _cand in (_RAIZ / "py" / "cotizador", _RAIZ / "cotizador"):
    if _cand.exists() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

from core import config                                    # noqa: E402
from core.motor import DatosPoliza, Persona, calcular_reserva  # noqa: E402
from core.metodos_iterativos import (                        # noqa: E402
    CriterioParada, ORDEN_TEORICO, aitken_steffensen, anderson_bjorck, biseccion,
    brent, halley, illinois, itp, muller, newton_analitico, newton_diferencias,
    newton_salvaguardado, newton_semisuave, pegasus, punto_fijo, regula_falsi,
    ridders, secante, steffensen, steffensen_escalado,
)
from core.problema_tesis import ObjetivoActuarial              # noqa: E402

RUTA_SALIDAS = _RAIZ / "salidas"
RUTA_FIGURAS = _RAIZ / "tex" / "figuras"
RUTA_TEX = _RAIZ / "tex"
# Base de polizas: la real si esta disponible localmente en datos_privados/
# (no se publica); en caso contrario, la base ficticia de ejemplo.
_BASE_PRIVADA = _RAIZ / "datos_privados" / "base_cotizacion_prueba_7_casos.xlsx"
RUTA_BASE_REAL = (_BASE_PRIVADA if _BASE_PRIVADA.exists()
                  else _RAIZ / "py" / "cotizador" / "ejemplos" / "base_cotizacion_ejemplo.xlsx")

# Semilla explícita del escenario de mercado de retiro programado. Sin ella el
# motor deriva una semilla estable de un resumen SHA-256 de las entradas; aquí
# se fija una para que todas las pólizas y las perturbaciones del experimento
# de propagación compartan la misma realización de mercado, como exige el
# teorema de propagación (mismos rendimientos en las trayectorias comparadas).
SEMILLA_RP = 20260822


# =====================================================================
# Paleta y estilo
# =====================================================================

AZUL = "#0072B2"
NARANJA = "#E69F00"
VERDE = "#009E73"
ROJO = "#D55E00"
MORADO = "#CC79A7"
CELESTE = "#56B4E9"
GRIS = "#5A5A5A"
GRIS_CLARO = "#D8D8D8"
PALETA = [AZUL, NARANJA, VERDE, ROJO, MORADO, CELESTE, GRIS]

COLOR_FAMILIA = {"encaje": AZUL, "abierto": NARANJA, "no suave": VERDE}


def plantilla_plotly():
    """Plantilla de Plotly consistente con las figuras del documento."""
    return dict(
        template="plotly_white",
        font=dict(family="Georgia, 'Times New Roman', serif", size=13, color="#222"),
        margin=dict(l=60, r=30, t=50, b=50),
        hoverlabel=dict(font_size=12),
        legend=dict(bgcolor="rgba(255,255,255,.7)", bordercolor="#DDD", borderwidth=1),
    )


# =====================================================================
# Construcción de parámetros y pólizas
# =====================================================================


def parametros(**cambios) -> "config.ParametrosActuariales":
    p = config.ParametrosActuariales()
    return replace(p, **cambios) if cambios else p


def poliza(fecha_nac_causante=date(1961, 5, 10), sexo_causante=1, estado_causante=1,
           con_conyuge=True, fecha_nac_conyuge=date(1965, 3, 2), sexo_conyuge=2,
           con_hijo=False, n_mesadas=13, tasa=0.0420, smlv=None) -> DatosPoliza:
    p = parametros()
    benef = []
    if con_conyuge:
        benef.append(Persona(fecha_nac_conyuge, config.COD_CONYUGE, sexo_conyuge, 1))
    if con_hijo:
        benef.append(Persona(date(2012, 4, 12), config.COD_HIJO, 1, 1))
    return DatosPoliza(
        id_pol="APP", n_mesadas=n_mesadas, fecha_valoracion=date(2026, 7, 31),
        smlv=smlv if smlv is not None else p.smlv,
        mesada_actual=p.smlv, tasa_interes_real=tasa,
        causante=Persona(fecha_nac_causante, config.COD_CAUSANTE, sexo_causante, estado_causante),
        beneficiarios=benef,
    )


# =====================================================================
# Evaluación cacheada
# =====================================================================


def _clave(datos: DatosPoliza, p) -> tuple:
    """Clave hashable que identifica una combinación póliza-parámetros."""
    return (
        datos.n_mesadas, datos.fecha_valoracion, datos.smlv, datos.tasa_interes_real,
        datos.causante.fecha_nacimiento, datos.causante.sexo, datos.causante.estado,
        tuple((b.fecha_nacimiento, b.tipo_beneficiario, b.sexo, b.estado)
              for b in datos.beneficiarios),
        p.ipc_primer_anio, p.ipc_segundo_anio, p.ipc_objetivo_largo_plazo,
        p.delta_deslizamiento, p.smlv, p.porcentaje_recargo_gastos_reserva,
        p.porcentaje_reserva_cambio_grupo,
    )


@st.cache_data(show_spinner=False, max_entries=64)
def curva_vp(_datos: DatosPoliza, _p, clave: tuple, m_min: float, m_max: float,
             n: int = 260) -> pd.DataFrame:
    """Malla de (M, VP(M), VP'_+(M), VP'_-(M)). `clave` fuerza la invalidación."""
    xs = np.linspace(m_min, m_max, n)
    filas = []
    for x in xs:
        r = calcular_reserva(replace(_datos, mesada_actual=float(x)), _p, calcular_derivada=True)
        filas.append((x, r.reserva_matematica, r.derivada_rm_der, r.derivada_rm_izq))
    return pd.DataFrame(filas, columns=["M", "VP", "dVP_der", "dVP_izq"])


@st.cache_data(show_spinner=False, max_entries=256)
def vp_en(_datos: DatosPoliza, _p, clave: tuple, m: float) -> float:
    return float(calcular_reserva(replace(_datos, mesada_actual=float(m)), _p).reserva_matematica)


def objetivo(datos: DatosPoliza, p, capital: float):
    """Devuelve (f, df_der) sobre el objetivo instrumentado del banco de pruebas.

    `f` es un ObjetivoActuarial: cuenta las llamadas efectivas al motor (valor y
    derivadas) y reinicia su memoria en cada ejecución de un método, como en el
    protocolo del capítulo de resultados."""
    f = ObjetivoActuarial(datos, capital, p)
    return f, f.df_der


# =====================================================================
# Ejecución de los métodos
# =====================================================================

METODOS_DISPONIBLES = [
    "Bisección", "Regula falsi", "Illinois", "Pegasus", "Anderson-Björck",
    "Ridders", "Brent", "ITP", "Secante", "Newton (dif. finitas)",
    "Newton (analítico)", "Steffensen", "Steffensen escalado", "Müller",
    "Halley", "Punto fijo relajado", "Aitken-Steffensen", "Newton semisuave",
    "Newton salvaguardado",
]

FAMILIA = {
    "Bisección": "encaje", "Regula falsi": "encaje", "Illinois": "encaje",
    "Pegasus": "encaje", "Anderson-Björck": "encaje", "Ridders": "encaje",
    "Brent": "encaje", "ITP": "encaje", "Secante": "abierto",
    "Newton (dif. finitas)": "abierto", "Newton (analítico)": "abierto",
    "Steffensen": "abierto", "Steffensen escalado": "abierto", "Müller": "abierto",
    "Halley": "abierto", "Punto fijo relajado": "abierto",
    "Aitken-Steffensen": "abierto", "Newton semisuave": "no suave",
    "Newton salvaguardado": "no suave",
}

ORDEN_NOMINAL = {
    "Bisección": 1.0, "Regula falsi": 1.0, "Illinois": 1.442, "Pegasus": 1.642,
    "Anderson-Björck": 1.71, "Ridders": 1.414, "Brent": 1.839, "ITP": 1.618,
    "Secante": 1.618, "Newton (dif. finitas)": 2.0, "Newton (analítico)": 2.0,
    "Steffensen": 2.0, "Steffensen escalado": 2.0, "Müller": 1.839, "Halley": 3.0,
    "Punto fijo relajado": 1.0, "Aitken-Steffensen": 2.0,
    "Newton semisuave": 2.0, "Newton salvaguardado": 2.0,
}


# Métodos que, como en el banco de pruebas, calculan conjuntamente valor y
# derivada en cada punto: una sola llamada al motor por iterado.
CON_DERIVADA_CONJUNTA = {"Newton (analítico)", "Newton semisuave", "Newton salvaguardado"}


def ejecutar(nombre: str, f, df, a: float, b: float, x0: float, crit: CriterioParada):
    """Corre un método por su nombre en la interfaz, con el mismo protocolo del
    banco de pruebas: memoria propia por ejecución, preparación incluida en el
    costo y evaluación conjunta de valor y derivada en los métodos analíticos."""
    medio = x0
    if isinstance(f, ObjetivoActuarial):
        f.derivada_conjunta = nombre in CON_DERIVADA_CONJUNTA

    def relajacion():
        d0 = df(medio)
        return -1.0 / d0 if d0 else -1e-3
    if nombre == "Bisección":
        return biseccion(f, a, b, crit)
    if nombre == "Regula falsi":
        return regula_falsi(f, a, b, crit)
    if nombre == "Illinois":
        return illinois(f, a, b, crit)
    if nombre == "Pegasus":
        return pegasus(f, a, b, crit)
    if nombre == "Anderson-Björck":
        return anderson_bjorck(f, a, b, crit)
    if nombre == "Ridders":
        return ridders(f, a, b, crit)
    if nombre == "Brent":
        return brent(f, a, b, crit)
    if nombre == "ITP":
        return itp(f, a, b, crit)
    if nombre == "Secante":
        return secante(f, a, b, crit, lo=a, hi=b)
    if nombre == "Newton (dif. finitas)":
        return newton_diferencias(f, medio, crit, lo=a, hi=b)
    if nombre == "Newton (analítico)":
        return newton_analitico(f, df, medio, crit, lo=a, hi=b)
    if nombre == "Steffensen":
        return steffensen(f, medio, crit, lo=a, hi=b)
    if nombre == "Steffensen escalado":
        return steffensen_escalado(f, medio, lambda: df(medio), crit, lo=a, hi=b)
    if nombre == "Müller":
        return muller(f, a, medio, b, crit, lo=a, hi=b)
    if nombre == "Halley":
        return halley(f, medio, crit, lo=a, hi=b)
    if nombre == "Punto fijo relajado":
        return punto_fijo(f, medio, relajacion, crit, lo=a, hi=b)
    if nombre == "Aitken-Steffensen":
        return aitken_steffensen(f, medio, relajacion, crit, lo=a, hi=b)
    if nombre == "Newton semisuave":
        return newton_semisuave(f, df, medio, crit, lo=a, hi=b)
    if nombre == "Newton salvaguardado":
        return newton_salvaguardado(f, df, a, b, crit)
    raise ValueError(f"Método desconocido: {nombre}")


# =====================================================================
# Utilidades de formato
# =====================================================================


def _es_co(texto: str) -> str:
    """Convierte «1,234.5» (formato de Python) en «1.234,5» (formato colombiano)."""
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def pesos(x, dec=0):
    return "$ " + _es_co(f"{x:,.{dec}f}")


def millones(x):
    if abs(x) >= 1e9:
        return _es_co(f"{x/1e9:,.2f}") + " MM"
    if abs(x) >= 1e6:
        return _es_co(f"{x/1e6:,.1f}") + " M"
    return _es_co(f"{x:,.0f}")


def tabla_resultados_guardada() -> pd.DataFrame | None:
    ruta = RUTA_SALIDAS / "resumen_global.csv"
    return pd.read_csv(ruta) if ruta.exists() else None


def tabla_larga_guardada() -> pd.DataFrame | None:
    ruta = RUTA_SALIDAS / "tabla_larga.csv"
    return pd.read_csv(ruta) if ruta.exists() else None


# =====================================================================
# Cálculos de las secciones añadidas (todos en vivo sobre el motor)
# =====================================================================


@st.cache_data(show_spinner=False, max_entries=8)
def supervivencia(con_hijo: bool = True) -> pd.DataFrame:
    """Probabilidades de supervivencia mensuales de cada integrante y la
    conjunta CONAB(t) = 1 - prod(1 - tpy), con las tablas RV-08 reales."""
    from core.motor import _tabla_persona

    d = poliza(con_hijo=con_hijo)
    fv = pd.Timestamp(d.fecha_valoracion) + pd.offsets.MonthEnd(0)
    tab_c, _ = _tabla_persona(d.causante, fv, es_causante=True)
    salida = {"t": np.arange(len(tab_c)) / 12.0, "causante": tab_c["nPx"].to_numpy()}
    nombres = {config.COD_CONYUGE: "cónyuge", config.COD_HIJO: "hijo"}
    for b in d.beneficiarios:
        tab_b, _ = _tabla_persona(b, fv, es_causante=False)
        salida[nombres.get(b.tipo_beneficiario, "beneficiario")] = tab_b["nPx"].to_numpy()
    df = pd.DataFrame(salida)
    vidas = [c for c in df.columns if c != "t"]
    df["CONAB"] = 1.0 - np.prod([1.0 - df[c].to_numpy() for c in vidas], axis=0)
    return df


def edad_en(fecha_nac: date, fecha_val: date = date(2026, 7, 31)) -> int:
    return fecha_val.year - fecha_nac.year - ((fecha_val.month, fecha_val.day) <
                                              (fecha_nac.month, fecha_nac.day))


@st.cache_data(show_spinner=False, max_entries=256)
def valor_y_derivadas(_datos: DatosPoliza, _p, clave: tuple, m: float) -> dict:
    """VP(M), las dos derivadas laterales exactas y los términos activos."""
    r = calcular_reserva(replace(_datos, mesada_actual=float(m)), _p, calcular_derivada=True)
    return {"VP": float(r.reserva_matematica), "izq": float(r.derivada_rm_izq),
            "der": float(r.derivada_rm_der), "renta": int(r.terminos_activos_renta),
            "auf": int(r.terminos_activos_auf)}


@st.cache_data(show_spinner=False, max_entries=64)
def diferencias_centrales(_datos: DatosPoliza, _p, clave: tuple, m: float,
                          pasos: tuple) -> list:
    """Aproximación (VP(M+h) - VP(M-h)) / 2h para cada paso h."""
    def vp(x):
        return calcular_reserva(replace(_datos, mesada_actual=float(x)), _p).reserva_matematica
    return [(vp(m + h) - vp(m - h)) / (2 * h) for h in pasos]


@st.cache_data(show_spinner=False, max_entries=4)
def efecto_demografico() -> pd.DataFrame:
    """Efecto de cada hipótesis demográfica y contractual sobre la reserva
    (misma construcción que py/fig_05_variables.py, recalculada en vivo)."""
    p = parametros()
    S0 = p.smlv
    caus = Persona(date(1961, 5, 10), config.COD_CAUSANTE, 1, 1)
    cony = Persona(date(1965, 3, 2), config.COD_CONYUGE, 2, 1)
    D = DatosPoliza("V", 13, date(2026, 7, 31), S0, 3 * S0, 0.042, caus, [cony])

    def rm(d):
        return calcular_reserva(d, p).reserva_matematica

    base = rm(D)
    casos = [
        ("Sin factores de mejora de longevidad", rm(replace(D, sin_factores_mejora=True))),
        ("Sin cónyuge beneficiaria", rm(replace(D, beneficiarios=[]))),
        ("Con un hijo menor adicional",
         rm(replace(D, beneficiarios=[cony, Persona(date(2012, 1, 1), config.COD_HIJO, 1, 1)]))),
        ("Régimen de 14 mesadas", rm(replace(D, n_mesadas=14))),
        ("Causante inválido (tabla RI-08)",
         rm(replace(D, causante=Persona(date(1961, 5, 10), config.COD_CAUSANTE, 1, 2)))),
        ("Causante mujer (tabla RV-08 F)",
         rm(replace(D, causante=Persona(date(1961, 5, 10), config.COD_CAUSANTE, 2, 1),
                    beneficiarios=[Persona(date(1965, 3, 2), config.COD_CONYUGE, 1, 1)]))),
    ]
    df = pd.DataFrame([(h, (v - base) / base * 100) for h, v in casos],
                      columns=["hipotesis", "efecto_pct"])
    return df.sort_values("efecto_pct").reset_index(drop=True)


@st.cache_resource(show_spinner=False)
def base_real() -> pd.DataFrame | None:
    """Base de las siete cotizaciones reales. Contiene datos personales: la
    aplicación solo usa de ella fechas, sexo, estado, capital y mesada, y
    nunca muestra nombres ni números de identificación."""
    if not RUTA_BASE_REAL.exists():
        return None
    return pd.read_excel(RUTA_BASE_REAL)


@st.cache_data(show_spinner=False, max_entries=2)
def validacion_real() -> pd.DataFrame | None:
    """Mesada del modelo frente a la reportada por la compañía, póliza a
    póliza. La raíz se obtiene con Brent a tolerancia cercana a la de
    máquina, como en el capítulo 6. Las pólizas se rotulan P1…P7."""
    from core.base_masiva import _fila_a_datos_poliza
    from core.metodos_iterativos import brent

    base = base_real()
    if base is None:
        return None
    p = parametros()
    filas = []
    for i, (_, fila) in enumerate(base.iterrows(), start=1):
        datos = _fila_a_datos_poliza(fila)
        datos.smlv = p.smlv
        capital = float(fila["capital_renta"])

        def f(m, datos=datos, capital=capital):
            return calcular_reserva(replace(datos, mesada_actual=float(m)), p).reserva_matematica - capital

        r = brent(f, p.smlv, 25 * p.smlv, CriterioParada(1e-6, 1e-10, 400))
        aseg = float(fila["Mesada_RV"])
        filas.append({"poliza": f"P{i}", "modelo": float(r.raiz), "aseguradora": aseg,
                      "dif_pct": (float(r.raiz) - aseg) / aseg * 100,
                      "mesada_smlv": float(r.raiz) / p.smlv, "capital": capital})
    return pd.DataFrame(filas)


def _proyectar_rp(indice: int, semilla: int, capital_extra: float = 0.0,
                  max_anios: int = 20):
    """Réplica de core.retiro_programado.resolver_y_proyectar_rp_para_fila con
    semilla explícita (la del motor no es estable entre arranques)."""
    from core.base_masiva import _fila_a_datos_poliza, proyeccion_mesada_por_anio
    from core.retiro_programado import (TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP,
                                        proyectar_rp_dinamico_cai)

    p = parametros()
    fila = base_real().iloc[indice]
    mesada_rv = float(validacion_real().iloc[indice]["modelo"])
    datos = _fila_a_datos_poliza(fila)
    datos.smlv = p.smlv
    if (datos.mesada_actual_rp is not None and datos.mesada_actual_rp > 0
            and abs(mesada_rv - datos.mesada_actual_rp) / datos.mesada_actual_rp
            < TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP):
        datos.aplicar_factor_ajuste_ni = True
    proy_rv = proyeccion_mesada_por_anio(fila, mesada_rv, p, max_anios=max_anios)
    mesada_rv_por_anio = {int(r["Anio"]): float(r["Mesada_Pensional_proyectada"])
                          for _, r in proy_rv.iterrows()}
    proy_rp = proyectar_rp_dinamico_cai(datos, float(fila["capital_renta"]) + capital_extra, p,
                                        max_anios=max_anios, mesada_rv_por_anio=mesada_rv_por_anio,
                                        semilla_aleatoria=semilla)
    return proy_rv, proy_rp, bool(datos.aplicar_factor_ajuste_ni)


@st.cache_data(show_spinner=False, max_entries=32)
def trayectorias_rv_rp(indice: int, semilla: int):
    return _proyectar_rp(indice, semilla)


@st.cache_data(show_spinner=False, max_entries=16)
def propagacion_rp(indice: int, semilla: int,
                   perturbaciones: tuple = (0.0, 1.0, 1e2, 1e4, 1e6)) -> dict:
    """Trayectorias de RP con el capital inicial perturbado en δ pesos, con
    el MISMO escenario de mercado, para medir cómo se propaga el error."""
    return {d: _proyectar_rp(indice, semilla, capital_extra=d, max_anios=15)[1]
            for d in perturbaciones}


@st.cache_data(show_spinner=False, max_entries=16)
def pendiente_normalizada(campo: str, valor: float, m_min: float, m_max: float,
                          n: int = 240) -> pd.DataFrame:
    """VP'_+(M) / VP'_+(3 SMLV) bajo una hipótesis alterada. Sirve para ver
    qué variables mueven los quiebres y cuáles solo cambian el nivel."""
    p = parametros() if campo in ("", "tasa") else parametros(**{campo: valor})
    d = poliza(tasa=valor) if campo == "tasa" else poliza()
    xs = np.linspace(m_min, m_max, n)
    der = np.array([calcular_reserva(replace(d, mesada_actual=float(x)), p,
                                     calcular_derivada=True).derivada_rm_der for x in xs])
    ref = calcular_reserva(replace(d, mesada_actual=3 * p.smlv), p,
                           calcular_derivada=True).derivada_rm_der
    return pd.DataFrame({"M": xs, "pendiente_rel": der / ref})


@st.cache_data(show_spinner=False, max_entries=32)
def produccion_con_capital(fraccion: float) -> dict:
    """Corre los algoritmos de PRODUCCIÓN (core/metodos_numericos.py: secante
    y bisección, con los parámetros por defecto del cotizador) sobre la póliza
    de referencia con un capital igual a `fraccion` · KA_min, y los compara con
    la prueba a priori de una sola evaluación (recomendación R1)."""
    from core import metodos_numericos as MN

    p = parametros()
    d = poliza()
    S0 = p.smlv
    ka_min = float(calcular_reserva(replace(d, mesada_actual=S0), p).reserva_matematica)
    capital = fraccion * ka_min

    class _Crit:
        epsilon = p.epsilon
        max_iteraciones = p.max_iteraciones
        paso_derivada = p.paso_derivada

    def correr(nombre):
        cont = [0]

        def f(m):           # convención de producción: KA - VP, decreciente
            cont[0] += 1
            return capital - calcular_reserva(replace(d, mesada_actual=float(m)), p).reserva_matematica
        if nombre == "secante":
            r = MN.secante(f, S0, 25 * S0, _Crit(), limite_inferior=S0, limite_superior=25 * S0)
        else:
            r = MN.biseccion(f, S0, 25 * S0, _Crit())
        return {"convergio": bool(r.convergio), "evaluaciones": cont[0],
                "mesada_smlv": float(r.valor) / S0, "mensaje": r.mensaje}

    return {"ka_min": ka_min, "capital": capital,
            "secante": correr("secante"), "biseccion": correr("biseccion")}


@st.cache_data(show_spinner=False, max_entries=4)
def barrido_newton_semisuave(objetivo_smlv: float, n: int = 70) -> pd.DataFrame:
    """Iteraciones de Newton semisuave desde n puntos iniciales (sección de
    terminación finita). Se cachea porque son n corridas completas."""
    p = parametros()
    d = poliza()
    S0 = p.smlv
    capital = float(calcular_reserva(replace(d, mesada_actual=objetivo_smlv * S0), p).reserva_matematica)
    f, df_ = objetivo(d, p, capital)
    crit = CriterioParada(epsilon_f=1e-6, epsilon_x=1e-12, max_iteraciones=100, paso_derivada=1.0)
    filas = []
    for x0 in np.linspace(1.05, 24.5, n):
        r = ejecutar("Newton semisuave", f, df_, S0, 25 * S0, x0 * S0, crit)
        filas.append({"x0": x0, "iteraciones": r.iteraciones,
                      "evaluaciones": r.evaluaciones_funcion,
                      "error": abs(r.raiz - objetivo_smlv * S0)})
    return pd.DataFrame(filas)


# =====================================================================
# Cifras citadas del documento (tex/, copia del proyecto de Overleaf)
# =====================================================================

_SUPERINDICES = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def _latex_a_texto(s: str) -> str:
    """Convierte el contenido de una celda o macro de LaTeX en texto legible
    con la convención colombiana (coma decimal, punto de miles)."""
    s = s.strip().strip("$").strip()
    s = re.sub(r"\\ensuremath\{(.*)\}$", r"\1", s)
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = s.replace("$", "")
    s = s.replace("{,}", ",").replace("\\,", ".").replace("\\%", " %")
    s = re.sub(r"\s*\\cdot\s*10\^\{?([-0-9]+)\}?",
               lambda m: "·10" + str(int(m.group(1))).translate(_SUPERINDICES), s)
    s = s.replace("·10⁰", "")
    s = s.replace("--", "–").replace("\\ ", " ").replace("~", " ")
    return s.strip()


def _a_numero(s: str) -> float | None:
    """Valor numérico de una cifra ya convertida por _latex_a_texto."""
    t = s.replace(" %", "").replace(".", "").replace(",", ".")
    m = re.fullmatch(r"(-?[0-9.]+)(?:·10([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+))?", t)
    if not m:
        return None
    base = float(m.group(1))
    if m.group(2):
        exp = int(m.group(2).translate(str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "-0123456789")))
        base *= 10.0 ** exp
    return base


@st.cache_data(show_spinner=False)
def macros_tesis() -> dict:
    """Macros \\datoX de tex/datos_numericos.tex y tex/datos_variables.tex,
    convertidas a texto: {'EvNSG': '5,52', 'SMLV': '1.750.905', ...}."""
    salida = {}
    for nombre in ("datos_numericos.tex", "datos_variables.tex"):
        ruta = RUTA_TEX / nombre
        if not ruta.exists():
            continue
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\\newcommand\{\\dato([A-Za-z]+)\}\{(.*)\}\s*$", linea.strip())
            if m:
                salida[m.group(1)] = _latex_a_texto(m.group(2))
    return salida


def cifra(nombre: str, respaldo: str = "—") -> str:
    """Cifra del documento por el nombre de su macro (sin el prefijo «dato»)."""
    return macros_tesis().get(nombre, respaldo)


def cifra_num(nombre: str, respaldo: float = float("nan")) -> float:
    v = _a_numero(macros_tesis().get(nombre, ""))
    return respaldo if v is None else v


@st.cache_data(show_spinner=False)
def tabla_tesis(nombre: str) -> pd.DataFrame | None:
    """Tabla de tex/tablas/<nombre>.tex convertida en DataFrame de texto."""
    ruta = RUTA_TEX / "tablas" / f"{nombre}.tex"
    if not ruta.exists():
        return None
    texto = ruta.read_text(encoding="utf-8")
    filas = []
    encabezado = None
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea.endswith("\\\\") or linea.startswith(
                ("\\toprule", "\\midrule", "\\bottomrule", "\\begin", "\\end", "\\endhead")):
            continue
        celdas = [_latex_a_texto(c) for c in linea[:-2].split("&")]
        if encabezado is None:
            encabezado = celdas
        else:
            filas.append(celdas)
    if encabezado is None:
        return None
    return pd.DataFrame(filas, columns=encabezado)


@st.cache_resource(show_spinner=False)
def tiempo_por_llamada_ms() -> float:
    """Mediana del tiempo de una llamada al motor en este equipo (ms)."""
    d = poliza()
    p = parametros()
    tiempos = []
    for k in range(7):
        t0 = time.perf_counter()
        calcular_reserva(replace(d, mesada_actual=float(p.smlv * (2.0 + 0.01 * k))), p)
        tiempos.append((time.perf_counter() - t0) * 1000)
    return float(np.median(tiempos[1:]))
