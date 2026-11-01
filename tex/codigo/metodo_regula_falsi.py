# core/metodos_iterativos.py :: regula falsi y sus tres correcciones
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
