"""
Motor de calculo actuarial: replica exactamente la hoja EncontrarMesada /
EncontarTasaEquivalente del Excel de nota tecnica.

f(M) = KA - Reserva_Matematica(M)      (EncontrarMesada)
f(r) = Capital_Acumulado - Prima(r)    (EncontarTasaEquivalente, paso 1)
f(M) = Capital_Acumulado - Prima(M)    (EncontarTasaEquivalente, paso 2)

Se usa este motor junto con core.metodos_numericos para encontrar la mesada
(M) o la tasa (r) que hacen cero la funcion objetivo correspondiente.
"""

from dataclasses import dataclass, field, replace
from datetime import date
from typing import List, Optional

import numpy as np
import pandas as pd

from . import config
from .mortalidad import DatosAuxiliares, datos_auxiliar, generar_tabla_mortalidad_mensualizada


@dataclass
class Persona:
    fecha_nacimiento: date
    tipo_beneficiario: int
    sexo: int
    estado: int


@dataclass
class DatosPoliza:
    id_pol: str
    n_mesadas: int
    fecha_valoracion: date
    smlv: float
    mesada_actual: float
    tasa_interes_real: float
    causante: Persona
    beneficiarios: List[Persona] = field(default_factory=list)
    # Curva MTM/TMR (opcional): lista de hasta 120 tasas anuales (nodos 1..120).
    # Si se define, se usa en lugar de tasa_interes_real para el descuento
    # (equivalente a pegar la curva en EG27:EG146 de EncontarTasaEquivalente).
    curva_tasa: Optional[List[float]] = None
    # Retiro Programado: usar la tabla de mortalidad SIN factores de mejora
    # de longevidad (en vez de la version con mejora usada por EncontrarMesada
    # y Encontrar Tasa Equivalente).
    sin_factores_mejora: bool = False
    # Retiro Programado: % de sobrecosto de mortalidad (de
    # sobrecosto_mortalidad_RP.xlsx, segun edad/sexo del causante) y % de
    # Gastos RP, aplicados cada uno como un recargo independiente sobre la
    # misma base de reserva (igual formula que gastos_reserva/gastos_prima).
    # Si son None, no se aplican (comportamiento normal de EncontrarMesada).
    porcentaje_sobrecosto_mortalidad: Optional[float] = None
    porcentaje_gastos_rp: Optional[float] = None
    # Retiro Programado: mesada actual/base RP de la cedula (columna
    # "Mesada_Actual_RP" de la base), usada UNICAMENTE para decidir que
    # Deslizamiento RP aplica (alto si esta mesada es exactamente igual al
    # SMLV, bajo en caso contrario) -- mismo criterio que ya usa Renta
    # Vitalicia (datos.mesada_actual == datos.smlv) para decidir si el
    # crecimiento de la mesada incluye deslizamiento o no. Si es None, se
    # usa el Deslizamiento RP "alto" (comportamiento anterior, sin esta
    # distincion).
    mesada_actual_rp: Optional[float] = None
    # Retiro Programado: si es True, se aplica params.factor_ajuste_ni
    # (multiplicador sobre la Reserva Matematica RP) en la busqueda de la
    # mesada -- corrige un factor no documentado por la actuaria que solo
    # aplica cuando la mesada de RV coincide con Mesada_Actual_RP de la
    # base (ver core/retiro_programado.py, seteado por el codigo que
    # arma DatosPoliza para RP, no por el usuario directamente).
    aplicar_factor_ajuste_ni: bool = False


