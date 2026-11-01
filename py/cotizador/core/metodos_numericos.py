"""
Metodos numericos para encontrar la raiz de una funcion F(mesada).

Incluye biseccion (traduccion fiel de MetodoBiseccionEncontrarMesada.R),
Newton y secante. Los tres son genericos: reciben cualquier funcion f de
una variable y devuelven un resultado con el mismo formato, para que la
pagina de comparacion de metodos los pueda mostrar lado a lado.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, List, Tuple




@dataclass
class IteracionMetodo:
    """Un paso individual de la busqueda, usado para graficar la convergencia."""

    numero: int
    x: float
    f_x: float


@dataclass
class ResultadoMetodoNumerico:
    """Resultado uniforme de cualquiera de los tres metodos numericos."""

    nombre_metodo: str
    valor: float
    convergio: bool
    iteraciones: int
    historial: List[IteracionMetodo] = field(default_factory=list)
    tiempo_ejecucion_segundos: float = 0.0
    mensaje: str = ""


def biseccion(
    f: Callable[[float], float],
    a: float,
    b: float,
    params,
) -> ResultadoMetodoNumerico:
    """
    Metodo de biseccion, traduccion fiel de MetodoBiseccionEncontrarMesada.R.

    Parametros
    ----------
    f: funcion objetivo F(mesada) = capital_asegurado - Prima(mesada).
    a: mesada minima posible (limite inferior del intervalo).
    b: mesada maxima posible (limite superior del intervalo).
    params: tolerancia (epsilon) y limite de iteraciones.
    """
    tiempo_inicio = time.perf_counter()
    historial: List[IteracionMetodo] = []

    mesada_minima, mesada_maxima = a, b
    f_minima = f(mesada_minima)
    historial.append(IteracionMetodo(0, mesada_minima, f_minima))

    convergio = False
    mesada_iterada = mesada_minima
    f_mid = f_minima

    for iteracion in range(1, params.max_iteraciones + 1):
        mesada_iterada = (mesada_minima + mesada_maxima) / 2
        f_mid = f(mesada_iterada)
        historial.append(IteracionMetodo(iteracion, mesada_iterada, f_mid))

        # Condicion de parada por tolerancia, igual que el abs(f_m_mid) < epsilon del R
        if abs(f_mid) < params.epsilon:
            convergio = True
            break

        # El intervalo se cerro sin converger (mismo chequeo que el R original)
        if mesada_maxima - mesada_minima <= 0:
            break

        # Si hay cambio de signo entre el punto medio y el limite inferior, la raiz
        # esta en la mitad izquierda; si no, se mueve el limite inferior
        if f_mid * f_minima < 0:
            mesada_maxima = mesada_iterada
        else:
            mesada_minima = mesada_iterada
            f_minima = f_mid

    tiempo_total = time.perf_counter() - tiempo_inicio
    mensaje = "" if convergio else "No convergio dentro de la tolerancia o iteraciones permitidas"

    return ResultadoMetodoNumerico(
        nombre_metodo="Biseccion",
        valor=mesada_iterada,
        convergio=convergio,
        iteraciones=len(historial) - 1,
        historial=historial,
        tiempo_ejecucion_segundos=tiempo_total,
        mensaje=mensaje,
    )


def newton(
    f: Callable[[float], float],
    x0: float,
    params,
    limite_inferior: float = None,
    limite_superior: float = None,
) -> ResultadoMetodoNumerico:
    """
    Metodo de Newton usando derivada numerica (diferencias finitas centradas).

    Se usa derivada numerica porque Prima(mesada) no tiene forma cerrada:
    depende de tablas de mortalidad y flujos descontados calculados en cada
    evaluacion.

    Si se dan limite_inferior/limite_superior, cada candidato x_siguiente se
    recorta a ese rango antes de evaluarlo: cuando f es casi plana cerca del
    optimo, Newton puede extrapolar a valores absurdos (overflow en potencias
    de descuento); acotar evita eso sin cambiar el comportamiento cuando el
    candidato ya cae dentro del rango esperado.
    """
    tiempo_inicio = time.perf_counter()
    historial: List[IteracionMetodo] = []

    def _acotar(v):
        if limite_inferior is not None:
            v = max(v, limite_inferior)
        if limite_superior is not None:
            v = min(v, limite_superior)
        return v

    x = x0
    f_x = f(x)
    historial.append(IteracionMetodo(0, x, f_x))

    convergio = False
    mensaje = ""

    for iteracion in range(1, params.max_iteraciones + 1):
        if abs(f_x) < params.epsilon:
            convergio = True
            break

        # Derivada numerica centrada: (f(x+h) - f(x-h)) / (2h)
        h = params.paso_derivada
        derivada = (f(_acotar(x + h)) - f(_acotar(x - h))) / (2 * h)

        if derivada == 0:
            mensaje = "La derivada numerica se anulo, no se puede continuar"
            break

        x_siguiente = _acotar(x - f_x / derivada)
        f_x = f(x_siguiente)
        x = x_siguiente
        historial.append(IteracionMetodo(iteracion, x, f_x))

    if convergio is False and mensaje == "":
        mensaje = "No convergio dentro de la tolerancia o iteraciones permitidas"

    tiempo_total = time.perf_counter() - tiempo_inicio

    return ResultadoMetodoNumerico(
        nombre_metodo="Newton",
        valor=x,
        convergio=convergio,
        iteraciones=len(historial) - 1,
        historial=historial,
        tiempo_ejecucion_segundos=tiempo_total,
        mensaje=mensaje,
    )


def secante(
    f: Callable[[float], float],
    x0: float,
    x1: float,
    params,
    limite_inferior: float = None,
    limite_superior: float = None,
) -> ResultadoMetodoNumerico:
    """
    Metodo de la secante, usa dos puntos iniciales en vez de una derivada.

    Es una alternativa a Newton cuando no se quiere depender de una derivada
    numerica, aproximando la pendiente con los dos ultimos puntos evaluados.

    Si se dan limite_inferior/limite_superior, cada candidato x_siguiente se
    recorta a ese rango: cuando f es casi plana cerca del optimo, la
    secante puede extrapolar a valores absurdos (overflow en potencias de
    descuento); acotar evita eso sin cambiar el comportamiento cuando el
    candidato ya cae dentro del rango esperado.
    """
    tiempo_inicio = time.perf_counter()
    historial: List[IteracionMetodo] = []

    def _acotar(v):
        if limite_inferior is not None:
            v = max(v, limite_inferior)
        if limite_superior is not None:
            v = min(v, limite_superior)
        return v

    x_anterior, x_actual = x0, x1
    f_anterior = f(x_anterior)
    f_actual = f(x_actual)
    historial.append(IteracionMetodo(0, x_anterior, f_anterior))
    historial.append(IteracionMetodo(1, x_actual, f_actual))

    convergio = False
    mensaje = ""

    for iteracion in range(2, params.max_iteraciones + 1):
        if abs(f_actual) < params.epsilon:
            convergio = True
            break

        diferencia_f = f_actual - f_anterior
        if diferencia_f == 0:
            mensaje = "La diferencia entre evaluaciones se anulo, no se puede continuar"
            break

        # Formula de la secante: aproxima la pendiente con los dos ultimos puntos
        x_siguiente = _acotar(x_actual - f_actual * (x_actual - x_anterior) / diferencia_f)

        x_anterior, f_anterior = x_actual, f_actual
        x_actual = x_siguiente
        f_actual = f(x_actual)
        historial.append(IteracionMetodo(iteracion, x_actual, f_actual))

    if convergio is False and mensaje == "":
        mensaje = "No convergio dentro de la tolerancia o iteraciones permitidas"

    tiempo_total = time.perf_counter() - tiempo_inicio

    return ResultadoMetodoNumerico(
        nombre_metodo="Secante",
        valor=x_actual,
        convergio=convergio,
        iteraciones=len(historial) - 1,
        historial=historial,
        tiempo_ejecucion_segundos=tiempo_total,
        mensaje=mensaje,
    )
