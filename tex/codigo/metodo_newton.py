# core/metodos_iterativos.py :: Newton con diferencias finitas
# y Newton con derivada analítica exacta
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