@dataclass
class ResultadoReserva:
    id_pol: str
    reserva_amparo_basico: float
    reserva_amparo_basico_cambio_grupo: float
    auxilio_funerario: float
    recargo_gastos_reserva: float
    reserva_matematica: float
    recargo_gastos_prima: float
    prima: float
    duracion_macaulay: float = 0.0
    # Retiro Programado (0.0 si no aplica, ver DatosPoliza.porcentaje_*)
    recargo_sobrecosto_mortalidad: float = 0.0
    recargo_gastos_rp: float = 0.0
    reserva_matematica_rp: float = 0.0
    duracion_macaulay_rp: float = 0.0
    # Derivadas laterales exactas de la Reserva Matematica respecto de la
    # mesada inicial M (solo se llenan si se pide calcular_derivada=True).
    # Existen porque VP(M) es lineal por tramos: en los puntos de quiebre
    # las derivadas por izquierda y por derecha diferen, y el par
    # [izq, der] es exactamente el subdiferencial de Clarke cuando el
    # tramo es convexo, y el B-subdiferencial de Qi en general.
    derivada_rm_der: float = 0.0
    derivada_rm_izq: float = 0.0
    derivada_rm_rp_der: float = 0.0
    derivada_rm_rp_izq: float = 0.0
    # Numero de terminos activos (indice del tramo lineal en que cae M)
    terminos_activos_renta: int = 0
    terminos_activos_auf: int = 0
    flujos: Optional[pd.DataFrame] = None
    # Componentes crudos de la proyeccion de flujos (arreglos numpy de
    # N_MESES posiciones). SIEMPRE se guardan: son los mismos arreglos que
    # calcular_reserva ya calculo para llegar a la reserva, asi que
    # conservarlos no cuesta computo adicional, solo mantener viva la
    # referencia (~130 KB por resultado).
    #
    # Existen para que NO haya que volver a correr el motor solo para
    # obtener la proyeccion de flujos: quien haya llamado a calcular_reserva
    # (tipicamente dentro de la funcion objetivo de un metodo de iteracion)
    # puede pedir el DataFrame despues, con construir_flujos(), sin repetir
    # los 1.439 meses de calculo. Ver
    # core/base_masiva.py::_resolver_mesada_con_flujos.
    componentes_flujos: Optional[dict] = None

    def construir_flujos(self) -> Optional[pd.DataFrame]:
        """
        Devuelve el DataFrame de flujos proyectados, armandolo la primera
        vez a partir de `componentes_flujos` y cacheandolo en `flujos`.

        No recalcula nada del motor actuarial: los arreglos ya venian
        computados desde la llamada original a calcular_reserva. Lo unico
        que ocurre aqui es el ensamblado del DataFrame.
        """
        if self.flujos is not None:
            return self.flujos
        if self.componentes_flujos is None:
            return None
        self.flujos = pd.DataFrame(self.componentes_flujos)
        return self.flujos


def _generar_calendario(fecha_valoracion: date, n_meses: int) -> pd.DatetimeIndex:
    """
    Primer mes = fin de mes de fecha_valoracion; sucesivos, fin de mes
    siguiente.

    Construido con aritmetica de numpy (datetime64), no con
    period_range/date_range de pandas: estas ultimas dos, al pedirles fin
    de mes (freq="M"/"ME"), terminan invocando la inferencia de frecuencia
    de pandas (infer_freq/month_position_check) -- codigo pensado para
    ADIVINAR la frecuencia de una serie de fechas arbitraria, carisimo, e
    innecesario aqui porque la frecuencia ya se conoce (mensual, fin de
    mes). Esta version es ~20x mas rapida para la misma salida (verificado
    con fechas identicas mes a mes), y es el cuello de botella principal
    de la proyeccion dinamica de Retiro Programado (se llama 2 veces por
    cada evaluacion de la reserva, y esa evaluacion se repite decenas de
    veces por cedula en la busqueda de la mesada de cada año).
    """
    primer_mes = pd.Timestamp(fecha_valoracion) + pd.offsets.MonthEnd(0)
    base_mes = np.datetime64(primer_mes.date().replace(day=1), "M")
    meses = base_mes + np.arange(n_meses)
    fin_de_mes = (meses + 1).astype("datetime64[D]") - 1
    return pd.DatetimeIndex(fin_de_mes)


def _factor_ipc_acumulado(anios_transcurridos: np.ndarray, params: "config.ParametrosActuariales", con_deslizamiento: bool) -> np.ndarray:
    """
    Replica las formulas de las columnas I (inflacion) / J (salario minimo) de
    EncontrarMesada:
        n=0            -> 1
        n=1            -> F
        n=2            -> F*S
        n>=3           -> F*S*T^(n-2)
    donde F,S,T son 1+tasa del año 1, 2 y objetivo largo plazo (mas
    deslizamiento si con_deslizamiento=True).
    """
    desliz = params.delta_deslizamiento if con_deslizamiento else 0.0
    f_year1 = 1 + params.ipc_primer_anio + desliz
    f_year2 = 1 + params.ipc_segundo_anio + desliz
    f_year3 = 1 + params.ipc_objetivo_largo_plazo + desliz

    n = anios_transcurridos
    factor = np.ones_like(n, dtype=float)
    factor = np.where(n == 1, f_year1, factor)
    factor = np.where(n == 2, f_year1 * f_year2, factor)
    factor = np.where(n >= 3, f_year1 * f_year2 * (f_year3 ** np.maximum(n - 2, 0)), factor)
    return factor


