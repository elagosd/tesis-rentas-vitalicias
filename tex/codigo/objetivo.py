# core/problema_tesis.py :: construcción de f y de su subdiferencial
class ObjetivoActuarial:
    """Valor y derivadas con reutilizacion local y conteo del motor.

    Cada solucionador inicia una ejecucion independiente. Si se solicita
    calculo conjunto, el valor y las derivadas de un mismo punto proceden
    de una unica llamada al motor; las solicitudes repetidas se reutilizan.
    """

    def __init__(self, datos, capital, params, usar_rp=False,
                 derivada_conjunta=False):
        self.datos = datos
        self.capital = float(capital)
        self.params = params
        self.usar_rp = usar_rp
        self.derivada_conjunta = derivada_conjunta
        self.nueva_ejecucion()

    def nueva_ejecucion(self):
        self.cache = {}
        self.evaluaciones_motor = 0
        self.evaluaciones_solo_valor = 0
        self.evaluaciones_con_derivada = 0
        self.solicitudes_valor = 0
        self.solicitudes_derivada = 0

    def _evaluar(self, M, derivada=False):
        clave = float(M)
        necesita_derivada = derivada or self.derivada_conjunta
        guardado = self.cache.get(clave)
        if guardado is None or (necesita_derivada and not guardado[1]):
            resultado = calcular_reserva(
                replace(self.datos, mesada_actual=clave), self.params,
                calcular_derivada=necesita_derivada,
            )
            self.evaluaciones_motor += 1
            if necesita_derivada:
                self.evaluaciones_con_derivada += 1
            else:
                self.evaluaciones_solo_valor += 1
            guardado = resultado, necesita_derivada
            self.cache[clave] = guardado
        return guardado[0]

    def __call__(self, M):
        self.solicitudes_valor += 1
        campo = "reserva_matematica_rp" if self.usar_rp else "reserva_matematica"
        return getattr(self._evaluar(M), campo) - self.capital

    def df_der(self, M):
        self.solicitudes_derivada += 1
        campo = "derivada_rm_rp_der" if self.usar_rp else "derivada_rm_der"
        return getattr(self._evaluar(M, derivada=True), campo)

    def df_izq(self, M):
        self.solicitudes_derivada += 1
        campo = "derivada_rm_rp_izq" if self.usar_rp else "derivada_rm_izq"
        return getattr(self._evaluar(M, derivada=True), campo)


def constructor_objetivo(datos: DatosPoliza,
                         capital: float,
                         params: "config.ParametrosActuariales",
                         usar_rp: bool = False,
                         derivada_conjunta: bool = False) -> Tuple[Callable, Callable, Callable]:
    r"""
    Devuelve la terna (f, df_der, df_izq) donde

        f(M)      = VP(M) - KA
        df_der(M) = VP'_+(M)   (derivada lateral derecha exacta)
        df_izq(M) = VP'_-(M)   (derivada lateral izquierda exacta)

    El par (df_izq, df_der) es exactamente el B-subdiferencial de f en M.

    NOTA DE SIGNO. En el codigo de produccion la funcion objetivo esta
    definida como KA - VP(M), que es DECRECIENTE. Aqui se usa la
    convencion opuesta, f = VP - KA, CRECIENTE, porque es la que hace que
    la teoria de metodos para funciones convexas y monotonas crecientes se
    aplique sin cambios de signo. La raiz es evidentemente la misma.
    """
    objetivo = ObjetivoActuarial(datos, capital, params, usar_rp,
                                 derivada_conjunta)
    return objetivo, objetivo.df_der, objetivo.df_izq
