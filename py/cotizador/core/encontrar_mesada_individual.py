"""
Encontrar Mesada (individual): replica la hoja EncontrarMesada del Excel
para una sola cedula.

f(mesada) = Capital_Asegurado - Reserva_Matematica(mesada)

IMPORTANTE (validado contra Nueva_nota_tecnica_30_jul_2026_econtrar_mesada.xlsm,
hoja EncontrarMesada): en esta hoja el unico recargo presente esta etiquetado
"Recargo_Gastos_Prima" (C19 = ((1/(1-5%))-1)*(C16+C17+C18)), y alimenta lo
que la hoja llama "Reserva Matematica" (C20 = C16+C17+C18+C19). Es decir,
aunque la etiqueta final diga "Reserva Matematica", el recargo usado es el
de PRIMA, no el de reserva. Por eso aqui se usa r.prima (que en
core/motor.py se construye con params.porcentaje_recargo_gastos_prima) como
la cantidad que debe igualar el capital asegurado, aunque en pantalla se
siga llamando "Reserva Matematica" (para no confundir con la terminologia
del Excel).

A diferencia de Encontrar Tasa Equivalente, aqui la tasa de interes real es
un dato de entrada fijo (no se busca una tasa equivalente): solo se itera
la mesada.
"""

from dataclasses import replace

from . import config
from .metodos_numericos import biseccion, newton, secante
from .motor import DatosPoliza, ResultadoReserva, calcular_reserva


class _ParamsIteracion:
    def __init__(self, params: "config.ParametrosActuariales"):
        self.epsilon = params.epsilon
        self.max_iteraciones = params.max_iteraciones
        self.paso_derivada = params.paso_derivada


def encontrar_mesada(
    datos: DatosPoliza,
    capital_asegurado: float,
    params: "config.ParametrosActuariales",
) -> "tuple":
    """Busca la mesada que hace que la "Reserva Matematica" (que en esta
    hoja se construye con el % Recargo Gastos Prima, ver docstring del
    modulo) iguale el capital asegurado.
    Devuelve (resultado_metodo_numerico, ResultadoReserva final)."""

    def f(mesada: float) -> float:
        datos_iter = replace(datos, mesada_actual=mesada)
        r = calcular_reserva(datos_iter, params)
        return capital_asegurado - r.prima

    mesada_min = params.smlv
    mesada_max = params.smlv * 25

    p = _ParamsIteracion(params)
    if params.metodo_iteracion == "biseccion":
        resultado = biseccion(f, mesada_min, mesada_max, p)
    elif params.metodo_iteracion == "newton":
        resultado = newton(f, (mesada_min + mesada_max) / 2, p, limite_inferior=mesada_min, limite_superior=mesada_max)
    else:
        resultado = secante(f, mesada_min, mesada_max, p, limite_inferior=mesada_min, limite_superior=mesada_max)

    datos_final = replace(datos, mesada_actual=resultado.valor)
    resultado_reserva: ResultadoReserva = calcular_reserva(datos_final, params)

    return resultado, resultado_reserva