def _tasas_forward_mensuales(
    tasa_o_curva,
    fechas: pd.DatetimeIndex,
    fecha_valoracion: pd.Timestamp,
    params: "config.ParametrosActuariales",
) -> np.ndarray:
    """
    Replica las columnas ER (Interes Nominal / spot), EU (Conversion a
    Forward), EV (Tasas Forward mensuales), FF (IPC mensual) y U (tasa
    nominal mensual = (1+FF)*(1+EV)-1) de la hoja EncontarTasaEquivalente
    (identico a EU/FE/U de EncontrarMesada cuando la tasa es plana).

    tasa_o_curva puede ser:
    - un float: tasa real plana (equivalente a EG27:EGxxx = "=C14").
    - una lista/array de hasta 120 tasas anuales (un nodo por año 1..120,
      equivalente a pegar la curva en EG27:EG146). Para cada mes t se toma
      el nodo mas cercano por año (redondeo Excel, sin interpolar entre
      nodos), igual que el VLOOKUP de coincidencia exacta de las columnas
      EO/EP de la hoja.
    """
    n_meses = len(fechas)
    t_meses = np.arange(1, n_meses + 1)

    if np.isscalar(tasa_o_curva):
        er = np.full(n_meses, float(tasa_o_curva))
    else:
        curva = np.asarray(tasa_o_curva, dtype=float)
        anio_fraccion = t_meses / 12
        nodo = np.floor(anio_fraccion + 0.5).astype(int)  # redondeo Excel (half-up)
        nodo = np.where(nodo == 0, 1, nodo)
        nodo = np.clip(nodo, 1, len(curva))
        er = curva[nodo - 1]

    # EU: conversion de spot (ER) a forward, telescopica sobre EK=t (mes).
    eu = np.empty(n_meses)
    eu[0] = er[0]
    with np.errstate(divide="ignore", invalid="ignore"):
        eu[1:] = (1 + er[1:]) ** t_meses[1:] / (1 + er[:-1]) ** t_meses[:-1] - 1
    ev = (1 + eu) ** (1 / 12) - 1  # tasa forward mensual real

    anio_valoracion = fecha_valoracion.year
    diff_anios = fechas.year.to_numpy() - anio_valoracion
    meses_calendario = fechas.month.to_numpy()

    vector_mensual = np.array(params.vector_ipc_primer_anio, dtype=float)
    ipc_mensual_anio2 = (1 + params.ipc_segundo_anio) ** (1 / 12) - 1
    ipc_mensual_largo_plazo = (1 + params.ipc_objetivo_largo_plazo) ** (1 / 12) - 1

    ff = np.where(
        diff_anios == 0,
        vector_mensual[meses_calendario - 1],
        np.where(diff_anios == 1, ipc_mensual_anio2, ipc_mensual_largo_plazo),
    )

    return (1 + ff) * (1 + ev) - 1


def _tabla_pagos(n_mesadas: int) -> pd.Series:
    """CP_n: numero de mesadas pagadas por mes calendario (columnas EY:EZ)."""
    meses_numeros = list(range(1, 12)) + [0]
    cp_n = np.ones(12, dtype=int)
    cp_n[10] = 2  # noviembre: mesada normal + adicional de fin de año
    if n_mesadas == 13:
        cp_n[5] = 1
    elif n_mesadas == 14:
        cp_n[5] = 2  # junio: mesada adicional de mitad de año
    else:
        cp_n[5] = 1
    return pd.Series(cp_n, index=meses_numeros)


