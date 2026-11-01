"""
Datos auxiliares y tabla de mortalidad mensualizada por persona.

Replica exactamente el bloque "Contingencia - Afiliado Titular / Beneficiario N"
de la hoja EncontrarMesada (columnas AT:DM) y el bloque de auxilio funerario
(columnas AC:AG), fila a fila.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config


@dataclass
class DatosAuxiliares:
    auxiliar: int
    anio_factores_mejora: int
    edad_mensual: int
    auxiliar_2: int
    dura_y: int


def datos_auxiliar(
    sexo: int,
    estado: int,
    tipo_beneficiario: int,
    fecha_emision_ajustada: pd.Timestamp,
    fecha_nacimiento,
    ecbp: float = 0,
) -> DatosAuxiliares:
    """
    Calcula el conjunto de variables auxiliares para una persona (causante o
    beneficiario), replica el bloque "Contingencia" de la hoja EncontrarMesada
    (y la funcion datos_auxiliar de Funcion_datos_auxiliares.R).

    ecbp: "Edad Cumplida Beneficiario Padres" (o similar), solo se usa para
    tipo_beneficiario = CONYUGE_TEMPORAL. En el proyecto R siempre se llama
    con ECBP=0, por eso es el valor por defecto aqui.
    """
    sexo_ajustado = 2 if (sexo == 0 or sexo is None) else sexo
    combinacion = sexo_ajustado * 10 + estado
    auxiliar = {11: 1, 21: 2, 12: 3, 22: 4}.get(combinacion, 0)

    anio_factores_mejora = 2022 if auxiliar < 3 else 1985

    # Edad mensual: replica el neto de Funcion_datos_auxiliares.R +
    # Funcion_Calcula_Reserva.R del proyecto en R. Alli, antes de llamar a
    # datos_auxiliar() se le resta 1 mes a Fecha_emisi_poliza
    # (Fecha_emisi_poliza %m-% months(1)), y dentro de datos_auxiliar() se
    # le vuelve a sumar 1 mes solo para el componente de AÑO
    # (Edad_anual <- year(Fecha_emisi_poliza %m+% months(1)) - ...), pero
    # el componente de MES usa Fecha_calculo_reserva SIN ese desplazamiento
    # (s <- month(Fecha_calculo_reserva) - ...). Como en este proyecto
    # Fecha_emisi_poliza y Fecha_calculo_reserva son la misma fecha
    # (fecha_valoracion), el -1 y el +1 se cancelan exactamente: el
    # resultado neto es la edad en meses completos calculada directamente
    # sobre fecha_valoracion, sin ningun corrimiento de mes.
    fecha_ref = pd.Timestamp(fecha_emision_ajustada)
    fecha_nac = pd.Timestamp(fecha_nacimiento)

    edad_anual = fecha_ref.year - fecha_nac.year
    s = fecha_ref.month - fecha_nac.month
    edad_mensual = edad_anual * 12 + s

    if tipo_beneficiario == config.COD_HIJO:
        auxiliar_2 = 0 if estado == config.ESTADO_VALIDO else 1
    else:
        auxiliar_2 = 1

    if estado == config.ESTADO_MUERTO:
        dura_y = 0
    elif tipo_beneficiario == config.COD_CONYUGE_TEMPORAL:
        dura_y = ecbp + 240 - edad_mensual
    elif tipo_beneficiario == config.COD_HIJO:
        # Funcion_datos_auxiliares.R: hijo invalido -> 1331 - Edad_mensual
        # (sin acotar en 0); hijo valido -> max((300 - Edad_mensual) - 1, 0).
        dura_y = (1331 - edad_mensual) if estado == config.ESTADO_INVALIDO else max((300 - edad_mensual) - 1, 0)
    else:
        dura_y = max(config.DURA_Y_LIMITE - edad_mensual, 0)

    return DatosAuxiliares(
        auxiliar=auxiliar,
        anio_factores_mejora=anio_factores_mejora,
        edad_mensual=int(edad_mensual),
        auxiliar_2=auxiliar_2,
        dura_y=int(dura_y),
    )


@lru_cache(maxsize=1)
def _cargar_tabla_mortalidad_csv() -> pd.DataFrame:
    return pd.read_csv(config.RUTA_TABLA_MORTALIDAD)


def cargar_tabla_mortalidad() -> pd.DataFrame:
    """Tabla de mortalidad (edad 0-122) con columnas RV_Masculino, RV_Femenino,
    RI_Masculino, RI_Femenino, FM_M_Valido, FM_F_Valido, FM_M_Invalido, FM_F_Invalido."""
    return _cargar_tabla_mortalidad_csv().copy()


_COL_QX = {1: "RV_Masculino", 2: "RV_Femenino", 3: "RI_Masculino", 4: "RI_Femenino"}
_COL_RX = {1: "FM_M_Valido", 2: "FM_F_Valido", 3: "FM_M_Invalido", 4: "FM_F_Invalido"}


def generar_tabla_mortalidad_mensualizada(
    fecha_emision_ajustada: pd.Timestamp,
    edad_mensual: int,
    dura_y: int,
    estado: int,
    auxiliar: int,
    auxiliar_2: int,
    anio_factores_mejora: int,
    factor_aplicabilidad: float,
    fechas_fin_mes: pd.DatetimeIndex,
    sin_factores_mejora: bool = False,
) -> pd.DataFrame:
    """Tabla mensualizada de mortalidad y supervivencia (nPx), una fila por mes proyectado.

    sin_factores_mejora=True: no aplica la mejora de longevidad
    (1-rx)^años -- usa la tabla de mortalidad cruda (qx * factor de
    aplicabilidad), tal como pide Retiro Programado."""
    n_meses = config.N_MESES
    n_filas_tabla = config.FILAS_TABLA_MORTALIDAD

    tabla = cargar_tabla_mortalidad()
    if auxiliar != 0:
        q_x_anual = tabla[_COL_QX[auxiliar]].to_numpy(dtype=float)[:n_filas_tabla] * factor_aplicabilidad
        r_x_anual = tabla[_COL_RX[auxiliar]].to_numpy(dtype=float)[:n_filas_tabla]
    else:
        q_x_anual = np.zeros(n_filas_tabla)
        r_x_anual = np.zeros(n_filas_tabla)

    edad_meses = edad_mensual + np.arange(n_meses)
    edad_exacta = edad_meses / 12
    edad_entera = np.floor(edad_exacta).astype(int)
    fraccion_edad = edad_exacta - edad_entera
    t_meses_transcurridos = np.arange(1, n_meses + 1)

    vigencia = np.where(t_meses_transcurridos > dura_y, 0, 1)
    edad_entera_acotada = np.clip(edad_entera, 0, n_filas_tabla - 1)

    if estado != config.ESTADO_MUERTO:
        limite_tabla = edad_meses >= config.LIMITE_QX_MEJORADA_EDAD_MESES
        qx_base = q_x_anual[edad_entera_acotada]
        if sin_factores_mejora:
            qx_mejorada = np.where(limite_tabla, 1.0, qx_base)
        else:
            anio_dia_siguiente = (fechas_fin_mes + pd.Timedelta(days=1)).year
            anios_mejora = np.minimum(30, anio_dia_siguiente - anio_factores_mejora)
            rx_base = r_x_anual[edad_entera_acotada]
            qx_mejorada = np.where(limite_tabla, 1.0, qx_base * (1 - rx_base) ** anios_mejora)
    else:
        qx_mejorada = np.zeros(n_meses)

    limite_qx_t = edad_meses >= config.LIMITE_QX_T_EDAD_MESES
    with np.errstate(divide="ignore", invalid="ignore"):
        qx_t = np.where(limite_qx_t, 1.0, (qx_mejorada / 12) / (1 - fraccion_edad * qx_mejorada))

    n_px = np.ones(n_meses)
    if estado != config.ESTADO_MUERTO:
        # A partir de t=dura_y (indice 0-based i=dura_y), vigencia[i]=0
        # SIEMPRE, lo que fuerza n_px[i]=0 sin importar el resto -- no hace
        # falta seguir calculando la recursion mes a mes despues de ese
        # punto, se puede llenar directo con ceros. dura_y suele ser mucho
        # menor que n_meses (1439), asi que esto recorta el bucle
        # significativamente en la mayoria de los casos (es el bucle mas
        # caro de toda la funcion, por ser una recurrencia secuencial que
        # no se puede vectorizar directamente).
        limite_iter = min(dura_y, n_meses)
        for i in range(1, limite_iter):
            base = n_px[i - 1] * (1 - qx_t[i - 1]) if edad_meses[i] < config.LIMITE_NPX_EDAD_MESES else 0.0
            factor_aux2 = 1.0
            if auxiliar_2 == 0 and edad_meses[i] > 300:
                factor_aux2 = 0.0
            n_px[i] = base * factor_aux2 * vigencia[i]
        if limite_iter < n_meses:
            n_px[limite_iter:] = 0.0
    else:
        n_px = np.zeros(n_meses)

    return pd.DataFrame(
        {
            "t": t_meses_transcurridos,
            "Qx_t": qx_t,
            "nPx": n_px,
        }
    )
