# core/metodos_iterativos.py :: métodos para el caso no suave
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