def _tabla_persona(persona: Persona, fecha_valoracion: pd.Timestamp, es_causante: bool, sin_factores_mejora: bool = False):
    tipo = persona.tipo_beneficiario
    if tipo is None or tipo <= 0 or persona.sexo <= 0 or persona.estado <= 0:
        return None, None

    factor_aplicabilidad = (0.7 if persona.estado < config.ESTADO_INVALIDO else 1.0) if es_causante \
        else (0.95 if persona.estado < config.ESTADO_INVALIDO else 1.0)

    aux = datos_auxiliar(
        sexo=persona.sexo,
        estado=persona.estado,
        tipo_beneficiario=tipo,
        fecha_emision_ajustada=fecha_valoracion,
        fecha_nacimiento=persona.fecha_nacimiento,
    )
    # Funcion_Calcula_Reserva.R le suma 1 a DURA_y para cada beneficiario
    # (b1..b9), pero no para el causante -- se replica aqui, fuera de
    # datos_auxiliar(), que es donde el R original lo hace tambien (a nivel
    # de la funcion que arma los flujos, no dentro de datos_auxiliar()).
    dura_y = aux.dura_y if es_causante else aux.dura_y + 1

    fechas = _generar_calendario(fecha_valoracion, config.N_MESES)
    tabla = generar_tabla_mortalidad_mensualizada(
        fecha_emision_ajustada=fecha_valoracion,
        edad_mensual=aux.edad_mensual,
        dura_y=dura_y,
        estado=persona.estado,
        auxiliar=aux.auxiliar,
        auxiliar_2=aux.auxiliar_2,
        anio_factores_mejora=aux.anio_factores_mejora,
        factor_aplicabilidad=factor_aplicabilidad,
        fechas_fin_mes=fechas,
        sin_factores_mejora=sin_factores_mejora,
    )
    return tabla, aux


