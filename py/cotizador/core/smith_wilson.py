"""
Modelo Smith-Wilson: construye una curva de tasas de interes (una tasa
anual por año) que reproduce exactamente un conjunto de tasas observadas
("puntos liquidos") y converge suavemente hacia una Tasa Forward Ultima
(UFR, "Ultimate Forward Rate") para plazos largos.

Es el modelo estandar de la industria (usado por EIOPA/Solvencia II en
Europa) para extrapolar curvas de descuento mas alla del ultimo dato de
mercado confiable, evitando asumir una tasa plana indefinidamente.

Referencia: EIOPA, "Technical documentation of the methodology to derive
EIOPA's risk-free interest rate term structures".
"""

from typing import Dict

import numpy as np


def curva_smith_wilson(
    tasas_observadas: Dict[float, float],
    ufr: float,
    alpha: float,
    n_anios: int,
) -> np.ndarray:
    """
    Devuelve un array de n_anios tasas anuales (indice 0 = año 1, indice
    n_anios-1 = año n_anios), calibradas con Smith-Wilson:

    - En los años dados en `tasas_observadas` (dict {año: tasa_anual}), la
      curva resultante reproduce EXACTAMENTE esa tasa.
    - Para años mayores al ultimo punto observado, la curva converge de
      forma suave y monotona hacia `ufr` -- entre mas alto `alpha`, mas
      rapida la convergencia.

    Ambas tasas (observadas y ufr) se interpretan como tasas anuales
    efectivas (igual convencion que el resto del proyecto).
    """
    tenores = np.array(sorted(tasas_observadas.keys()), dtype=float)
    tasas = np.array([tasas_observadas[t] for t in tenores])

    ufr_continuo = np.log(1 + ufr)  # UFR anual efectiva -> tasa continua equivalente

    # Factores de descuento observados, a partir de las tasas anuales dadas
    p_mercado = (1 + tasas) ** (-tenores)

    def _wilson(t, u):
        t = np.asarray(t, dtype=float)
        u = np.asarray(u, dtype=float)
        min_tu = np.minimum(t, u)
        max_tu = np.maximum(t, u)
        return np.exp(-ufr_continuo * (t + u)) * (
            alpha * min_tu - np.exp(-alpha * max_tu) * np.sinh(alpha * min_tu)
        )

    n = len(tenores)
    matriz_w = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            matriz_w[i, j] = _wilson(tenores[i], tenores[j])

    objetivo = p_mercado - np.exp(-ufr_continuo * tenores)
    zeta = np.linalg.solve(matriz_w, objetivo)

    anios = np.arange(1, n_anios + 1, dtype=float)
    descuento = np.exp(-ufr_continuo * anios)
    for i in range(n):
        descuento += zeta[i] * _wilson(anios, tenores[i])

    tasa_anual = descuento ** (-1 / anios) - 1
    return tasa_anual
