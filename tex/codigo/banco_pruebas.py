# core/banco_pruebas.py :: protocolo de comparación
def ejecutar_catalogo(escenario: Escenario,
                      params: "config.ParametrosActuariales",
                      crit: Optional[CriterioParada] = None,
                      usar_rp: bool = False) -> Dict[str, ResultadoIteracion]:
    """Corre los 19 metodos con un objetivo independiente para cada uno."""
    crit = crit or CriterioParada(epsilon_f=1.0, epsilon_x=1e-8,
                                  max_iteraciones=200, paso_derivada=1.0)
    a = params.smlv
    b = params.smlv * 25.0
    medio = 0.5 * (a + b)

    def relajacion(df):
        d0 = df(medio)
        return -1.0 / d0 if d0 else -1e-3

    catalogo = [
        ("Biseccion", False, lambda f, df: biseccion(f, a, b, crit)),
        ("Regula Falsi", False, lambda f, df: regula_falsi(f, a, b, crit)),
        ("Illinois", False, lambda f, df: illinois(f, a, b, crit)),
        ("Pegasus", False, lambda f, df: pegasus(f, a, b, crit)),
        ("Anderson-Bjorck", False, lambda f, df: anderson_bjorck(f, a, b, crit)),
        ("Ridders", False, lambda f, df: ridders(f, a, b, crit)),
        ("Brent", False, lambda f, df: brent(f, a, b, crit)),
        ("ITP", False, lambda f, df: itp(f, a, b, crit)),
        ("Secante", False, lambda f, df: secante(f, a, b, crit, lo=a, hi=b)),
        ("Newton (dif. finitas)", False, lambda f, df: newton_diferencias(f, medio, crit, lo=a, hi=b)),
        ("Newton (derivada analitica)", True, lambda f, df: newton_analitico(f, df, medio, crit, lo=a, hi=b)),
        ("Steffensen", False, lambda f, df: steffensen(f, medio, crit, lo=a, hi=b)),
        ("Steffensen escalado", False, lambda f, df: steffensen_escalado(f, medio, lambda: df(medio), crit, lo=a, hi=b)),
        ("Muller", False, lambda f, df: muller(f, a, medio, b, crit, lo=a, hi=b)),
        ("Halley", False, lambda f, df: halley(f, medio, crit, lo=a, hi=b)),
        ("Punto fijo relajado", False, lambda f, df: punto_fijo(f, medio, lambda: relajacion(df), crit, lo=a, hi=b)),
        ("Aitken-Steffensen", False, lambda f, df: aitken_steffensen(f, medio, lambda: relajacion(df), crit, lo=a, hi=b)),
        ("Newton semisuave", True, lambda f, df: newton_semisuave(f, df, medio, crit, lo=a, hi=b)),
        ("Newton salvaguardado", True, lambda f, df: newton_salvaguardado(f, df, a, b, crit)),
    ]
    resultados: Dict[str, ResultadoIteracion] = {}
    for nombre, conjunta, resolver in catalogo:
        f, df_der, _ = constructor_objetivo(
            escenario.datos, escenario.capital, params, usar_rp,
            derivada_conjunta=conjunta,
        )
        resultados[nombre] = resolver(f, df_der)
    return resultados


def tabla_resultados(escenarios: List[Escenario],
                     params: "config.ParametrosActuariales",
                     crit: Optional[CriterioParada] = None) -> pd.DataFrame:
    """DataFrame largo con una fila por (escenario, metodo)."""
    filas = []
    for esc in escenarios:
        ref = esc.mesada_teorica
        res = ejecutar_catalogo(esc, params, crit)
        for nombre, r in res.items():
            err_abs = abs(r.raiz - ref) if ref else float("nan")
            filas.append({
                "escenario": esc.codigo,
                "region": esc.region,
                "metodo": nombre,
                "familia": r.familia,
                "convergio": r.convergio,
                "iteraciones": r.iteraciones,
                "evaluaciones": r.evaluaciones_funcion,
                "evaluaciones_valor": r.evaluaciones_valor,
                "evaluaciones_con_derivada": r.evaluaciones_con_derivada,
                "tiempo_ms": r.tiempo_segundos * 1000,
                "raiz": r.raiz,
                "error_abs": err_abs,
                "error_rel": err_abs / abs(ref) if ref else float("nan"),
                "residuo": abs(r.historial[-1].fx) if r.historial else float("nan"),
                "orden_empirico": r.estimar_orden(ref) if ref else None,
                "razon_lineal": r.razon_lineal(ref) if ref else None,
                "razon_intervalo": r.razon_ancho_intervalo(),
                "orden_teorico": ORDEN_TEORICO.get(nombre),
                "indice_eficiencia": r.indice_eficiencia(ref) if ref else None,
                "mensaje": r.mensaje,
                "estado": r.estado,
                "cota_error": r.cota_error,
            })
    return pd.DataFrame(filas)
