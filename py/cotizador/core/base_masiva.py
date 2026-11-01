"""
Carga y procesamiento masivo de la base de calculo (cedulas).

Espera un archivo con la misma estructura de columnas que
base_polizas_10_polizas.xlsx: id_cotizacion, id_0 (cedula del causante,
usada para identificar cada registro en la pagina), mesada, no_mesada,
capital_renta, it_emision, fecha_inicio_vigencia,
fecha_nacimiento_0/cod_genero_0/cod_estado_0/parentesco_0 (causante),
fecha_nacimiento_N/cod_genero_N/cod_estado_N/parentesco_N (beneficiarios 1-9).
"""

VERSION_ESQUEMA_BASE = "id_0_v3_2026-08-04"

from dataclasses import dataclass
from typing import Callable, List, Optional

import pandas as pd

from . import config
from .mapeo_base import (
    MAX_BENEFICIARIOS_BASE,
    cod_estado_a_estado,
    cod_genero_a_sexo,
    parentesco_texto_a_codigo,
)
from .metodos_numericos import biseccion, newton, secante
from .motor import DatosPoliza, Persona, calcular_reserva
from .paralelo import ejecutar_en_paralelo
from .tasa_equivalente import ResultadoTasaEquivalente, resolver_tasa_y_mesada


@dataclass
class ResultadoCedula:
    cedula: str
    id_cotizacion: str
    mesada_inicial: float
    capital_asegurado: float
    mesada_encontrada: float
    reserva_en_mesada_encontrada: float
    duracion_macaulay: float
    convergio: bool
    iteraciones: int
    error: str = ""


