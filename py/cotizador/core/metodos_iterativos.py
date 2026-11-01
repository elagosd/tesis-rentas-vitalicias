# -*- coding: utf-8 -*-
"""
Biblioteca de metodos numericos iterativos para la resolucion de la ecuacion
no lineal de equivalencia actuarial

        f(M) = VP(M) - KA = 0 .

Este modulo es el nucleo experimental de la tesis "Metodos numericos
iterativos para la cotizacion de rentas vitalicias". A diferencia de
`core/metodos_numericos.py` (que replica los tres metodos usados en
produccion), aqui se implementa el CATALOGO COMPLETO de metodos que se
comparan en el trabajo, todos con la misma interfaz e instrumentacion, de
modo que la comparacion sea justa:

  * mismo criterio de parada,
  * mismo contador de evaluaciones de la funcion objetivo,
  * mismo registro de la sucesion de iterados,
  * misma medicion de tiempo.

Taxonomia de los metodos implementados
--------------------------------------

A. Metodos con encaje (bracketing). Requieren un intervalo [a,b] con
   f(a)f(b) < 0 y GARANTIZAN convergencia global.

     1. biseccion               orden 1, razon 1/2
     2. regula_falsi            orden 1 (puede estancar un extremo)
     3. illinois                regula falsi con peso 1/2
     4. pegasus                 regula falsi con peso f2/(f2+f_nuevo)
     5. anderson_bjorck         regula falsi con peso adaptativo
     6. ridders                 orden sqrt(2) por evaluacion, usa exponencial
     7. brent                   inversa cuadratica + salvaguarda de biseccion
     8. itp                     Interpolate-Truncate-Project (Oliveira-Takahashi,
                                2021): optimo en el peor caso Y superlineal
                                en el caso bueno

B. Metodos abiertos (sin encaje). Convergencia solo local, pero de orden
   superior.

     9. secante                 orden aureo phi = 1.618...
    10. newton_diferencias      Newton con derivada por diferencias centradas
    11. newton_analitico        Newton con la derivada EXACTA de VP (aporte
                                de esta tesis, ver core/motor.py)
    12. steffensen              orden 2 sin derivada
    13. muller                  orden 1.839 (interpolacion cuadratica)
    14. halley                  orden 3 (usa f, f', f'')
    15. punto_fijo              orden 1, iteracion de contraccion
    16. aitken_steffensen       punto fijo acelerado por Delta^2 de Aitken

C. Metodos para el caso NO SUAVE, que es el que realmente corresponde a
   este problema (ver el capitulo de estructura funcional).

    17. newton_semisuave        Newton generalizado de Qi-Sun sobre un
                                elemento del B-subdiferencial
    18. newton_salvaguardado    Newton analitico con retroceso a biseccion
                                (hibrido globalmente convergente)

Convenciones
------------

Todos los metodos devuelven un `ResultadoIteracion`. El criterio de parada
por defecto es mixto: se detiene cuando |f(x_k)| < epsilon_f o cuando
|x_k - x_{k-1}| < epsilon_x. Esto es deliberado: en este problema |f| se
mide en pesos de reserva (magnitud ~1e8) mientras que x se mide en pesos de
mesada (magnitud ~1e6), y la derivada vale ~245, de modo que un criterio
puro en |f| y uno puro en |x| no son equivalentes -- el trabajo discute
esto en detalle.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple


# =====================================================================
# Instrumentacion
# =====================================================================


class ContadorFuncion:
    """
    Envuelve la funcion objetivo para contar evaluaciones.

    El numero de evaluaciones de f -- y no el numero de iteraciones -- es
    la medida honesta del costo en este problema: cada evaluacion de f
    dispara una proyeccion actuarial completa de 1.439 meses, que domina
    por completo el costo aritmetico del metodo. Un metodo que hace una
    sola iteracion pero tres evaluaciones de f es mas caro que uno que
    hace dos iteraciones con una evaluacion cada una.
    """

    def __init__(self, f: Callable[[float], float]):
        self._f = f
        if hasattr(f, "nueva_ejecucion"):
            f.nueva_ejecucion()
        self.evaluaciones_valor = 0
        self.cache: dict = {}

    @property
    def evaluaciones(self):
        """Llamadas efectivas al motor, o evaluaciones de un callable generico."""
        return getattr(self._f, "evaluaciones_motor", self.evaluaciones_valor)

    def __call__(self, x: float) -> float:
        clave = float(x)
        if clave in self.cache:
            return self.cache[clave]
        self.evaluaciones_valor += 1
        valor = self._f(clave)
        self.cache[clave] = valor
        return valor

    def sin_contar(self, x: float) -> float:
        """Evalua f sin incrementar el contador (para diagnostico)."""
        return self._f(float(x))


@dataclass
class Iterado:
    """Un paso de la sucesion, con todo lo necesario para el analisis."""

    k: int
    x: float
    fx: float
    evaluaciones_acumuladas: int = 0
    ancho_intervalo: Optional[float] = None
    derivada: Optional[float] = None
    nota: str = ""


@dataclass
class ResultadoIteracion:
    """Resultado uniforme de cualquier metodo del catalogo."""

    metodo: str
    familia: str                     # "encaje", "abierto" o "no suave"
    raiz: float
    convergio: bool
    iteraciones: int
    evaluaciones_funcion: int
    tiempo_segundos: float
    historial: List[Iterado] = field(default_factory=list)
    mensaje: str = ""
    orden_empirico: Optional[float] = None
    constante_asintotica: Optional[float] = None
    evaluaciones_valor: int = 0
    evaluaciones_con_derivada: int = 0
    estado: str = ""
    cota_error: Optional[float] = None

    # ---- utilidades de analisis -------------------------------------

    def errores(self, raiz_referencia: float) -> List[float]:
        """Sucesion |x_k - x*| frente a una raiz de referencia de alta precision."""
        return [abs(it.x - raiz_referencia) for it in self.historial]

    def residuos(self) -> List[float]:
        return [abs(it.fx) for it in self.historial]

    def estimar_orden(self, raiz_referencia: float) -> Optional[float]:
        r"""
        Estimacion del orden de convergencia p por REGRESION lineal de

            log e_{k+1} = log C + p log e_k

        sobre la cola util de la sucesion de errores e_k = |x_k - x*|.

        Se usa minimos cuadrados y no el cociente de logaritmos de tres
        terminos consecutivos porque este ultimo es muy sensible al ruido:
        basta que un iterado caiga accidentalmente cerca de la raiz para
        que el cociente devuelva un valor sin sentido. Esto ocurre
        sistematicamente con la biseccion, cuya sucesion de errores NO es
        monotona (oscila mientras el intervalo se reduce), y con los
        metodos que terminan en muy pocos pasos.

        Se descartan los errores por debajo del ruido de redondeo relativo
        (1e-14 veces la escala de la raiz), donde el error ya no obedece la
        ley asintotica sino la aritmetica de punto flotante.
        """
        escala = max(abs(raiz_referencia), 1.0)
        e = [v for v in self.errores(raiz_referencia) if v > escala * 1e-14]
        if len(e) < 4:
            return None
        xs = [math.log(v) for v in e[:-1]]
        ys = [math.log(v) for v in e[1:]]
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        sxx = sum((v - mx) ** 2 for v in xs)
        if sxx < 1e-12:
            return None
        sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        p = sxy / sxx
        self.constante_asintotica = math.exp(my - p * mx)
        return p

    def razon_lineal(self, raiz_referencia: float) -> Optional[float]:
        r"""
        Razon de convergencia lineal  R = lim e_{k+1}/e_k, estimada como la
        media geometrica de los cocientes. Es la medida adecuada para los
        metodos de orden 1 (biseccion, regula falsi, punto fijo), donde el
        "orden" p = 1 no informa nada y lo que distingue a un metodo de
        otro es precisamente esta razon (1/2 para la biseccion).
        """
        escala = max(abs(raiz_referencia), 1.0)
        e = [v for v in self.errores(raiz_referencia) if v > escala * 1e-14]
        if len(e) < 3:
            return None
        cocientes = [e[i + 1] / e[i] for i in range(len(e) - 1) if e[i] > 0]
        cocientes = [c for c in cocientes if c > 0]
        if not cocientes:
            return None
        return math.exp(sum(math.log(c) for c in cocientes) / len(cocientes))

    def razon_ancho_intervalo(self) -> Optional[float]:
        """
        Para metodos de encaje: razon media de reduccion del ancho del
        intervalo. Es la magnitud que la teoria acota (1/2 exacto para la
        biseccion) y la unica que no depende de conocer la raiz.
        """
        anchos = [it.ancho_intervalo for it in self.historial if it.ancho_intervalo and it.ancho_intervalo > 0]
        if len(anchos) < 3:
            return None
        cocientes = [anchos[i + 1] / anchos[i] for i in range(len(anchos) - 1) if anchos[i] > 0]
        cocientes = [c for c in cocientes if c > 0]
        if not cocientes:
            return None
        return math.exp(sum(math.log(c) for c in cocientes) / len(cocientes))

    def indice_eficiencia(self, raiz_referencia: float) -> Optional[float]:
        r"""
        Indice de eficiencia de Ostrowski  E = p^{1/c}, donde p es el orden
        de convergencia y c el numero de evaluaciones de f por iteracion.
        Es la medida correcta para comparar metodos cuyo costo por paso
        difiere (Newton evalua f y f'; la secante solo f).
        """
        p = self.orden_empirico or self.estimar_orden(raiz_referencia)
        if p is None or p <= 0 or self.iteraciones == 0:
            return None
        c = self.evaluaciones_funcion / max(self.iteraciones, 1)
        if c <= 0:
            return None
        return p ** (1.0 / c)


@dataclass
class CriterioParada:
    """Parametros comunes a todos los metodos."""

    epsilon_f: float = 1.0            # tolerancia en el residuo, en pesos
    epsilon_x: float = 1e-8           # tolerancia en el paso
    max_iteraciones: int = 200
    paso_derivada: float = 1.0        # h de las diferencias finitas, en pesos

    def cumple(self, fx: float, paso: Optional[float] = None) -> bool:
        """Certifica la solucion por el residuo.

        El paso se conserva en la firma por compatibilidad, pero un paso
        pequeno no certifica por si solo una raiz: un recorte al dominio
        puede producir un paso nulo con residuo no nulo. Los metodos lo
        usan como diagnostico de estancamiento.
        """
        return abs(fx) < self.epsilon_f


def _acotar(v: float, lo: Optional[float], hi: Optional[float]) -> float:
    if lo is not None:
        v = max(v, lo)
    if hi is not None:
        v = min(v, hi)
    return v


def _finalizar(metodo, familia, raiz, convergio, historial, contador, t0, mensaje="",
               cota_error=None):
    objetivo = contador._f
    if convergio:
        estado = "certificado por encaje" if cota_error is not None else "certificado por residuo"
    elif mensaje.startswith("Estancamiento"):
        estado = "estancamiento"
    else:
        estado = "sin convergencia"
    return ResultadoIteracion(
        metodo=metodo,
        familia=familia,
        raiz=float(raiz),
        convergio=bool(convergio),
        iteraciones=max(len(historial) - 1, 0),
        evaluaciones_funcion=contador.evaluaciones,
        tiempo_segundos=time.perf_counter() - t0,
        historial=historial,
        mensaje=mensaje,
        evaluaciones_valor=getattr(objetivo, "evaluaciones_solo_valor", contador.evaluaciones_valor),
        evaluaciones_con_derivada=getattr(objetivo, "evaluaciones_con_derivada", 0),
        estado=estado,
        cota_error=cota_error,
    )


# =====================================================================
# A. METODOS CON ENCAJE
# =====================================================================


def biseccion(f, a: float, b: float, crit: CriterioParada = CriterioParada()) -> ResultadoIteracion:
    r"""
    Metodo de biseccion (Bolzano).

    Fundamento: si f es continua en [a,b] y f(a)f(b) < 0, el teorema del
    valor intermedio garantiza una raiz en (a,b). Partiendo el intervalo a
    la mitad y conservando el subintervalo donde persiste el cambio de
    signo, el ancho se divide por 2 en cada paso:

        |x_k - x*| <= (b-a) / 2^{k+1}.

    Es de convergencia LINEAL con razon exactamente 1/2 y, lo que aqui
    importa mas, su cota de error no requiere hipotesis de suavidad:
    solo usa continuidad. Por eso es un metodo de referencia cuando VP
    es lineal por tramos y no diferenciable en un conjunto finito de
    puntos.

    Numero de iteraciones necesario para una tolerancia eps en x:
        k >= log2((b-a)/eps) - 1,
    cota conocida de antemano, independiente de f. Otros metodos con
    encaje y los hibridos salvaguardados tienen sus propias cotas.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []

    fa, fb = F(a), F(b)
    for extremo, valor in ((a, fa), (b, fb)):
        if crit.cumple(valor):
            hist.append(Iterado(0, extremo, valor, F.evaluaciones, abs(b - a)))
            return _finalizar("Biseccion", "encaje", extremo, True, hist, F, t0)
    if fa * fb > 0:
        hist.append(Iterado(0, a, fa, F.evaluaciones, b - a))
        return _finalizar("Biseccion", "encaje", a, False, hist, F, t0,
                          "No hay cambio de signo en el intervalo: f(a) y f(b) tienen el mismo signo")

    x = 0.5 * (a + b)
    hist.append(Iterado(0, x, F(x), F.evaluaciones, b - a))
    convergio = False

    for k in range(1, crit.max_iteraciones + 1):
        x = 0.5 * (a + b)
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones, b - a))
        if crit.cumple(fx) or (b - a) < crit.epsilon_x:
            convergio = True
            break
        if fa * fx < 0:
            b, fb = x, fx
        else:
            a, fa = x, fx

    return _finalizar("Biseccion", "encaje", x, convergio, hist, F, t0,
                      "" if convergio else "No convergio en el maximo de iteraciones",
                      cota_error=0.5 * abs(b - a) if convergio and not crit.cumple(fx) else None)


