# core/metodos_iterativos.py :: familia de encaje
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