def calcular_reserva(datos: DatosPoliza, params: "config.ParametrosActuariales", generar_flujos: bool = False, calcular_derivada: bool = False) -> ResultadoReserva:
    n_meses = config.N_MESES
    fecha_valoracion = pd.Timestamp(datos.fecha_valoracion) + pd.offsets.MonthEnd(0)
    fechas = _generar_calendario(fecha_valoracion, n_meses)

    tabla_causante, _ = _tabla_persona(datos.causante, fecha_valoracion, es_causante=True, sin_factores_mejora=datos.sin_factores_mejora)
    tablas_beneficiarios = []
    for b in datos.beneficiarios:
        tabla_b, _ = _tabla_persona(b, fecha_valoracion, es_causante=False, sin_factores_mejora=datos.sin_factores_mejora)
        if tabla_b is not None:
            tablas_beneficiarios.append(tabla_b)

    tablas_validas = ([tabla_causante] if tabla_causante is not None else []) + tablas_beneficiarios
    if tablas_validas:
        complementos = np.array([1 - t["nPx"].to_numpy() for t in tablas_validas])
        npx_conjunta = 1 - np.prod(complementos, axis=0)
    else:
        npx_conjunta = np.ones(n_meses)

    tasas_forward = _tasas_forward_mensuales(
        datos.curva_tasa if datos.curva_tasa else datos.tasa_interes_real,
        fechas, fecha_valoracion, params,
    )

    # --- Crecimiento de mesada (columnas C a M) ---
    t_meses = np.arange(1, n_meses + 1)
    vigencia_general = np.where(t_meses >= config.VIGENCIA_CORTE_T, 0, 1)
    anios_transcurridos = fechas.year.to_numpy() - fecha_valoracion.year

    factor_ipc = _factor_ipc_acumulado(anios_transcurridos, params, con_deslizamiento=False)
    factor_salario_min = _factor_ipc_acumulado(anios_transcurridos, params, con_deslizamiento=True)

    salario_minimo_proyectado = datos.smlv * factor_salario_min  # columna K
    if datos.mesada_actual == datos.smlv:
        tasa_aplicar = factor_salario_min
    else:
        tasa_aplicar = factor_ipc
    mesada_mensual_uncapped = np.maximum(datos.mesada_actual * tasa_aplicar, salario_minimo_proyectado)  # columna L
    mesada_con_vigencia = mesada_mensual_uncapped * vigencia_general  # columna M

    # --- Contingencia y descuento (columnas O a W) ---
    cp_n = _tabla_pagos(datos.n_mesadas)
    meses_mod_12 = fechas.month % 12
    numero_mesadas = meses_mod_12.map(cp_n).to_numpy(dtype=float)  # columna O

    total_mesada_mensual = mesada_con_vigencia * numero_mesadas  # columna P (=R, Q=1)

    npx_lead = np.append(npx_conjunta[1:], np.nan)  # columna S
    flujos_renta_supervivencia = total_mesada_mensual * npx_lead  # columna T

    descuento_tecnico = np.ones(n_meses)
    for i in range(1, n_meses):
        descuento_tecnico[i] = descuento_tecnico[i - 1] / (1 + tasas_forward[i - 1])
    descuento_tecnico_lead = np.append(descuento_tecnico[1:], np.nan)  # columna V

    flujos_descontados = flujos_renta_supervivencia * descuento_tecnico_lead  # columna W
    flujos_descontados = np.nan_to_num(flujos_descontados, nan=0.0)
    reserva_amparo_basico = float(np.sum(flujos_descontados))

    # --- Auxilio funerario (columnas Y a AG), usa L (sin vigencia) ---
    auxilio_funerario = 0.0
    if datos.causante.estado != config.ESTADO_MUERTO and tabla_causante is not None:
        auxilio = np.where(
            mesada_mensual_uncapped <= 5 * salario_minimo_proyectado, 5 * salario_minimo_proyectado,
            np.where(mesada_mensual_uncapped <= 10 * salario_minimo_proyectado, mesada_mensual_uncapped, 10 * salario_minimo_proyectado),
        )
        auxilio_por_vigencia = auxilio * vigencia_general  # AB (Q general, no dura_y)

        qx_t_causante = tabla_causante["Qx_t"].to_numpy()
        npx_causante = tabla_causante["nPx"].to_numpy()

        flujo_auf_sin_descuento = auxilio_por_vigencia * qx_t_causante * npx_causante
        flujo_auf_sin_descuento = np.nan_to_num(flujo_auf_sin_descuento, nan=0.0)

        flujo_auf = flujo_auf_sin_descuento * descuento_tecnico_lead
        flujo_auf = np.nan_to_num(flujo_auf, nan=0.0)
        auxilio_funerario = float(np.sum(flujo_auf))
    else:
        flujo_auf_sin_descuento = np.zeros(n_meses)
        qx_t_causante = np.zeros(n_meses)
        npx_causante = np.zeros(n_meses)

    reserva_cambio_grupo = params.porcentaje_reserva_cambio_grupo * reserva_amparo_basico
    base_reserva = reserva_amparo_basico + reserva_cambio_grupo + auxilio_funerario
    recargo_gastos_reserva = ((1 / (1 - params.porcentaje_recargo_gastos_reserva)) - 1) * base_reserva
    reserva_matematica = base_reserva + recargo_gastos_reserva
    recargo_gastos_prima = ((1 / (1 - params.porcentaje_recargo_gastos_prima)) - 1) * base_reserva
    prima = base_reserva + recargo_gastos_prima

    # --- Retiro Programado: sobrecosto de mortalidad + gastos RP, cada uno
    # como un recargo independiente sobre la misma base_reserva (misma
    # formula que gastos_reserva/gastos_prima), sumados a base_reserva.
    recargo_sobrecosto_mortalidad = 0.0
    recargo_gastos_rp = 0.0
    reserva_matematica_rp = 0.0
    if datos.porcentaje_sobrecosto_mortalidad is not None or datos.porcentaje_gastos_rp is not None:
        pct_sobrecosto = datos.porcentaje_sobrecosto_mortalidad or 0.0
        pct_gastos_rp = datos.porcentaje_gastos_rp or 0.0
        recargo_sobrecosto_mortalidad = ((1 / (1 - pct_sobrecosto)) - 1) * base_reserva
        recargo_gastos_rp = ((1 / (1 - pct_gastos_rp)) - 1) * base_reserva
        reserva_matematica_rp = base_reserva + recargo_sobrecosto_mortalidad + recargo_gastos_rp

    # --- Duracion Macaulay (Funcion_Calcula_Reserva.R, linea 776) ---
    # Usa flujos SIN el descuento tecnico mes a mes (T=Flujos_Renta_Supervivencia
    # y el Flujo_AUF sin descontar), grosseados por el recargo de gastos de
    # reserva, y los descuenta con una tasa PLANA anualizada
    # ((1+IPC_primer_año)*(1+tasa_real))^(-t_años) -- distinta del descuento
    # tecnico mensual exacto que usa la Reserva Matematica; es una
    # convencion propia del calculo de duracion, no del valor de la reserva.
    frs_sin_nan = np.nan_to_num(flujos_renta_supervivencia, nan=0.0)
    reserva_cambio_grupo_por_periodo = frs_sin_nan * params.porcentaje_reserva_cambio_grupo
    total_pol = (frs_sin_nan + reserva_cambio_grupo_por_periodo + flujo_auf_sin_descuento) / (
        1 - params.porcentaje_recargo_gastos_reserva
    )
    ipc_duracion = params.ipc_primer_anio
    descuento_duracion = 1 / ((1 + ipc_duracion) * (1 + datos.tasa_interes_real)) ** (t_meses / 12)
    duracion_por_periodo = t_meses * total_pol * descuento_duracion / 12
    duracion_macaulay = float(np.sum(duracion_por_periodo) / reserva_matematica) if reserva_matematica else 0.0

    duracion_macaulay_rp = 0.0
    if reserva_matematica_rp:
        pct_gastos_rp = datos.porcentaje_gastos_rp or 0.0
        total_pol_rp = (frs_sin_nan + reserva_cambio_grupo_por_periodo + flujo_auf_sin_descuento) / (
            1 - pct_gastos_rp
        )
        duracion_por_periodo_rp = t_meses * total_pol_rp * descuento_duracion / 12
        duracion_macaulay_rp = float(np.sum(duracion_por_periodo_rp) / reserva_matematica_rp)

    # --- Derivadas laterales exactas de la Reserva Matematica (opcional) ---
    #
    # VP(M) es lineal por tramos en M. Sus dos sumandos dependientes de M son
    #
    #   renta:   max(M*tau_t, S_t)            (maximo -> convexo)
    #   auxilio: med(5*S_t, M*tau_t, 10*S_t)  (clamp  -> NO convexo)
    #
    # con tau_t = tasa_aplicar[t] y S_t = salario_minimo_proyectado[t]. Las
    # derivadas laterales se obtienen sumando tau_t sobre los terminos
    # ACTIVOS, con el criterio de desigualdad estricta/no estricta que
    # corresponde a cada lado. El par (izq, der) es el B-subdiferencial de
    # Qi; su envolvente convexa es el subdiferencial de Clarke.
    derivada_rm_der = derivada_rm_izq = 0.0
    derivada_rm_rp_der = derivada_rm_rp_izq = 0.0
    n_activos_renta = n_activos_auf = 0
    if calcular_derivada:
        # HALLAZGO DOCUMENTADO EN LA TESIS (cap. de estructura funcional):
        # el motor elige `tasa_aplicar` por una distincion de casos
        # (M == SMLV -> factor con deslizamiento; M != SMLV -> factor IPC).
        # El VALOR de VP es continuo en M = SMLV (el piso del salario minimo
        # absorbe la diferencia), pero la FORMULA de la derivada no lo es:
        # evaluada literalmente en M = SMLV devolveria la pendiente de la
        # rama con deslizamiento, cuando la derivada lateral derecha
        # verdadera (limite cuando eps -> 0+) se calcula sobre la rama IPC.
        # Se usa la rama IPC para la derivada en ese punto, que es la que
        # corresponde al limite; la derivada por izquierda es 0 porque VP
        # es constante en [0, SMLV].
        tasa_derivada = factor_ipc if datos.mesada_actual == datos.smlv else tasa_aplicar
        m_tau = datos.mesada_actual * tasa_derivada
        peso_renta = tasa_derivada * vigencia_general * numero_mesadas * np.nan_to_num(npx_lead, nan=0.0) * np.nan_to_num(descuento_tecnico_lead, nan=0.0)

        activo_renta_der = m_tau >= salario_minimo_proyectado
        activo_renta_izq = m_tau > salario_minimo_proyectado
        d_rab_der = float(np.sum(np.where(activo_renta_der, peso_renta, 0.0)))
        d_rab_izq = float(np.sum(np.where(activo_renta_izq, peso_renta, 0.0)))
        n_activos_renta = int(np.count_nonzero(activo_renta_der & (vigencia_general > 0)))

        d_auf_der = d_auf_izq = 0.0
        if datos.causante.estado != config.ESTADO_MUERTO and tabla_causante is not None:
            peso_auf = tasa_derivada * vigencia_general * np.nan_to_num(qx_t_causante, nan=0.0) * np.nan_to_num(npx_causante, nan=0.0) * np.nan_to_num(descuento_tecnico_lead, nan=0.0)
            banda_der = (m_tau >= 5 * salario_minimo_proyectado) & (m_tau < 10 * salario_minimo_proyectado)
            banda_izq = (m_tau > 5 * salario_minimo_proyectado) & (m_tau <= 10 * salario_minimo_proyectado)
            d_auf_der = float(np.sum(np.where(banda_der, peso_auf, 0.0)))
            d_auf_izq = float(np.sum(np.where(banda_izq, peso_auf, 0.0)))
            n_activos_auf = int(np.count_nonzero(banda_der & (vigencia_general > 0)))

        d_base_der = (1 + params.porcentaje_reserva_cambio_grupo) * d_rab_der + d_auf_der
        d_base_izq = (1 + params.porcentaje_reserva_cambio_grupo) * d_rab_izq + d_auf_izq

        escala_rm = 1.0 / (1 - params.porcentaje_recargo_gastos_reserva)
        derivada_rm_der = d_base_der * escala_rm
        derivada_rm_izq = d_base_izq * escala_rm

        if datos.porcentaje_sobrecosto_mortalidad is not None or datos.porcentaje_gastos_rp is not None:
            pct_s = datos.porcentaje_sobrecosto_mortalidad or 0.0
            pct_g = datos.porcentaje_gastos_rp or 0.0
            escala_rp = 1.0 / (1 - pct_s) + 1.0 / (1 - pct_g) - 1.0
            derivada_rm_rp_der = d_base_der * escala_rp
            derivada_rm_rp_izq = d_base_izq * escala_rp

    # Los componentes de la proyeccion de flujos se guardan SIEMPRE (son
    # los arreglos que ya se calcularon arriba; guardarlos es solo mantener
    # la referencia). El DataFrame en si se arma solo si se pide de una vez
    # con generar_flujos=True; si no, queda disponible bajo demanda via
    # ResultadoReserva.construir_flujos(), sin repetir el calculo.
    componentes = {
        "Fecha": fechas,
        "t": t_meses,
        "Mesada_Pensional_proyectada": mesada_con_vigencia,
        "Total_mesada_mensual_proyectada": total_mesada_mensual,
        "nPx": npx_lead,
        "Flujos_Renta_Supervivencia": flujos_renta_supervivencia,
        "Descuento_tecnico": descuento_tecnico_lead,
        "Flujos_Renta_Supervivencia_descontados": flujos_descontados,
    }
    flujos_df = pd.DataFrame(componentes) if generar_flujos else None

    return ResultadoReserva(
        id_pol=datos.id_pol,
        reserva_amparo_basico=reserva_amparo_basico,
        reserva_amparo_basico_cambio_grupo=reserva_cambio_grupo,
        auxilio_funerario=auxilio_funerario,
        recargo_gastos_reserva=recargo_gastos_reserva,
        reserva_matematica=reserva_matematica,
        recargo_gastos_prima=recargo_gastos_prima,
        prima=prima,
        duracion_macaulay=duracion_macaulay,
        recargo_sobrecosto_mortalidad=recargo_sobrecosto_mortalidad,
        recargo_gastos_rp=recargo_gastos_rp,
        reserva_matematica_rp=reserva_matematica_rp,
        duracion_macaulay_rp=duracion_macaulay_rp,
        derivada_rm_der=derivada_rm_der,
        derivada_rm_izq=derivada_rm_izq,
        derivada_rm_rp_der=derivada_rm_rp_der,
        derivada_rm_rp_izq=derivada_rm_rp_izq,
        terminos_activos_renta=n_activos_renta,
        terminos_activos_auf=n_activos_auf,
        flujos=flujos_df,
        componentes_flujos=componentes,
    )