def _regula_falsi_generico(f, a, b, crit, variante: str, nombre: str) -> ResultadoIteracion:
    r"""
    Implementacion comun de la familia regula falsi y sus correcciones.

    La regula falsi pura toma como nuevo iterado la raiz de la recta que
    une (a,f(a)) con (b,f(b)):

        x = b - f(b) (b-a) / (f(b)-f(a)).

    Conserva el encaje (nunca pierde la raiz) pero sufre ESTANCAMIENTO: si
    f es convexa, un mismo extremo se retiene indefinidamente, el ancho del
    intervalo no tiende a cero y la convergencia degenera a lineal con
    razon cercana a 1. Las variantes corrigen esto reduciendo el valor de
    f en el extremo retenido por un factor gamma:

      * Illinois        gamma = 1/2 (constante).
      * Pegasus         gamma = f(b) / (f(b) + f(x)).
      * Anderson-Bjorck gamma = 1 - f(x)/f(b) si ese valor es positivo,
                        y 1/2 en caso contrario.

    Illinois y Pegasus alcanzan orden superlineal (~1.44 y ~1.64) SIN
    perder la garantia de encaje: son, en la practica, la mejor relacion
    entre robustez y velocidad para funciones poco suaves.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []

    fa, fb = F(a), F(b)
    for extremo, valor in ((a, fa), (b, fb)):
        if crit.cumple(valor):
            hist.append(Iterado(0, extremo, valor, F.evaluaciones, abs(b - a)))
            return _finalizar(nombre, "encaje", extremo, True, hist, F, t0)
    if fa * fb > 0:
        hist.append(Iterado(0, a, fa, F.evaluaciones, b - a))
        return _finalizar(nombre, "encaje", a, False, hist, F, t0, "No hay cambio de signo en el intervalo")

    if not (math.isfinite(fa) and math.isfinite(fb)):
        hist.append(Iterado(0, b, fb, F.evaluaciones, abs(b - a)))
        return _finalizar(nombre, "encaje", b, False, hist, F, t0, "Evaluacion no finita")

    # a es el extremo retenido y b el ultimo punto evaluado. La orientacion
    # puede invertirse; el ancho geometrico siempre es abs(b-a).
    x, fx = b, fb
    hist.append(Iterado(0, x, fx, F.evaluaciones, abs(b - a)))
    convergio = False

    for k in range(1, crit.max_iteraciones + 1):
        den = fb - fa
        if den == 0:
            return _finalizar(nombre, "encaje", x, False, hist, F, t0, "Denominador nulo en la interpolacion lineal")
        x = b - fb * (b - a) / den
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones, abs(b - a)))

        if not math.isfinite(fx):
            return _finalizar(nombre, "encaje", x, False, hist, F, t0, "Evaluacion no finita")

        if crit.cumple(fx) or abs(b - a) < crit.epsilon_x:
            convergio = True
            break

        if fb * fx < 0:
            # El extremo reciente reemplaza al retenido sin ponderacion.
            a, fa = b, fb
        else:
            # fb todavia es el valor del punto ANTERIOR: las variantes
            # requieren ese valor para que sus factores sean diferentes.
            if variante == "illinois":
                fa *= 0.5
            elif variante == "pegasus":
                fa *= fb / (fb + fx)
            elif variante == "anderson":
                factor = 1.0 - fx / fb
                fa *= factor if factor > 0 else 0.5
        b, fb = x, fx

    return _finalizar(nombre, "encaje", x, convergio, hist, F, t0,
                      "" if convergio else "No convergio en el maximo de iteraciones",
                      cota_error=abs(b - a) if convergio and not crit.cumple(fx) else None)


def regula_falsi(f, a, b, crit=CriterioParada()):
    """Regula falsi clasica (falsa posicion). Ver `_regula_falsi_generico`."""
    return _regula_falsi_generico(f, a, b, crit, "ninguna", "Regula Falsi")


def illinois(f, a, b, crit=CriterioParada()):
    """Variante de Illinois: peso 1/2 sobre el extremo estancado."""
    return _regula_falsi_generico(f, a, b, crit, "illinois", "Illinois")


def pegasus(f, a, b, crit=CriterioParada()):
    """Variante Pegasus (Dowell-Jarratt, 1972): peso f2/(f2+f3)."""
    return _regula_falsi_generico(f, a, b, crit, "pegasus", "Pegasus")


def anderson_bjorck(f, a, b, crit=CriterioParada()):
    """Variante de Anderson-Bjorck (1973): peso adaptativo 1 - f3/f2."""
    return _regula_falsi_generico(f, a, b, crit, "anderson", "Anderson-Bjorck")


def ridders(f, a, b, crit=CriterioParada()) -> ResultadoIteracion:
    r"""
    Metodo de Ridders (1979).

    Idea: en lugar de interpolar f linealmente, se supone que la funcion
    g(x) = f(x) e^{Q(x-x_1)} es lineal para un Q adecuado. Evaluando f en
    el punto medio x_2 = (a+b)/2 y resolviendo para Q se obtiene la
    formula explicita

        x_3 = x_2 + (x_2 - a) sign(f(a)-f(b)) f(x_2) / sqrt(f(x_2)^2 - f(a)f(b)).

    Propiedades: x_3 SIEMPRE cae dentro de [a,b] (conserva encaje) y la
    convergencia es cuadratica por PAR de evaluaciones, es decir de orden
    sqrt(2) ~ 1.414 por evaluacion de f. Es notablemente robusto ante
    funciones con curvatura fuerte.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    fa, fb = F(a), F(b)
    if fa * fb > 0:
        hist.append(Iterado(0, a, fa, F.evaluaciones, b - a))
        return _finalizar("Ridders", "encaje", a, False, hist, F, t0, "No hay cambio de signo en el intervalo")

    x = 0.5 * (a + b)
    hist.append(Iterado(0, x, F(x), F.evaluaciones, b - a))
    convergio = False

    for k in range(1, crit.max_iteraciones + 1):
        x2 = 0.5 * (a + b)
        f2 = F(x2)
        radicando = f2 * f2 - fa * fb
        if radicando <= 0:
            x = x2
            convergio = crit.cumple(f2)
            hist.append(Iterado(k, x, f2, F.evaluaciones, b - a))
            break
        signo = 1.0 if (fa - fb) > 0 else -1.0
        x3 = x2 + (x2 - a) * signo * f2 / math.sqrt(radicando)
        f3 = F(x3)
        x = x3
        hist.append(Iterado(k, x, f3, F.evaluaciones, b - a))
        if crit.cumple(f3) or abs(b - a) < crit.epsilon_x:
            convergio = True
            break
        # reencaje conservando el cambio de signo mas ajustado
        if f2 * f3 < 0:
            a, fa, b, fb = min(x2, x3), (f2 if x2 < x3 else f3), max(x2, x3), (f3 if x2 < x3 else f2)
        elif fa * f3 < 0:
            b, fb = x3, f3
        else:
            a, fa = x3, f3

    return _finalizar("Ridders", "encaje", x, convergio, hist, F, t0,
                      "" if convergio else "No convergio en el maximo de iteraciones")


