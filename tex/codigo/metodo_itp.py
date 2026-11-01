# core/metodos_iterativos.py :: ITP (Oliveira y Takahashi, 2021)
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
