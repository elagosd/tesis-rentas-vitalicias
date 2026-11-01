# core/metodos_iterativos.py :: familia de métodos abiertos
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
