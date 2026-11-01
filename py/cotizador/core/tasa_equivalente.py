"""
Encontrar Tasa Equivalente: replica la hoja EncontarTasaEquivalente del
Excel de nota tecnica.

Dos pasos secuenciales (tal como las macros Bisecciontasaequivalente_parte1
+ EncontrarValorCercanoACero del Excel):

1) Con la mesada de referencia FIJA (datos.mesada_actual) y la curva MTM/TMR
   cargada en Parametrizacion Actuarial, se calcula la Prima usando la curva
   completa (no un solo numero) -> ese valor es el "Capital Acumulado"
   objetivo (equivalente a la macro que copia C22 en G12).
2) Se busca la tasa real PLANA que, usada en vez de la curva, reproduce esa
   misma Prima (biseccion/secante/newton sobre f(tasa) = Capital - Prima(tasa)).
   Esa es la "tasa equivalente".
3) Con la tasa equivalente ya FIJA, se busca la mesada que hace que la Prima
   iguale el Capital Acumulado real (que puede ser un numero distinto al del
   paso 1, p.ej. el fondo realmente acumulado de la cedula) -> f(mesada) =
   Capital - Prima(mesada).

Los pasos 2 y 3 usan el metodo de iteracion configurado en Parametrizacion
Actuarial (por defecto: secante).
"""

from dataclasses import dataclass, replace
from typing import Optional

from . import config
from .metodos_numericos import biseccion, newton, secante
from .motor import DatosPoliza, calcular_reserva


@dataclass
class ResultadoTasaEquivalente:
    id_pol: str
    capital_objetivo_tasa: float
    tasa_equivalente: float
    convergio_tasa: bool
    iteraciones_tasa: int
    capital_objetivo_mesada: float
    mesada_encontrada: float
    convergio_mesada: bool
    iteraciones_mesada: int
    prima_final: float
    duracion_macaulay: float = 0.0


class _ParamsIteracion:
    def __init__(self, params: "config.ParametrosActuariales"):
        self.epsilon = params.epsilon
        self.max_iteraciones = params.max_iteraciones
        self.paso_derivada = params.paso_derivada


def _resolver(f, x0, x1, params: "config.ParametrosActuariales"):
    """Corre el metodo configurado, acotando el candidato de cada iteracion
    al rango [x0, x1]: la secante y Newton pueden extrapolar fuera de rango
    cuando la funcion es casi plana, lo que dispara valores absurdos
    (overflow en las potencias del descuento). Bisección nunca sale de
    rango por construccion."""
    p = _ParamsIteracion(params)
    if params.metodo_iteracion == "biseccion":
        return biseccion(f, x0, x1, p)
    if params.metodo_iteracion == "newton":
        return newton(f, (x0 + x1) / 2, p, limite_inferior=x0, limite_superior=x1)
    return secante(f, x0, x1, p, limite_inferior=x0, limite_superior=x1)


def capital_acumulado_con_curva(
    datos: DatosPoliza, params: "config.ParametrosActuariales"
) -> float:
    """Prima calculada usando la curva MTM/TMR completa (columna EG pegada),
    con la mesada de referencia (datos.mesada_actual) fija. Equivale al
    valor que la macro Bisecciontasaequivalente_parte1 copia en G12."""
    curva = params.curva_expandida()
    if not curva:
        raise ValueError("No hay una curva MTM/TMR cargada en Parametrizacion Actuarial.")
    datos_curva = replace(datos, curva_tasa=curva)
    resultado = calcular_reserva(datos_curva, params)
    return resultado.prima


def encontrar_tasa_equivalente(
    datos: DatosPoliza,
    capital_objetivo: float,
    params: "config.ParametrosActuariales",
) -> "tuple":
    """Paso 2: biseccion/secante/newton sobre la tasa real plana (datos.mesada_actual fijo)."""

    def f(tasa: float) -> float:
        datos_iter = replace(datos, tasa_interes_real=tasa, curva_tasa=None)
        r = calcular_reserva(datos_iter, params)
        return capital_objetivo - r.prima

    resultado = _resolver(f, params.tasa_equivalente_min, params.tasa_equivalente_max, params)
    return resultado


def encontrar_mesada_con_tasa_fija(
    datos: DatosPoliza,
    tasa_equivalente: float,
    capital_objetivo: float,
    params: "config.ParametrosActuariales",
) -> "tuple":
    """Paso 3: biseccion/secante/newton sobre la mesada, con la tasa equivalente fija."""

    def f(mesada: float) -> float:
        datos_iter = replace(datos, tasa_interes_real=tasa_equivalente, mesada_actual=mesada, curva_tasa=None)
        r = calcular_reserva(datos_iter, params)
        return capital_objetivo - r.prima

    mesada_min = params.smlv
    mesada_max = params.smlv * 25
    resultado = _resolver(f, mesada_min, mesada_max, params)
    return resultado


def resolver_tasa_y_mesada(
    datos: DatosPoliza,
    params: "config.ParametrosActuariales",
    capital_objetivo_mesada: Optional[float] = None,
) -> ResultadoTasaEquivalente:
    """
    Corre el proceso completo: (1) capital objetivo via curva con la mesada
    de referencia fija, (2) tasa equivalente, (3) mesada final.

    Si capital_objetivo_mesada es None, se reutiliza el mismo capital
    calculado en el paso 1 (como en la hoja de ejemplo del Excel, donde
    ambos pasos usan el mismo "Capital ACUMULADO"). Si se pasa un valor
    (p.ej. el capital realmente acumulado de la cedula en la base masiva),
    se usa ese en el paso 3 en su lugar.
    """
    capital_curva = capital_acumulado_con_curva(datos, params)

    res_tasa = encontrar_tasa_equivalente(datos, capital_curva, params)
    tasa_equivalente = res_tasa.valor

    capital_mesada = capital_objetivo_mesada if capital_objetivo_mesada is not None else capital_curva
    res_mesada = encontrar_mesada_con_tasa_fija(datos, tasa_equivalente, capital_mesada, params)
    mesada_encontrada = res_mesada.valor

    datos_final = replace(datos, tasa_interes_real=tasa_equivalente, mesada_actual=mesada_encontrada, curva_tasa=None)
    resultado_final = calcular_reserva(datos_final, params)
    prima_final = resultado_final.prima

    return ResultadoTasaEquivalente(
        id_pol=datos.id_pol,
        capital_objetivo_tasa=capital_curva,
        tasa_equivalente=tasa_equivalente,
        convergio_tasa=res_tasa.convergio,
        iteraciones_tasa=res_tasa.iteraciones,
        capital_objetivo_mesada=capital_mesada,
        mesada_encontrada=mesada_encontrada,
        convergio_mesada=res_mesada.convergio,
        iteraciones_mesada=res_mesada.iteraciones,
        prima_final=prima_final,
        duracion_macaulay=resultado_final.duracion_macaulay,
    )
