# -*- coding: utf-8 -*-
"""
Definicion del PROBLEMA de la tesis y de los escenarios de prueba.

Encapsula la construccion de la funcion objetivo

        f(M) = VP(M) - KA

y de su derivada exacta VP'(M), a partir del motor actuarial, de modo que
todos los metodos del catalogo se apliquen a exactamente el mismo objeto.

Tambien define el conjunto de ESCENARIOS con los que se hace la comparacion
empirica del capitulo de resultados: se eligieron para cubrir las tres
regiones estructurales de VP identificadas en el capitulo de analisis
funcional (region plana bajo el SMLV, banda de quiebres del piso legal, y
tramo afin comercial), y ademas las dos bandas de quiebre del auxilio
funerario en 5 y 10 salarios minimos.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Callable, List, Optional, Tuple

from . import config
from .motor import DatosPoliza, Persona, calcular_reserva


# =====================================================================
# Construccion de la funcion objetivo y su derivada
# =====================================================================


class ObjetivoActuarial:
    """Valor y derivadas con reutilizacion local y conteo del motor.

    Cada solucionador inicia una ejecucion independiente. Si se solicita
    calculo conjunto, el valor y las derivadas de un mismo punto proceden
    de una unica llamada al motor; las solicitudes repetidas se reutilizan.
    """

    def __init__(self, datos, capital, params, usar_rp=False,
                 derivada_conjunta=False):
        self.datos = datos
        self.capital = float(capital)
        self.params = params
        self.usar_rp = usar_rp
        self.derivada_conjunta = derivada_conjunta
        self.nueva_ejecucion()

    def nueva_ejecucion(self):
        self.cache = {}
        self.evaluaciones_motor = 0
        self.evaluaciones_solo_valor = 0
        self.evaluaciones_con_derivada = 0
        self.solicitudes_valor = 0
        self.solicitudes_derivada = 0

    def _evaluar(self, M, derivada=False):
        clave = float(M)
        necesita_derivada = derivada or self.derivada_conjunta
        guardado = self.cache.get(clave)
        if guardado is None or (necesita_derivada and not guardado[1]):
            resultado = calcular_reserva(
                replace(self.datos, mesada_actual=clave), self.params,
                calcular_derivada=necesita_derivada,
            )
            self.evaluaciones_motor += 1
            if necesita_derivada:
                self.evaluaciones_con_derivada += 1
            else:
                self.evaluaciones_solo_valor += 1
            guardado = resultado, necesita_derivada
            self.cache[clave] = guardado
        return guardado[0]

    def __call__(self, M):
        self.solicitudes_valor += 1
        campo = "reserva_matematica_rp" if self.usar_rp else "reserva_matematica"
        return getattr(self._evaluar(M), campo) - self.capital

    def df_der(self, M):
        self.solicitudes_derivada += 1
        campo = "derivada_rm_rp_der" if self.usar_rp else "derivada_rm_der"
        return getattr(self._evaluar(M, derivada=True), campo)

    def df_izq(self, M):
        self.solicitudes_derivada += 1
        campo = "derivada_rm_rp_izq" if self.usar_rp else "derivada_rm_izq"
        return getattr(self._evaluar(M, derivada=True), campo)


def constructor_objetivo(datos: DatosPoliza,
                         capital: float,
                         params: "config.ParametrosActuariales",
                         usar_rp: bool = False,
                         derivada_conjunta: bool = False) -> Tuple[Callable, Callable, Callable]:
    r"""
    Devuelve la terna (f, df_der, df_izq) donde

        f(M)      = VP(M) - KA
        df_der(M) = VP'_+(M)   (derivada lateral derecha exacta)
        df_izq(M) = VP'_-(M)   (derivada lateral izquierda exacta)

    El par (df_izq, df_der) es exactamente el B-subdiferencial de f en M.

    NOTA DE SIGNO. En el codigo de produccion la funcion objetivo esta
    definida como KA - VP(M), que es DECRECIENTE. Aqui se usa la
    convencion opuesta, f = VP - KA, CRECIENTE, porque es la que hace que
    la teoria de metodos para funciones convexas y monotonas crecientes se
    aplique sin cambios de signo. La raiz es evidentemente la misma.
    """
    objetivo = ObjetivoActuarial(datos, capital, params, usar_rp,
                                 derivada_conjunta)
    return objetivo, objetivo.df_der, objetivo.df_izq


def valor_y_derivada(datos: DatosPoliza, M: float, params, usar_rp: bool = False):
    """Devuelve (VP(M), VP'_-(M), VP'_+(M)) en una sola evaluacion del motor."""
    r = calcular_reserva(replace(datos, mesada_actual=float(M)), params, calcular_derivada=True)
    if usar_rp:
        return r.reserva_matematica_rp, r.derivada_rm_rp_izq, r.derivada_rm_rp_der
    return r.reserva_matematica, r.derivada_rm_izq, r.derivada_rm_der


# =====================================================================
# Escenarios de prueba
# =====================================================================


@dataclass
class Escenario:
    """Un caso de valoracion completo, con su capital objetivo."""

    codigo: str
    descripcion: str
    region: str                  # region estructural de VP que se quiere provocar
    datos: DatosPoliza
    capital: float
    mesada_teorica: Optional[float] = None   # solo informativa


def _persona(anio, mes, dia, tipo, sexo, estado=1) -> Persona:
    return Persona(fecha_nacimiento=date(anio, mes, dia), tipo_beneficiario=tipo,
                   sexo=sexo, estado=estado)


def _base(codigo, causante, beneficiarios, params, n_mesadas=13,
          fecha=date(2026, 7, 31), tasa=0.0420) -> DatosPoliza:
    return DatosPoliza(
        id_pol=codigo, n_mesadas=n_mesadas, fecha_valoracion=fecha,
        smlv=params.smlv, mesada_actual=params.smlv, tasa_interes_real=tasa,
        causante=causante, beneficiarios=list(beneficiarios),
    )


def escenarios_estandar(params: Optional["config.ParametrosActuariales"] = None) -> List[Escenario]:
    """
    Bateria de nueve escenarios de valoracion.

    Se construye asi: para cada perfil demografico se fija una mesada
    OBJETIVO en la region estructural que se quiere provocar, se evalua
    VP en esa mesada, y se toma ese valor como capital KA del escenario.
    De esta forma se conoce de antemano la raiz exacta del problema y se
    puede medir el error de cada metodo contra un valor de referencia
    exacto, y no contra una solucion numerica de otro metodo.
    """
    p = params or config.ParametrosActuariales()
    S = p.smlv

    perfiles = [
        # (codigo, causante, beneficiarios, descripcion)
        ("A", _persona(1961, 5, 10, config.COD_CAUSANTE, 1),
         [_persona(1965, 3, 2, config.COD_CONYUGE, 2)],
         "Hombre 65 anios, conyuge mujer 61"),
        ("B", _persona(1969, 9, 15, config.COD_CAUSANTE, 2),
         [],
         "Mujer 56 anios, sin beneficiarios"),
        ("C", _persona(1956, 1, 20, config.COD_CAUSANTE, 1),
         [_persona(1960, 6, 6, config.COD_CONYUGE, 2),
          _persona(2010, 4, 12, config.COD_HIJO, 1)],
         "Hombre 70 anios, conyuge y un hijo menor"),
        ("D", _persona(1975, 11, 3, config.COD_CAUSANTE, 1, estado=config.ESTADO_INVALIDO),
         [_persona(1978, 2, 8, config.COD_CONYUGE, 2)],
         "Hombre 50 anios invalido, conyuge mujer 48"),
    ]

    # Multiplicadores del SMLV DELIBERADAMENTE IRRACIONALES (fracciones no
    # diadicas del intervalo de busqueda [SMLV, 25 SMLV]). Esto no es un
    # capricho metodologico: si la mesada objetivo fuese un multiplo
    # redondo del SMLV, los puntos medios sucesivos de la biseccion
    # podrian coincidir EXACTAMENTE con la raiz por pura aritmetica del
    # encaje, regalandole una convergencia artificialmente rapida y
    # viciando la comparacion. Con multiplicadores irracionales ningun
    # metodo recibe ese obsequio.
    objetivos = [
        ("R1", 0.6180339887, "region plana (VP constante, problema mal planteado)"),
        ("R2", 1.0371782684, "banda de quiebres del piso SMLV"),
        ("R3", 2.4142135624, "tramo afin comercial"),
        ("R4", 5.2360679775, "banda de quiebres del auxilio funerario (5 SMLV)"),
        ("R5", 10.3722813233, "banda de quiebres del auxilio funerario (10 SMLV)"),
    ]

    lista: List[Escenario] = []
    combinaciones = [
        ("A", "R2"), ("A", "R3"), ("A", "R4"), ("A", "R5"),
        ("B", "R3"), ("B", "R2"),
        ("C", "R3"), ("C", "R4"),
        ("D", "R3"),
    ]
    mapa_perfil = {c[0]: c for c in perfiles}
    mapa_obj = {o[0]: o for o in objetivos}

    for cod_perfil, cod_region in combinaciones:
        _, causante, benef, desc = mapa_perfil[cod_perfil]
        _, mult, region = mapa_obj[cod_region]
        datos = _base(f"{cod_perfil}{cod_region}", causante, benef, p)
        mesada_objetivo = S * mult
        capital = calcular_reserva(replace(datos, mesada_actual=mesada_objetivo), p).reserva_matematica
        lista.append(Escenario(
            codigo=f"{cod_perfil}-{cod_region}",
            descripcion=f"{desc}; objetivo {mult:.3f} SMLV, {region}",
            region=region,
            datos=datos,
            capital=float(capital),
            mesada_teorica=float(mesada_objetivo),
        ))
    return lista


def escenarios_reales(ruta_base: str,
                      params: Optional["config.ParametrosActuariales"] = None,
                      limite: Optional[int] = None) -> List[Escenario]:
    """
    Escenarios construidos a partir de POLIZAS REALES (base de cotizacion
    de la aseguradora). El capital objetivo es el `capital_renta` efectivo
    de cada cotizacion, de modo que la raiz NO se conoce de antemano.

    La raiz de referencia se obtiene con el metodo de Brent a tolerancia
    cercana a la de maquina; se usa Brent y no uno de los metodos que
    despues se comparan para no favorecer a ninguno de ellos.
    """
    import pandas as pd

    from .base_masiva import _fila_a_datos_poliza
    from .metodos_iterativos import CriterioParada, brent

    p = params or config.ParametrosActuariales()
    base = pd.read_excel(ruta_base)
    if limite:
        base = base.head(limite)

    lista: List[Escenario] = []
    for _, fila in base.iterrows():
        datos = _fila_a_datos_poliza(fila)
        datos.smlv = p.smlv
        capital = float(fila["capital_renta"])
        f, _, _ = constructor_objetivo(datos, capital, p)
        crit = CriterioParada(epsilon_f=1e-6, epsilon_x=1e-10, max_iteraciones=400)
        ref = brent(f, p.smlv, p.smlv * 25.0, crit)
        lista.append(Escenario(
            codigo=str(fila["id_cotizacion"]),
            descripcion=f"Poliza real, capital {capital:,.0f}",
            region="poliza real",
            datos=datos,
            capital=capital,
            mesada_teorica=float(ref.raiz) if ref.convergio else None,
        ))
    return lista


def capital_minimo(datos: DatosPoliza, params) -> float:
    r"""
    Capital minimo financiable KA_min = VP(SMLV).

    VP es constante en [0, SMLV] por el piso legal. Si se permiten todas
    las mesadas no negativas, KA = VP(SMLV) da un continuo de soluciones
    en ese intervalo. En el dominio admisible M >= SMLV, con crecimiento
    estricto a partir del piso, la igualdad tiene la solucion unica
    M = SMLV. Para KA < VP(SMLV) no hay solucion admisible; para capitales
    superiores hay una unica solucion cuando pertenecen al rango de VP.
    Si se impone ademas M <= 25 SMLV, se exige KA <= VP(25 SMLV).
    """
    return float(calcular_reserva(replace(datos, mesada_actual=params.smlv), params).reserva_matematica)


def detectar_quiebres(datos: DatosPoliza, params, m_min: float, m_max: float,
                      n_muestras: int = 4000, tolerancia: float = 1e-9) -> List[float]:
    """
    Localiza numericamente los puntos de quiebre de VP en [m_min, m_max]
    detectando saltos en la derivada lateral derecha exacta.

    Se usa para verificar empiricamente la caracterizacion analitica del
    conjunto de quiebres obtenida en el capitulo de analisis funcional.
    """
    import numpy as np

    malla = np.linspace(m_min, m_max, n_muestras)
    derivadas = np.array([
        calcular_reserva(replace(datos, mesada_actual=float(m)), params,
                         calcular_derivada=True).derivada_rm_der
        for m in malla
    ])
    saltos = np.abs(np.diff(derivadas))
    umbral = max(tolerancia, saltos.max() * 1e-6) if saltos.size else tolerancia
    indices = np.where(saltos > umbral)[0]
    return [float(0.5 * (malla[i] + malla[i + 1])) for i in indices]
