# core/problema_tesis.py :: verificación numérica de la estructura
def capital_minimo(datos: DatosPoliza, params) -> float:
    r"""
    Capital minimo financiable KA_min = VP(SMLV).

    VP es constante en [0, SMLV] por el piso legal. Si se permiten todas
    las mesadas no negativas, KA = VP(SMLV) da un continuo de soluciones
    en ese intervalo. En el dominio admisible M >= SMLV, con crecimiento
    estricto a partir del piso, la igualdad tiene la solucion unica
    M = SMLV. Para KA < VP(SMLV) no hay solucion admisible; para capitales
    superiores hay una unica solucion cuando pertenecen al rango de VP.
    Si se impone ademas M <= 25 SMLV, se exige KA <= VP(25 SMLV).
    """
    return float(calcular_reserva(replace(datos, mesada_actual=params.smlv), params).reserva_matematica)


def detectar_quiebres(datos: DatosPoliza, params, m_min: float, m_max: float,
                      n_muestras: int = 4000, tolerancia: float = 1e-9) -> List[float]:
    """
    Localiza numericamente los puntos de quiebre de VP en [m_min, m_max]
    detectando saltos en la derivada lateral derecha exacta.

    Se usa para verificar empiricamente la caracterizacion analitica del
    conjunto de quiebres obtenida en el capitulo de analisis funcional.
    """
    import numpy as np

    malla = np.linspace(m_min, m_max, n_muestras)
    derivadas = np.array([
        calcular_reserva(replace(datos, mesada_actual=float(m)), params,
                         calcular_derivada=True).derivada_rm_der
        for m in malla
    ])
    saltos = np.abs(np.diff(derivadas))
    umbral = max(tolerancia, saltos.max() * 1e-6) if saltos.size else tolerancia
    indices = np.where(saltos > umbral)[0]
    return [float(0.5 * (malla[i] + malla[i + 1])) for i in indices]