def _formatear_cedula(valor) -> str:
    """id_0 llega como numero (float) desde excel; se formatea sin decimales."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return ""
    try:
        return str(int(valor))
    except (ValueError, TypeError):
        return str(valor)


def _parsear_fecha_robusta(valor, nombre_columna: str, id_fila: str):
    """
    Convierte un valor de una columna de fecha a `date`, tolerando el caso
    en que Excel/pandas la haya leido como un NUMERO CRUDO en vez de como
    fecha (celda con formato "General"/"Numero" en vez de "Fecha") -- ese
    numero es un "serial de Excel" (dias desde 1899-12-30), NO nanosegundos
    desde 1970. Si se le pasa directo a pd.Timestamp() sin este ajuste, da
    una fecha ancladas en 1970-01-01 (el epoch de Unix), silenciosamente
    mal -- por eso la proyeccion de mesada aparecia empezando en 1970.

    Si la celda esta genuinamente vacia (NaN), se lanza un error CLARO con
    la cedula y la columna afectada, en vez de dejar pasar una fecha
    invalida en silencio.
    """
    if pd.isna(valor):
        raise ValueError(
            f"La columna '{nombre_columna}' esta vacia para la cedula/poliza "
            f"'{id_fila}' -- revisa esa fila en la base de origen."
        )
    if isinstance(valor, (int, float)):
        # Serial de Excel: dias desde 1899-12-30 (el "dia 0" de Excel).
        # Esto pasa cuando la celda tenia formato "General"/"Numero" en vez
        # de "Fecha" al guardar el archivo.
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(valor))).date()
    return pd.Timestamp(valor).date()


def _fila_a_datos_poliza(fila: pd.Series) -> DatosPoliza:
    id_fila = str(fila.get("id_cotizacion", fila.get("id_0", "?")))
    causante = Persona(
        fecha_nacimiento=_parsear_fecha_robusta(fila["fecha_nacimiento_0"], "fecha_nacimiento_0", id_fila),
        tipo_beneficiario=1,
        sexo=cod_genero_a_sexo(fila.get("cod_genero_0")),
        estado=cod_estado_a_estado(fila.get("cod_estado_0")),
    )

    beneficiarios: List[Persona] = []
    for n in range(1, MAX_BENEFICIARIOS_BASE + 1):
        col_fecha = f"fecha_nacimiento_{n}"
        if col_fecha not in fila.index or pd.isna(fila.get(col_fecha)):
            continue
        tipo = parentesco_texto_a_codigo(fila.get(f"parentesco_{n}"))
        if tipo <= 0:
            continue
        beneficiarios.append(
            Persona(
                fecha_nacimiento=_parsear_fecha_robusta(fila[col_fecha], col_fecha, id_fila),
                tipo_beneficiario=tipo,
                sexo=cod_genero_a_sexo(fila.get(f"cod_genero_{n}")),
                estado=cod_estado_a_estado(fila.get(f"cod_estado_{n}")),
            )
        )

    mesada_actual_rp = None
    if "Mesada_Actual_RP" in fila.index and pd.notna(fila.get("Mesada_Actual_RP")):
        mesada_actual_rp = float(fila["Mesada_Actual_RP"])

    return DatosPoliza(
        id_pol=str(fila["id_cotizacion"]),
        n_mesadas=int(fila["no_mesada"]),
        fecha_valoracion=_parsear_fecha_robusta(fila["fecha_inicio_vigencia"], "fecha_inicio_vigencia", id_fila),
        smlv=0.0,  # se sobreescribe con el SMLV global de Parametrizacion
        mesada_actual=float(fila["mesada"]),
        tasa_interes_real=float(fila.get("it_emision", 0) or 0),  # ya viene en formato decimal (ej 0.0408); no se usa cuando se aplica una curva MTM/TMR
        causante=causante,
        beneficiarios=beneficiarios,
        mesada_actual_rp=mesada_actual_rp,
    )


def proyeccion_anual_desde_flujos(flujos: pd.DataFrame, max_anios: Optional[int] = None) -> pd.DataFrame:
    """
    Agrega un DataFrame de flujos mensuales (el que produce
    motor.calcular_reserva) a la proyeccion ANUAL de la mesada: una fila por
    año, con la mesada maxima de ese año.

    Se separo en su propia funcion para que la agregacion sea EXACTAMENTE la
    misma se llegue por donde se llegue: desde la evaluacion que ya hizo el
    metodo de iteracion (_resolver_mesada_con_flujos) o desde una llamada
    suelta al motor (proyeccion_mesada_por_anio).
    """
    df = flujos.copy()
    df["Anio"] = df["Fecha"].dt.year
    proyeccion = df.groupby("Anio", as_index=False)["Mesada_Pensional_proyectada"].max()
    if max_anios is not None:
        proyeccion = proyeccion.head(max_anios)
    return proyeccion


def _resolver_mesada_con_flujos(
    datos: DatosPoliza,
    params: config.ParametrosActuariales,
    capital_asegurado: float,
) -> tuple:
    """
    Encuentra la mesada de Renta Vitalicia y devuelve
    (resultado_metodo, ResultadoReserva de esa mesada), SIN volver a correr
    el motor actuarial al final.

    Antes se hacia una llamada extra a calcular_reserva() con la mesada ya
    encontrada, para obtener la prima final y la proyeccion de flujos. Esa
    llamada era un duplicado exacto: el metodo de iteracion ACABABA de
    evaluar la funcion objetivo en ese mismo punto (los tres metodos --
    biseccion, secante, Newton -- devuelven un punto que si evaluaron), asi
    que se estaban recorriendo dos veces los 1.439 meses de proyeccion para
    obtener el mismo numero.

    Ahora la funcion objetivo guarda cada ResultadoReserva que produce, y al
    terminar se recupera el que corresponde a la mesada devuelta. Los flujos
    proyectados salen de ahi con ResultadoReserva.construir_flujos(), que
    solo ensambla el DataFrame a partir de arreglos ya calculados.

    El cache se limita a las ultimas evaluaciones (no a todas) porque cada
    ResultadoReserva mantiene vivos ~130 KB de arreglos y biseccion puede
    llegar a cientos de iteraciones. Se guardan varias y no solo la ultima
    porque Newton evalua f(x+h) y f(x-h) para su derivada numerica, de modo
    que la ultima evaluacion no siempre es la del punto devuelto.
    """
    MAX_EVALUACIONES_EN_CACHE = 4
    evaluaciones: "dict[float, ResultadoReserva]" = {}

    def f(mesada_iterada: float) -> float:
        datos_iter = DatosPoliza(**{**datos.__dict__, "mesada_actual": mesada_iterada})
        r = calcular_reserva(datos_iter, params)
        evaluaciones[mesada_iterada] = r
        if len(evaluaciones) > MAX_EVALUACIONES_EN_CACHE:
            evaluaciones.pop(next(iter(evaluaciones)))
        return capital_asegurado - r.prima

    mesada_min = params.smlv
    mesada_max = params.smlv * 25

    class _P:
        epsilon = params.epsilon
        max_iteraciones = params.max_iteraciones
        paso_derivada = params.paso_derivada

    if params.metodo_iteracion == "biseccion":
        res = biseccion(f, mesada_min, mesada_max, _P())
    elif params.metodo_iteracion == "newton":
        res = newton(f, (mesada_min + mesada_max) / 2, _P(), limite_inferior=mesada_min, limite_superior=mesada_max)
    else:
        res = secante(f, mesada_min, mesada_max, _P(), limite_inferior=mesada_min, limite_superior=mesada_max)

    reserva_final = evaluaciones.get(res.valor)
    if reserva_final is None:
        # Respaldo defensivo: si algun metodo llegara a devolver un punto
        # que no evaluo (o que ya salio del cache), se calcula una vez. Con
        # los tres metodos actuales esto no deberia ocurrir.
        reserva_final = calcular_reserva(
            DatosPoliza(**{**datos.__dict__, "mesada_actual": res.valor}), params
        )

    return res, reserva_final


def _procesar_fila_mesada(
    fila: pd.Series,
    params: config.ParametrosActuariales,
    indice: int,
    max_anios_proyeccion: Optional[int] = None,
) -> tuple:
    """
    Procesa UNA fila para Masivo EncontrarMesada. Funcion a nivel de modulo
    (no un closure) para que se pueda enviar a otros procesos via
    core.paralelo.ejecutar_en_paralelo.

    Devuelve (ResultadoCedula, proyeccion_anual), donde proyeccion_anual es
    una lista de tuplas (año, mesada) construida a partir de la MISMA
    evaluacion que uso el metodo de iteracion -- no de una corrida nueva del
    motor. Se devuelve como lista de tuplas (y no como DataFrame) porque
    este resultado viaja entre procesos: son ~20 pares de numeros, contra
    los 1.439 meses del DataFrame completo.
    """
    try:
        datos = _fila_a_datos_poliza(fila)
        datos.smlv = params.smlv
        capital_asegurado = float(fila["capital_renta"])

        res, reserva_final = _resolver_mesada_con_flujos(datos, params, capital_asegurado)

        # Los flujos ya estaban calculados dentro de la iteracion: aqui solo
        # se ensambla el DataFrame y se agrega por año.
        proyeccion_anual: List[tuple] = []
        flujos = reserva_final.construir_flujos()
        if flujos is not None:
            proyeccion = proyeccion_anual_desde_flujos(flujos, max_anios=max_anios_proyeccion)
            proyeccion_anual = [
                (int(r["Anio"]), float(r["Mesada_Pensional_proyectada"]))
                for _, r in proyeccion.iterrows()
            ]

        resultado = ResultadoCedula(
            cedula=_formatear_cedula(fila.get("id_0")),
            id_cotizacion=datos.id_pol,
            mesada_inicial=datos.mesada_actual,
            capital_asegurado=capital_asegurado,
            mesada_encontrada=res.valor,
            reserva_en_mesada_encontrada=reserva_final.prima,
            duracion_macaulay=reserva_final.duracion_macaulay,
            convergio=res.convergio,
            iteraciones=res.iteraciones,
        )
        return resultado, proyeccion_anual
    except Exception as exc:  # noqa: BLE001
        return (
            ResultadoCedula(
                cedula=_formatear_cedula(fila.get("id_0")),
                id_cotizacion=str(fila.get("id_cotizacion", indice)),
                mesada_inicial=float(fila.get("mesada", 0) or 0),
                capital_asegurado=float(fila.get("capital_renta", 0) or 0),
                mesada_encontrada=0.0,
                reserva_en_mesada_encontrada=0.0,
                duracion_macaulay=0.0,
                convergio=False,
                iteraciones=0,
                error=str(exc),
            ),
            [],
        )


def procesar_base(
    base: pd.DataFrame,
    params: config.ParametrosActuariales,
    callback_progreso: Optional[Callable[[int, int], None]] = None,
    devolver_proyecciones: bool = False,
    max_anios_proyeccion: Optional[int] = None,
):
    """
    Encuentra la mesada de cada fila de la base usando el metodo configurado.
    Corre en paralelo usando todos los nucleos del equipo menos 1 (igual que
    plan(multisession, workers=detectCores()-1) del proyecto en R) -- ver
    core/paralelo.py. Si el paralelismo no esta disponible en el entorno,
    hace fallback automatico a ejecucion secuencial.

    Si `devolver_proyecciones` es True, devuelve una tupla
    (resultados, proyecciones_rv) donde proyecciones_rv es un dict
    {indice_de_fila: [(año, mesada), ...]} con la proyeccion anual de Renta
    Vitalicia de cada cedula, obtenida de la MISMA evaluacion que uso el
    metodo de iteracion. Sirve para que la corrida de proyecciones (ver
    core/proyecciones_masivo.py) y el grafico no tengan que volver a correr
    el motor para reconstruir algo que ya se calculo. Si es False (default),
    devuelve solo el DataFrame de resultados, como siempre.

    IMPORTANTE (validado contra Nueva_nota_tecnica_30_jul_2026_econtrar_mesada.xlsm,
    hoja EncontrarMesada): el objetivo usa r.prima (construido con
    params.porcentaje_recargo_gastos_prima), no r.reserva_matematica. En esa
    hoja el unico recargo presente esta etiquetado "Recargo_Gastos_Prima"
    aunque alimenta la celda que la hoja llama "Reserva Matematica" -- ver
    docstring de core/encontrar_mesada_individual.py para el detalle.
    """
    if max_anios_proyeccion is None:
        max_anios_proyeccion = params.max_anios_proyeccion_rp_tope

    argumentos = [
        (fila, params, i, max_anios_proyeccion) for i, (_, fila) in enumerate(base.iterrows())
    ]
    salidas = ejecutar_en_paralelo(_procesar_fila_mesada, argumentos, callback_progreso)

    resultados = pd.DataFrame([r.__dict__ for r, _ in salidas])
    if not devolver_proyecciones:
        return resultados

    proyecciones_rv = {i: proy for i, (_, proy) in enumerate(salidas)}
    return resultados, proyecciones_rv


def proyeccion_mesada_por_anio(
    fila: pd.Series, mesada_encontrada: float, params: config.ParametrosActuariales, max_anios: Optional[int] = None
) -> pd.DataFrame:
    """Devuelve la mesada pensional proyectada por año para una cedula, usando la
    mesada ya encontrada (para graficar). Si max_anios se define, recorta la
    proyeccion a ese numero de años desde la fecha de valoracion.

    OJO: esta funcion SI corre el motor actuarial completo. Cuando la mesada
    viene de una corrida masiva, la proyeccion de Renta Vitalicia ya se
    obtuvo gratis dentro de la iteracion (ver procesar_base con
    devolver_proyecciones=True) y no hace falta llamar aca. Se conserva para
    los casos sueltos, donde no hay una iteracion previa de la cual
    aprovechar el resultado.
    """
    datos = _fila_a_datos_poliza(fila)
    datos.smlv = params.smlv
    datos.mesada_actual = mesada_encontrada
    resultado = calcular_reserva(datos, params, generar_flujos=True)
    return proyeccion_anual_desde_flujos(resultado.flujos, max_anios=max_anios)


@dataclass
class ResultadoCedulaTasaEquivalente:
    cedula: str
    id_cotizacion: str
    mesada_inicial: float
    capital_objetivo_tasa: float
    tasa_equivalente: float
    convergio_tasa: bool
    capital_objetivo_mesada: float
    mesada_encontrada: float
    convergio_mesada: bool
    prima_final: float
    duracion_macaulay: float
    error: str = ""


def _procesar_fila_tasa_equivalente(
    fila: pd.Series, params: config.ParametrosActuariales, indice: int
) -> "ResultadoCedulaTasaEquivalente":
    """
    Procesa UNA fila para Masivo Encontrar Tasa Equivalente. Funcion a nivel
    de modulo (no un closure) para que se pueda enviar a otros procesos via
    core.paralelo.ejecutar_en_paralelo.
    """
    try:
        datos = _fila_a_datos_poliza(fila)
        datos.smlv = params.smlv
        capital_objetivo_mesada = float(fila["capital_renta"])

        r: ResultadoTasaEquivalente = resolver_tasa_y_mesada(
            datos, params, capital_objetivo_mesada=capital_objetivo_mesada
        )

        return ResultadoCedulaTasaEquivalente(
            cedula=_formatear_cedula(fila.get("id_0")),
            id_cotizacion=datos.id_pol,
            mesada_inicial=float(fila["mesada"]),
            capital_objetivo_tasa=r.capital_objetivo_tasa,
            tasa_equivalente=r.tasa_equivalente,
            convergio_tasa=r.convergio_tasa,
            capital_objetivo_mesada=r.capital_objetivo_mesada,
            mesada_encontrada=r.mesada_encontrada,
            convergio_mesada=r.convergio_mesada,
            prima_final=r.prima_final,
            duracion_macaulay=r.duracion_macaulay,
        )
    except Exception as exc:  # noqa: BLE001
        return ResultadoCedulaTasaEquivalente(
            cedula=_formatear_cedula(fila.get("id_0")),
            id_cotizacion=str(fila.get("id_cotizacion", indice)),
            mesada_inicial=float(fila.get("mesada", 0) or 0),
            capital_objetivo_tasa=0.0,
            tasa_equivalente=0.0,
            convergio_tasa=False,
            capital_objetivo_mesada=float(fila.get("capital_renta", 0) or 0),
            mesada_encontrada=0.0,
            convergio_mesada=False,
            prima_final=0.0,
            duracion_macaulay=0.0,
            error=str(exc),
        )


def procesar_base_tasa_equivalente(
    base: pd.DataFrame,
    params: config.ParametrosActuariales,
    callback_progreso: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """
    Para cada fila de la base: (1) calcula el capital objetivo usando la
    curva MTM/TMR de Parametrizacion Actuarial con la mesada de la base como
    referencia, (2) encuentra la tasa equivalente, (3) encuentra la mesada
    final usando esa tasa contra el capital_renta de la base (el capital
    realmente objetivo de la cedula). Replica EncontarTasaEquivalente:
    primero se itera la tasa, despues la mesada.

    Corre en paralelo usando todos los nucleos del equipo menos 1 (igual que
    plan(multisession, workers=detectCores()-1) del proyecto en R) -- ver
    core/paralelo.py. Si el paralelismo no esta disponible en el entorno,
    hace fallback automatico a ejecucion secuencial.
    """
    if not params.curva_expandida():
        raise ValueError("No hay una curva MTM/TMR cargada en Parametrizacion Actuarial.")

    argumentos = [(fila, params, i) for i, (_, fila) in enumerate(base.iterrows())]
    resultados = ejecutar_en_paralelo(_procesar_fila_tasa_equivalente, argumentos, callback_progreso)
    return pd.DataFrame([r.__dict__ for r in resultados])