def brent(f, a, b, crit=CriterioParada()) -> ResultadoIteracion:
    r"""
    Metodo de Brent (1973) = Dekker + salvaguarda.

    Combina tres ingredientes:
      * interpolacion cuadratica INVERSA cuando hay tres puntos distintos
        (ajusta x como polinomio de grado 2 en f, no al reves),
      * secante cuando solo hay dos,
      * biseccion como red de seguridad.

    En cada paso el candidato interpolado se acepta solo si satisface una
    bateria de condiciones que garantizan progreso (el paso debe caer en
    el tercio central del intervalo y reducir el ancho al menos a la mitad
    cada dos pasos); en caso contrario se bisecta. El resultado es un
    metodo que NUNCA es peor que la biseccion en el peor caso y que en la
    practica alcanza convergencia superlineal. Es el algoritmo por defecto
    de `scipy.optimize.brentq` y de la mayoria de bibliotecas cientificas.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    fa, fb = F(a), F(b)
    if fa * fb > 0:
        hist.append(Iterado(0, a, fa, F.evaluaciones, b - a))
        return _finalizar("Brent", "encaje", a, False, hist, F, t0, "No hay cambio de signo en el intervalo")

    if abs(fa) < abs(fb):
        a, b, fa, fb = b, a, fb, fa
    c, fc = a, fa
    bisecto_anterior = True
    d = 0.0
    hist.append(Iterado(0, b, fb, F.evaluaciones, abs(b - a)))
    convergio = crit.cumple(fb)

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        if fa != fc and fb != fc:
            # interpolacion cuadratica inversa
            s = (a * fb * fc / ((fa - fb) * (fa - fc))
                 + b * fa * fc / ((fb - fa) * (fb - fc))
                 + c * fa * fb / ((fc - fa) * (fc - fb)))
            nota = "cuadratica inversa"
        else:
            s = b - fb * (b - a) / (fb - fa)
            nota = "secante"

        cond1 = not (min((3 * a + b) / 4, b) <= s <= max((3 * a + b) / 4, b))
        cond2 = bisecto_anterior and abs(s - b) >= abs(b - c) / 2
        cond3 = (not bisecto_anterior) and abs(s - b) >= abs(c - d) / 2
        cond4 = bisecto_anterior and abs(b - c) < crit.epsilon_x
        cond5 = (not bisecto_anterior) and abs(c - d) < crit.epsilon_x
        if cond1 or cond2 or cond3 or cond4 or cond5:
            s = 0.5 * (a + b)
            bisecto_anterior = True
            nota = "biseccion (salvaguarda)"
        else:
            bisecto_anterior = False

        fs = F(s)
        d, c, fc = c, b, fb
        if fa * fs < 0:
            b, fb = s, fs
        else:
            a, fa = s, fs
        if abs(fa) < abs(fb):
            a, b, fa, fb = b, a, fb, fa

        hist.append(Iterado(k, b, fb, F.evaluaciones, abs(b - a), nota=nota))
        if crit.cumple(fb) or abs(b - a) < crit.epsilon_x:
            convergio = True

    return _finalizar("Brent", "encaje", b, convergio, hist, F, t0,
                      "" if convergio else "No convergio en el maximo de iteraciones")


def itp(f, a, b, crit=CriterioParada(), kappa1=0.1, kappa2=2.0, n0=1) -> ResultadoIteracion:
    r"""
    Metodo ITP -- Interpolate, Truncate and Project
    (Oliveira & Takahashi, ACM TOMS 47(1), 2021).

    Es el resultado mas reciente del catalogo y el unico que alcanza
    SIMULTANEAMENTE:
      * la cota de peor caso de la biseccion (nunca requiere mas
        iteraciones que ella, hasta n0 pasos extra), y
      * convergencia superlineal en el caso regular.

    Se estructura en tres etapas por iteracion:
      1. INTERPOLAR: candidato de regula falsi x_f.
      2. TRUNCAR: desplazar x_f hacia el punto medio, a lo sumo
         delta = kappa1 |b-a|^{kappa2}, obteniendo x_t.
      3. PROYECTAR: proyectar x_t sobre el intervalo de minmax
         [x_medio - r, x_medio + r], con r el radio que preserva la
         garantia de peor caso.

    Para este trabajo es especialmente relevante porque la garantia de la
    etapa 3 NO depende de la diferenciabilidad de f, de modo que sobrevive
    intacta en los puntos de quiebre de VP.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    fa, fb = F(a), F(b)
    for extremo, valor in ((a, fa), (b, fb)):
        if crit.cumple(valor):
            hist.append(Iterado(0, extremo, valor, F.evaluaciones, abs(b - a)))
            return _finalizar("ITP", "encaje", extremo, True, hist, F, t0)
    if fa * fb > 0:
        hist.append(Iterado(0, a, fa, F.evaluaciones, b - a))
        return _finalizar("ITP", "encaje", a, False, hist, F, t0, "No hay cambio de signo en el intervalo")

    eps = max(crit.epsilon_x, 1e-12)
    n_medio = math.ceil(math.log2(max((b - a) / (2 * eps), 2.0)))
    n_max = n_medio + n0
    j = 0
    x = 0.5 * (a + b)
    hist.append(Iterado(0, x, F(x), F.evaluaciones, b - a))
    convergio = False

    for k in range(1, crit.max_iteraciones + 1):
        x_medio = 0.5 * (a + b)
        # 1. interpolar
        x_f = (b * fa - a * fb) / (fa - fb) if fa != fb else x_medio
        # 2. truncar
        sigma = 1.0 if (x_medio - x_f) >= 0 else -1.0
        delta = kappa1 * (abs(b - a) ** kappa2)
        x_t = x_f + sigma * delta if delta <= abs(x_medio - x_f) else x_medio
        # 3. proyectar
        r = eps * (2 ** (n_max - j)) - 0.5 * (b - a)
        x_itp = x_t if abs(x_t - x_medio) <= r else x_medio - sigma * r

        fx = F(x_itp)
        x = x_itp
        hist.append(Iterado(k, x, fx, F.evaluaciones, b - a))
        if crit.cumple(fx):
            convergio = True
            break
        if fx * fa < 0:
            b, fb = x, fx
        else:
            a, fa = x, fx
        j += 1
        if (b - a) < 2 * eps:
            x = 0.5 * (a + b)
            fx = F(x)
            hist.append(Iterado(k + 1, x, fx, F.evaluaciones, b - a,
                                nota="punto medio del encaje certificado"))
            return _finalizar("ITP", "encaje", x, True, hist, F, t0,
                              "Convergencia por ancho del encaje",
                              cota_error=0.5 * (b - a))

    return _finalizar("ITP", "encaje", x, convergio, hist, F, t0,
                      "" if convergio else "No convergio en el maximo de iteraciones")


