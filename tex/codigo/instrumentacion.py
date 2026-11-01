# Fragmento de core/metodos_iterativos.py: instrumentación común.
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
