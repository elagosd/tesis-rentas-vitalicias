# core/metodos_iterativos.py :: ResultadoIteracion
# Estimadores del orden y de la razón de convergencia.
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