# =====================================================================
# B. METODOS ABIERTOS
# =====================================================================


def secante(f, x0: float, x1: float, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Metodo de la secante.

        x_{k+1} = x_k - f(x_k) (x_k - x_{k-1}) / (f(x_k) - f(x_{k-1})).

    Sustituye la derivada de Newton por la pendiente de la recta que une
    los dos ultimos iterados. Si f es dos veces continuamente diferenciable
    en un entorno de la raiz simple x*, el error satisface

        e_{k+1} ~ C e_k e_{k-1},

    lo que produce orden igual a la razon aurea phi = (1+sqrt5)/2 ~ 1.618.
    Como solo requiere UNA evaluacion nueva de f por paso, su indice de
    eficiencia phi^1 ~ 1.618 supera al de Newton (2^{1/2} ~ 1.414) cuando
    la derivada es cara -- que es exactamente el caso aqui, donde f' se
    obtendria por diferencias finitas al costo de dos proyecciones
    actuariales completas.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    xa, xb = x0, x1
    fa, fb = F(xa), F(xb)
    hist.append(Iterado(0, xa, fa, F.evaluaciones))
    hist.append(Iterado(1, xb, fb, F.evaluaciones))
    convergio = crit.cumple(fb)
    mensaje = ""

    for k in range(2, crit.max_iteraciones + 1):
        if convergio:
            break
        den = fb - fa
        if den == 0:
            mensaje = "Pendiente secante nula: los dos ultimos iterados dan el mismo valor de f"
            break
        x_nuevo = _acotar(xb - fb * (xb - xa) / den, lo, hi)
        paso = x_nuevo - xb
        xa, fa = xb, fb
        xb = x_nuevo
        fb = F(xb)
        hist.append(Iterado(k, xb, fb, F.evaluaciones))
        if crit.cumple(fb, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Secante", "abierto", xb, convergio, hist, F, t0, mensaje)


def newton_diferencias(f, x0: float, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Metodo de Newton-Raphson con derivada aproximada por diferencias
    centradas:

        f'(x) ~ (f(x+h) - f(x-h)) / (2h),   h = crit.paso_derivada.

    Es la version realmente implementable en este problema, porque VP no
    tiene forma cerrada derivable analiticamente en el codigo de
    produccion. Tiene dos costos que la teoria clasica de Newton no
    contempla y que la tesis analiza:

      1. COSTO: tres evaluaciones de f por iteracion (f(x), f(x+h),
         f(x-h)), lo que baja el indice de eficiencia a 2^{1/3} ~ 1.26,
         por debajo de la secante.
      2. SESGO EN LOS QUIEBRES: si el intervalo [x-h, x+h] contiene un
         punto de no diferenciabilidad, la diferencia centrada devuelve un
         PROMEDIO de las pendientes laterales, que en general no pertenece
         al subdiferencial util y puede frenar la convergencia. Fuera de
         esos intervalos, en cambio, la diferencia centrada es EXACTA,
         porque f es afin a trozos.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)
    mensaje = ""

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        h = crit.paso_derivada
        d = (F(_acotar(x + h, lo, hi)) - F(_acotar(x - h, lo, hi))) / (2 * h)
        if d == 0:
            mensaje = "Derivada numerica nula: el iterado cayo en una region plana de VP"
            break
        x_nuevo = _acotar(x - fx / d, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones, derivada=d))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Newton (dif. finitas)", "abierto", x, convergio, hist, F, t0, mensaje)


def newton_analitico(f, df, x0: float, crit=CriterioParada(), lo=None, hi=None,
                     nombre="Newton (derivada analitica)") -> ResultadoIteracion:
    r"""
    Newton-Raphson con derivada EXACTA.

    Requiere una funcion `df` que devuelva f'(x). En esta tesis df se
    obtiene de forma cerrada derivando la propia expresion del valor
    presente actuarial (ver `core/motor.py`, argumento
    `calcular_derivada=True`), lo que constituye uno de los aportes del
    trabajo: hace posible el metodo de Newton EXACTO sobre un modelo cuyo
    codigo de produccion solo ofrecia diferencias finitas.

    Consecuencia teorica notable: como f es afin a trozos, si x_0 y la
    raiz x* pertenecen al mismo tramo lineal, entonces

        x_1 = x_0 - f(x_0)/f'(x_0) = x*   EXACTAMENTE,

    y el metodo termina en UNA iteracion, no meramente "converge
    cuadraticamente". El capitulo de resultados verifica esto con error
    del orden del epsilon de maquina.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)
    mensaje = ""

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        d = df(x)
        if d == 0:
            mensaje = "Derivada nula: el iterado cayo en la region plana VP' = 0 (mesada por debajo del SMLV)"
            break
        x_nuevo = _acotar(x - fx / d, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones, derivada=d))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar(nombre, "abierto", x, convergio, hist, F, t0, mensaje)


def steffensen(f, x0: float, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Metodo de Steffensen.

        x_{k+1} = x_k - f(x_k)^2 / (f(x_k + f(x_k)) - f(x_k)).

    Alcanza orden 2 (como Newton) SIN calcular derivadas, usando el propio
    valor de f como incremento. Su punto debil en este problema es de
    escala: f se mide en pesos de reserva (~1e8) mientras que x se mide en
    pesos de mesada (~1e6), de modo que el incremento f(x_k) es ~100 veces
    mayor que la propia mesada y el metodo salta fuera del dominio
    admisible. La tesis lo incluye precisamente para documentar este modo
    de fallo, y evalua la variante ESCALADA en que el incremento se toma
    como f(x_k)/L con L una estimacion de la constante de Lipschitz.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)
    mensaje = ""

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        x_aux = _acotar(x + fx, lo, hi)
        den = F(x_aux) - fx
        if den == 0:
            mensaje = "Denominador nulo en la diferencia de Steffensen"
            break
        x_nuevo = _acotar(x - fx * fx / den, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Steffensen", "abierto", x, convergio, hist, F, t0, mensaje)


def steffensen_escalado(f, x0: float, escala, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Steffensen escalado: el incremento auxiliar se toma como f(x)/escala,
    con `escala` una estimacion de |f'| (por ejemplo el factor de renta
    actuarial ~245 de este problema). Restaura el orden 2 corrigiendo el
    desajuste dimensional entre f y x descrito en `steffensen`.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    if callable(escala):
        # Se obtiene despues de iniciar el contador, de modo que la
        # derivada que la prepara forma parte del costo del metodo.
        escala = escala()
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)
    mensaje = ""
    esc = escala if escala not in (0, None) else 1.0

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        incremento = fx / esc
        if incremento == 0:
            break
        x_aux = _acotar(x + incremento, lo, hi)
        den = F(x_aux) - fx
        if den == 0:
            mensaje = "Denominador nulo en la diferencia de Steffensen escalada"
            break
        x_nuevo = _acotar(x - fx * incremento / den, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Steffensen escalado", "abierto", x, convergio, hist, F, t0, mensaje)


def muller(f, x0: float, x1: float, x2: float, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Metodo de Muller (1956).

    Generaliza la secante interpolando una PARABOLA por los tres ultimos
    puntos y tomando como nuevo iterado la raiz de esa parabola mas
    cercana al ultimo punto (con la forma racionalizada de la formula
    cuadratica, para evitar la cancelacion catastrofica). Su orden de
    convergencia es la raiz real de t^3 = t^2 + t + 1, esto es
    p ~ 1.83929, superior a la secante y con una sola evaluacion nueva de
    f por paso.

    Observacion pertinente al problema: como VP es afin a trozos, el
    termino cuadratico de la parabola es NULO dentro de un mismo tramo y
    Muller degenera exactamente en la secante; el termino cuadratico solo
    se activa cuando los tres puntos abarcan un quiebre, donde precisamente
    la interpolacion parabolica no describe bien a la funcion. La tesis
    documenta esta perdida de ventaja.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    p0, p1, p2 = x0, x1, x2
    f0, f1, f2 = F(p0), F(p1), F(p2)
    for i, (pp, ff) in enumerate([(p0, f0), (p1, f1), (p2, f2)]):
        hist.append(Iterado(i, pp, ff, F.evaluaciones))
    convergio = crit.cumple(f2)
    mensaje = ""

    for k in range(3, crit.max_iteraciones + 1):
        if convergio:
            break
        h1, h2 = p1 - p0, p2 - p1
        if h1 == 0 or h2 == 0 or (h1 + h2) == 0:
            mensaje = "Puntos repetidos en la interpolacion cuadratica"
            break
        d1, d2 = (f1 - f0) / h1, (f2 - f1) / h2
        A = (d2 - d1) / (h2 + h1)
        B = A * h2 + d2
        C = f2
        disc = B * B - 4 * A * C
        raiz = math.sqrt(disc) if disc >= 0 else 0.0   # se toma la parte real
        den = B + raiz if abs(B + raiz) > abs(B - raiz) else B - raiz
        if den == 0:
            mensaje = "Denominador nulo en la formula de Muller"
            break
        x_nuevo = _acotar(p2 - 2 * C / den, lo, hi)
        paso = x_nuevo - p2
        p0, f0, p1, f1 = p1, f1, p2, f2
        p2 = x_nuevo
        f2 = F(p2)
        hist.append(Iterado(k, p2, f2, F.evaluaciones))
        if crit.cumple(f2, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Muller", "abierto", p2, convergio, hist, F, t0, mensaje)


def halley(f, x0: float, crit=CriterioParada(), lo=None, hi=None, df=None) -> ResultadoIteracion:
    r"""
    Metodo de Halley (metodo de las tangentes hiperbolicas, 1694).

        x_{k+1} = x_k - 2 f f' / (2 f'^2 - f f'').

    Es de orden CUBICO para raices simples de funciones tres veces
    diferenciables, el orden mas alto del catalogo. Se implementa con f' y
    f'' aproximadas por diferencias centradas (o con f' analitica si se
    suministra `df`).

    Su inclusion en la tesis tiene un proposito concreto: mostrar
    empiricamente que EL ORDEN TEORICO ALTO NO SIRVE DE NADA cuando la
    funcion no tiene la regularidad que ese orden presupone. Como VP es
    afin a trozos, f'' = 0 en casi todo punto y la formula de Halley
    colapsa exactamente en la de Newton; en los quiebres, en cambio, la
    f'' numerica explota como O(1/h) y desestabiliza el paso. Es el
    contraejemplo mas claro de que la eleccion del metodo debe guiarse por
    la estructura del problema y no por el orden nominal.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)
    mensaje = ""
    h = crit.paso_derivada

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        fmas = F(_acotar(x + h, lo, hi))
        fmenos = F(_acotar(x - h, lo, hi))
        d1 = df(x) if df is not None else (fmas - fmenos) / (2 * h)
        d2 = (fmas - 2 * fx + fmenos) / (h * h)
        den = 2 * d1 * d1 - fx * d2
        if den == 0 or d1 == 0:
            mensaje = "Denominador nulo en la formula de Halley"
            break
        x_nuevo = _acotar(x - 2 * fx * d1 / den, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones, derivada=d1))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Halley", "abierto", x, convergio, hist, F, t0, mensaje)


def punto_fijo(f, x0: float, lambda_relajacion, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Iteracion de punto fijo con relajacion:

        g(x) = x + lambda f(x),      x_{k+1} = g(x_k).

    Por el teorema de la aplicacion contractiva de Banach, la iteracion
    converge si |g'(x)| = |1 + lambda f'(x)| <= L < 1 en un entorno de la
    raiz, es decir si lambda esta en (-2/f', 0) para f' > 0. El valor
    optimo es lambda = -1/f', que reproduce exactamente el metodo de
    Newton -- de modo que el punto fijo relajado puede leerse como un
    Newton con derivada CONGELADA.

    En este problema f' ~ 245 es practicamente constante en todo el rango
    comercial, lo que hace que la eleccion lambda = -1/245 sea casi
    optima globalmente. Es el ejemplo perfecto de como la estructura afin
    a trozos permite que un metodo de orden 1 se comporte como uno de
    orden alto.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    if callable(lambda_relajacion):
        # Se obtiene despues de iniciar el contador, de modo que la
        # derivada que la prepara forma parte del costo del metodo.
        lambda_relajacion = lambda_relajacion()
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        x_nuevo = _acotar(x + lambda_relajacion * fx, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    return _finalizar("Punto fijo relajado", "abierto", x, convergio, hist, F, t0,
                      "" if convergio else "No convergio en el maximo de iteraciones")


def aitken_steffensen(f, x0: float, lambda_relajacion, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Punto fijo acelerado con el proceso Delta^2 de Aitken (esquema de
    Steffensen sobre g(x) = x + lambda f(x)):

        x* ~ x_k - (Delta x_k)^2 / Delta^2 x_k .

    Convierte una sucesion linealmente convergente en una cuadraticamente
    convergente. Requiere dos evaluaciones de g por paso.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    if callable(lambda_relajacion):
        # Se obtiene despues de iniciar el contador, de modo que la
        # derivada que la prepara forma parte del costo del metodo.
        lambda_relajacion = lambda_relajacion()
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)
    mensaje = ""

    def g(u):
        return _acotar(u + lambda_relajacion * F(u), lo, hi)

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        x1 = g(x)
        x2 = g(x1)
        den = x2 - 2 * x1 + x
        if den == 0:
            x_nuevo = x2
        else:
            x_nuevo = _acotar(x - (x1 - x) ** 2 / den, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Aitken-Steffensen", "abierto", x, convergio, hist, F, t0, mensaje)


# =====================================================================
# C. METODOS PARA EL CASO NO SUAVE
# =====================================================================


def newton_semisuave(f, subgradiente, x0: float, crit=CriterioParada(), lo=None, hi=None) -> ResultadoIteracion:
    r"""
    Metodo de Newton semisuave (Qi & Sun, Math. Programming 58, 1993).

        x_{k+1} = x_k - V_k^{-1} f(x_k),    V_k in partial_B f(x_k),

    donde partial_B f es el B-subdiferencial (el conjunto de limites de
    jacobianos en puntos de diferenciabilidad). Es el metodo TEORICAMENTE
    CORRECTO para este problema, porque:

      * f es lineal por tramos, luego es FUERTEMENTE semisuave;
      * en la raiz todos los elementos de partial_B f(x*) son positivos
        (BD-regularidad), pues cada uno es una suma de factores de renta
        actuarial estrictamente positivos.

    Bajo esas dos condiciones el teorema de Qi-Sun garantiza convergencia
    local de orden 2. Para funciones lineales a trozos el resultado es aun
    mas fuerte: la convergencia es FINITA, es decir se alcanza la raiz
    exacta en un numero finito de pasos.

    `subgradiente(x)` debe devolver un elemento de partial_B f(x). En esta
    tesis se toma la derivada lateral derecha, que se calcula de forma
    cerrada en `core/motor.py`.
    """
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    x = _acotar(x0, lo, hi)
    fx = F(x)
    hist.append(Iterado(0, x, fx, F.evaluaciones))
    convergio = crit.cumple(fx)
    mensaje = ""

    for k in range(1, crit.max_iteraciones + 1):
        if convergio:
            break
        V = subgradiente(x)
        if V == 0:
            mensaje = "Elemento del B-subdiferencial nulo: iterado en la region plana VP' = 0"
            break
        x_nuevo = _acotar(x - fx / V, lo, hi)
        paso = x_nuevo - x
        x = x_nuevo
        fx = F(x)
        hist.append(Iterado(k, x, fx, F.evaluaciones, derivada=V))
        if crit.cumple(fx, paso):
            convergio = True
        elif abs(paso) < crit.epsilon_x:
            mensaje = "Estancamiento sin satisfacer el residuo"
            break

    if not convergio and not mensaje:
        mensaje = "No convergio en el maximo de iteraciones"
    return _finalizar("Newton semisuave", "no suave", x, convergio, hist, F, t0, mensaje)


def newton_salvaguardado(f, subgradiente, a: float, b: float, crit=CriterioParada()) -> ResultadoIteracion:
    r"""
    Newton semisuave con biseccion periodica y encaje conservado.

    Tras cada evaluacion se actualiza el intervalo. Se admiten como maximo
    dos propuestas consecutivas de Newton en su interior; la siguiente
    propuesta es obligatoriamente el punto medio. Los candidatos no finitos,
    con derivada nula o exteriores tambien se sustituyen por biseccion.
    En aritmetica exacta, cada tres propuestas reducen el ancho al menos
    a la mitad. Un paso pequeno por si solo no certifica convergencia.
    """
    if not a < b:
        raise ValueError("El extremo inferior debe ser menor que el superior")
    t0 = time.perf_counter()
    F = ContadorFuncion(f)
    hist: List[Iterado] = []
    fa, fb = F(a), F(b)
    for extremo, valor in ((a, fa), (b, fb)):
        if crit.cumple(valor):
            hist.append(Iterado(0, extremo, valor, F.evaluaciones, b - a))
            return _finalizar("Newton salvaguardado", "no suave", extremo,
                              True, hist, F, t0)
    if not (math.isfinite(fa) and math.isfinite(fb)):
        hist.append(Iterado(0, a, fa, F.evaluaciones, b - a))
        return _finalizar("Newton salvaguardado", "no suave", a,
                          False, hist, F, t0, "Evaluacion no finita en los extremos")
    if fa * fb > 0:
        hist.append(Iterado(0, a, fa, F.evaluaciones, b - a))
        return _finalizar("Newton salvaguardado", "no suave", a, False, hist, F, t0,
                          "No hay cambio de signo en el intervalo")

    x = 0.5 * (a + b)
    fx = F(x)
    if crit.cumple(fx):
        hist.append(Iterado(0, x, fx, F.evaluaciones, b - a))
        return _finalizar("Newton salvaguardado", "no suave", x,
                          True, hist, F, t0)
    if fa * fx < 0:
        b, fb = x, fx
    else:
        a, fa = x, fx
    hist.append(Iterado(0, x, fx, F.evaluaciones, b - a,
                        nota="punto medio inicial"))
    consecutivos_newton = 0

    for k in range(1, crit.max_iteraciones + 1):
        if 0.5 * (b - a) <= crit.epsilon_x:
            x = 0.5 * (a + b)
            fx = F(x)
            hist.append(Iterado(k, x, fx, F.evaluaciones, b - a,
                                nota="punto medio del encaje certificado"))
            return _finalizar("Newton salvaguardado", "no suave", x,
                              True, hist, F, t0,
                              "Convergencia por ancho del encaje",
                              cota_error=0.5 * (b - a))

        V = None
        if consecutivos_newton >= 2:
            candidato = 0.5 * (a + b)
            nota = "biseccion periodica"
            consecutivos_newton = 0
        else:
            V = subgradiente(x)
            candidato = x - fx / V if V and math.isfinite(V) else float("nan")
            if math.isfinite(candidato) and a < candidato < b:
                nota = "newton semisuave"
                consecutivos_newton += 1
            else:
                candidato = 0.5 * (a + b)
                nota = "biseccion (propuesta de Newton no admisible)"
                consecutivos_newton = 0

        if not a < candidato < b:
            return _finalizar("Newton salvaguardado", "no suave", x,
                              False, hist, F, t0,
                              "Estancamiento: no hay punto interior representable")

        x = candidato
        fx = F(x)
        if not math.isfinite(fx):
            hist.append(Iterado(k, x, fx, F.evaluaciones, b - a,
                                derivada=V, nota=nota))
            return _finalizar("Newton salvaguardado", "no suave", x,
                              False, hist, F, t0, "Evaluacion no finita")
        if crit.cumple(fx):
            hist.append(Iterado(k, x, fx, F.evaluaciones, b - a,
                                derivada=V, nota=nota))
            return _finalizar("Newton salvaguardado", "no suave", x,
                              True, hist, F, t0)
        if fa * fx < 0:
            b, fb = x, fx
        else:
            a, fa = x, fx
        hist.append(Iterado(k, x, fx, F.evaluaciones, b - a, derivada=V, nota=nota))

    return _finalizar("Newton salvaguardado", "no suave", x, False, hist, F, t0,
                      "No convergio en el maximo de iteraciones")


# =====================================================================
# Registro del catalogo
# =====================================================================

FAMILIAS = {
    "Biseccion": "encaje", "Regula Falsi": "encaje", "Illinois": "encaje",
    "Pegasus": "encaje", "Anderson-Bjorck": "encaje", "Ridders": "encaje",
    "Brent": "encaje", "ITP": "encaje",
    "Secante": "abierto", "Newton (dif. finitas)": "abierto",
    "Newton (derivada analitica)": "abierto", "Steffensen": "abierto",
    "Steffensen escalado": "abierto", "Muller": "abierto", "Halley": "abierto",
    "Punto fijo relajado": "abierto", "Aitken-Steffensen": "abierto",
    "Newton semisuave": "no suave", "Newton salvaguardado": "no suave",
}

# Orden de convergencia TEORICO, para contrastarlo con el empirico.
ORDEN_TEORICO = {
    "Biseccion": 1.0, "Regula Falsi": 1.0, "Illinois": 1.442, "Pegasus": 1.642,
    "Anderson-Bjorck": 1.71, "Ridders": 2.0, "Brent": None, "ITP": 1.618,
    "Secante": 1.618, "Newton (dif. finitas)": 2.0, "Newton (derivada analitica)": 2.0,
    "Steffensen": 2.0, "Steffensen escalado": 2.0, "Muller": 1.839, "Halley": 3.0,
    "Punto fijo relajado": 1.0, "Aitken-Steffensen": 2.0,
    "Newton semisuave": 2.0, "Newton salvaguardado": None,
}
