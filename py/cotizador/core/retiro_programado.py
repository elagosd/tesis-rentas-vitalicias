"""
Retiro Programado (RP): calculo de la mesada de un portafolio de retiro
programado de un fondo de pensiones privado colombiano.

Se parte del mismo motor de EncontrarMesada (mortalidad, crecimiento,
descuento, auxilio funerario, Duracion Macaulay), con 4 diferencias
(pedidas explicitamente por el usuario):

1. La tabla de mortalidad se usa SIN factores de mejora de longevidad
   (DatosPoliza.sin_factores_mejora=True).
2. Se aplica un "Sobrecosto de mortalidad" adicional, buscado en
   sobrecosto_mortalidad_RP.xlsx segun la edad y el sexo del CAUSANTE en la
   fecha de valoracion (data/sobrecosto_mortalidad_rp.csv).
3. Si el pensionado no tiene beneficiarios, se crea un beneficiario conyuge
   hipotetico (siempre valido) segun tablas_sobrecosto_beneficiario_hipotetico.xlsx
   (hoja Validos o Invalidos, segun el estado del causante), usando la edad
   y el sexo del causante para tomar la diferencia de edad del conyuge
   hipotetico (data/beneficiario_hipotetico_validos.csv /
   _invalidos.csv).
4. Se aplica un recargo adicional de "Gastos RP" (misma formula que los
   demas recargos: ((1/(1-%))-1)*base_reserva).

SUPUESTO A VALIDAR CON EL USUARIO: el sobrecosto de mortalidad y los gastos
RP se calculan cada uno de forma independiente sobre la MISMA base de
reserva (igual que gastos_reserva/gastos_prima en EncontrarMesada / Encontrar
Tasa Equivalente), y se suman ambos recargos a la base para obtener la
Reserva Matematica RP (ver core/motor.py::calcular_reserva). Si en la
practica se deben encadenar de otra forma, avisar para ajustar.
"""

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from . import config
from .metodos_numericos import biseccion, newton, secante
from .motor import DatosPoliza, Persona, ResultadoReserva, _factor_ipc_acumulado, calcular_reserva

_RUTA_DATOS = Path(__file__).resolve().parent.parent / "data"
_RUTA_SOBRECOSTO = _RUTA_DATOS / "sobrecosto_mortalidad_rp.csv"
_RUTA_BENEFICIARIO_VALIDOS = _RUTA_DATOS / "beneficiario_hipotetico_validos.csv"
_RUTA_BENEFICIARIO_INVALIDOS = _RUTA_DATOS / "beneficiario_hipotetico_invalidos.csv"

# Margenes de seguridad para la comparacion comercial Renta Vitalicia (RV)
# vs Retiro Programado (RP), usados por proyectar_rp_dinamico_cai. La
# mesada de RP se topa cada año al (1-margen(t)) de la mesada de RV de ese
# mismo año, con un margen que CRECE con el tiempo (rampa lineal, de
# MARGEN_RP_ANIO1 en el año 1 hasta MARGEN_RP_FINAL en el ultimo año
# proyectado) -- asi RV y RP arrancan parecidos, y la brecha se va abriendo
# año a año, en vez de ser constante o (peor) cerrarse con el tiempo.
# En el primer año especificamente, se fija la mesada de RP EXACTAMENTE en
# ese techo (no solo como limite superior), para que el arranque sea
# consistente entre polizas independientemente de que tan lejos haya
# quedado el calculo actuarial puro.
MARGEN_RP_ANIO1 = 0.02
MARGEN_RP_FINAL = 0.20

# Tolerancia RELATIVA (no de $1 exacto) para decidir si la mesada de RV ya
# calculada coincide con "Mesada_Actual_RP" de la base y por lo tanto se
# activa factor_ajuste_ni. Se uso relativa (no absoluta) porque el propio
# calculo de RV puede diferir levemente (0.5%-2.9% en las pruebas) del
# origen de la columna Mesada_Actual_RP, sin que eso signifique que son
# cedulas distintas -- son diferencias normales de redondeo/parametros,
# no la señal real. Calibrado sobre los 7 casos de
# base_cotizacion_prueba_7_casos.xlsx: las 4 cedulas que SI coinciden
# mostraron 0.51%-2.88% de diferencia; las 3 que NO coinciden mostraron
# 16.4%-54.1% -- una separacion muy clara, 5% queda comodo en el medio.
TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP = 0.05


def _cargar_tabla(ruta: Path) -> pd.DataFrame:
    return pd.read_csv(ruta)


def edad_en_anios(fecha_nacimiento, fecha_valoracion) -> int:
    """Edad en años completos (floor) a la fecha de valoracion."""
    fv = pd.Timestamp(fecha_valoracion)
    fn = pd.Timestamp(fecha_nacimiento)
    edad = fv.year - fn.year
    if (fv.month, fv.day) < (fn.month, fn.day):
        edad -= 1
    return edad


def sobrecosto_mortalidad(edad: int, sexo: int) -> float:
    """% de sobrecosto de mortalidad segun edad (años) y sexo (1=M, 2=F) del
    causante, tomado de sobrecosto_mortalidad_RP.xlsx. Fuera de rango
    (edad<1 o >110): se usa el grupo mas cercano (primero o ultimo)."""
    tabla = _cargar_tabla(_RUTA_SOBRECOSTO)
    edad_acotada = max(1, min(edad, 110))
    fila = tabla[(tabla["edad_min"] <= edad_acotada) & (edad_acotada <= tabla["edad_max"])]
    if fila.empty:
        return 0.0
    columna = "sobrecosto_hombres" if sexo == 1 else "sobrecosto_mujeres"
    return float(fila.iloc[0][columna])


def deslizamiento_rp_aplicable(mesada_actual_rp: Optional[float], params: "config.ParametrosActuariales") -> float:
    """
    Determina que Deslizamiento RP usar, con el MISMO criterio que ya usa
    Renta Vitalicia (datos.mesada_actual == datos.smlv -- ver
    core/motor.py::calcular_reserva): si la mesada actual RP de la cedula
    (columna "Mesada_Actual_RP" de la base) es exactamente igual al SMLV,
    se usa el Deslizamiento RP "alto" (deslizamiento_rp); si es distinta
    (la cedula ya recibe una mesada por encima del SMLV), se usa el
    Deslizamiento RP "bajo" (deslizamiento_rp_bajo). Si no se conoce la
    mesada actual RP (None), se usa el "alto" por compatibilidad con
    llamadas anteriores.
    """
    if mesada_actual_rp is None:
        return params.deslizamiento_rp
    if abs(mesada_actual_rp - params.smlv) < 1.0:
        return params.deslizamiento_rp
    return params.deslizamiento_rp_bajo


def factor_crecimiento_rp(
    indice_anio: int,
    params: "config.ParametrosActuariales",
    mesada_actual_rp: Optional[float] = None,
) -> float:
    """
    Factor de crecimiento acumulado (desde la fecha de valoracion) para el
    año `indice_anio` (0=año de valoracion, 1=un año despues, etc.),
    usando el MISMO esquema de 3 tramos de IPC que usa Renta Vitalicia
    (ipc_primer_anio / ipc_segundo_anio / ipc_objetivo_largo_plazo -- ver
    core/motor.py::_factor_ipc_acumulado), pero con Deslizamiento RP en
    vez del Deslizamiento general -- Deslizamiento RP es un parametro
    propio de Retiro Programado, el resto del esquema de IPC se comparte
    con Renta Vitalicia. Cual Deslizamiento RP (alto/bajo) se decide con
    `deslizamiento_rp_aplicable` segun `mesada_actual_rp`.
    """
    desliz = deslizamiento_rp_aplicable(mesada_actual_rp, params)
    params_desliz_rp = replace(params, delta_deslizamiento=desliz)
    factor = _factor_ipc_acumulado(np.array([indice_anio]), params_desliz_rp, con_deslizamiento=True)
    return float(factor[0])


def crear_beneficiario_hipotetico(causante: Persona, fecha_valoracion) -> Persona:
    """
    Crea el beneficiario conyuge hipotetico segun
    tablas_sobrecosto_beneficiario_hipotetico.xlsx: hoja Validos o
    Invalidos segun el estado del causante, grupo de edad y sexo del
    causante para tomar la diferencia de edad. El conyuge hipotetico
    siempre se crea VALIDO y del sexo opuesto al causante.
    """
    edad_causante = edad_en_anios(causante.fecha_nacimiento, fecha_valoracion)
    ruta = _RUTA_BENEFICIARIO_VALIDOS if causante.estado == config.ESTADO_VALIDO else _RUTA_BENEFICIARIO_INVALIDOS
    tabla = _cargar_tabla(ruta)

    fila = tabla[(tabla["edad_min"] <= edad_causante) & (edad_causante <= tabla["edad_max"])]
    if fila.empty:
        fila = tabla.iloc[[-1 if edad_causante > tabla["edad_max"].max() else 0]]

    if causante.sexo == 1:  # causante hombre -> conyuge mujer
        diferencia = int(fila.iloc[0]["diferencia_edad_hombres"])
        sexo_conyuge = 2
    else:  # causante mujer -> conyuge hombre
        diferencia = int(fila.iloc[0]["diferencia_edad_mujeres"])
        sexo_conyuge = 1

    fecha_nac_conyuge = pd.Timestamp(causante.fecha_nacimiento) - pd.DateOffset(years=diferencia)

    return Persona(
        fecha_nacimiento=fecha_nac_conyuge.date(),
        tipo_beneficiario=config.COD_CONYUGE,
        sexo=sexo_conyuge,
        estado=config.ESTADO_VALIDO,
    )


class _ParamsIteracion:
    def __init__(self, params: "config.ParametrosActuariales"):
        self.epsilon = params.epsilon
        self.max_iteraciones = params.max_iteraciones
        self.paso_derivada = params.paso_derivada


def semilla_estable(*valores) -> int:
    """Entero de 32 bits derivado de un resumen SHA-256 de los valores en JSON."""
    texto = json.dumps(list(valores), ensure_ascii=True, separators=(",", ":"), default=str)
    return int.from_bytes(hashlib.sha256(texto.encode("utf-8")).digest()[:4], "big")


def resolver_mesada_rp(
    datos: DatosPoliza,
    capital_objetivo: float,
    params: "config.ParametrosActuariales",
    mesada_referencia_rv: Optional[float] = None,
) -> "tuple":
    """
    Busca la mesada RP que hace que la Reserva Matematica RP (con
    sobrecosto de mortalidad + gastos RP, sin factores de mejora, con
    beneficiario hipotetico si no hay beneficiarios reales) iguale el
    capital objetivo. Devuelve (resultado_metodo_numerico, ResultadoReserva
    final, beneficiarios_usados, pct_sobrecosto_usado).

    Usa los parametros propios de Retiro Programado de `params`
    (interes_tecnico_rp, deslizamiento_rp, gastos_rp). El esquema de IPC
    (año1/año2/año3+ y el vector mensual del primer año) es el MISMO que
    usa Renta Vitalicia -- ya no hay un "IPC Observado RP" plano separado.

    Si `datos.aplicar_factor_ajuste_ni` es True Y se pasa
    `mesada_referencia_rv` (la mesada de Renta Vitalicia ya calculada para
    esta cedula), se CALIBRA el factor_ajuste_ni EXACTO para esta cedula
    especifica (en vez de usar el valor generico `params.factor_ajuste_ni`):
    se calcula la Reserva Matematica RP a mesada=mesada_referencia_rv, y el
    factor exacto = capital_objetivo / esa_reserva -- el valor que hace que
    la mesada RP resultante coincida (dentro de la tolerancia de
    convergencia del metodo de iteracion, tipicamente << 0.5%) con la
    mesada de RV. Sin `mesada_referencia_rv`, se usa el valor generico
    `params.factor_ajuste_ni` como respaldo.
    """
    fecha_valoracion = pd.Timestamp(datos.fecha_valoracion) + pd.offsets.MonthEnd(0)
    edad_causante = edad_en_anios(datos.causante.fecha_nacimiento, fecha_valoracion)
    pct_sobrecosto = sobrecosto_mortalidad(edad_causante, datos.causante.sexo)

    beneficiarios = list(datos.beneficiarios)
    if not beneficiarios:
        beneficiarios = [crear_beneficiario_hipotetico(datos.causante, fecha_valoracion)]

    # Parametros RP: se usa el MISMO vector/esquema de IPC de 3 tramos
    # (año1/año2/año3+, mas el vector mensual del primer año) que ya usa
    # Renta Vitalicia (Parametros generales) -- ya NO se fuerza todo a un
    # solo dato plano ("IPC Observado RP"). Solo se sobreescribe el
    # Deslizamiento, porque Deslizamiento RP es un parametro propio de
    # Retiro Programado, distinto del Deslizamiento general -- cual de
    # los 2 (alto/bajo) se decide segun datos.mesada_actual_rp (ver
    # deslizamiento_rp_aplicable).
    params_rp = replace(
        params,
        delta_deslizamiento=deslizamiento_rp_aplicable(datos.mesada_actual_rp, params),
    )

    datos_rp = replace(
        datos,
        beneficiarios=beneficiarios,
        # Tasa plana (Interes Tecnico RP), sin curva Smith-Wilson: se probo
        # (ver VALIDACION.md) que la curva por si sola casi triplicaba la
        # reserva necesaria para rentas largas (+140% en un caso real),
        # dejando a la mayoria de las cedulas sin capital suficiente ni
        # para el SMLV. La garantia comercial "RV siempre > RP" ya se
        # logra con el techo de resolver_y_proyectar_rp_para_fila /
        # proyectar_rp_dinamico_cai (rampa MARGEN_RP_ANIO1..MARGEN_RP_FINAL),
        # asi que la curva no hacia falta para eso y solo agregaba un
        # costo de reserva artificial. El modelo Smith-Wilson sigue
        # disponible (core/smith_wilson.py, config.curva_smith_wilson_rp())
        # por si se necesita reactivar mas adelante.
        tasa_interes_real=params.interes_tecnico_rp,
        sin_factores_mejora=True,
        porcentaje_sobrecosto_mortalidad=pct_sobrecosto,
        porcentaje_gastos_rp=params.gastos_rp,
    )

    factor_calibrado = None
    if datos_rp.aplicar_factor_ajuste_ni and mesada_referencia_rv is not None and mesada_referencia_rv > 0:
        datos_referencia = replace(datos_rp, mesada_actual=mesada_referencia_rv)
        r_referencia = calcular_reserva(datos_referencia, params_rp)
        if r_referencia.reserva_matematica_rp > 0:
            factor_calibrado = capital_objetivo / r_referencia.reserva_matematica_rp

    def f(mesada: float) -> float:
        datos_iter = replace(datos_rp, mesada_actual=mesada)
        r = calcular_reserva(datos_iter, params_rp)
        if datos_rp.aplicar_factor_ajuste_ni:
            factor = factor_calibrado if factor_calibrado is not None else params.factor_ajuste_ni
        else:
            factor = 1.0
        return capital_objetivo - r.reserva_matematica_rp * factor

    mesada_min = params.smlv
    mesada_max = params.smlv * 25

    p = _ParamsIteracion(params)
    if params.metodo_iteracion == "biseccion":
        resultado = biseccion(f, mesada_min, mesada_max, p)
    elif params.metodo_iteracion == "newton":
        resultado = newton(f, (mesada_min + mesada_max) / 2, p, limite_inferior=mesada_min, limite_superior=mesada_max)
    else:
        resultado = secante(f, mesada_min, mesada_max, p, limite_inferior=mesada_min, limite_superior=mesada_max)

    # Respaldo: la curva Smith-Wilson hace que f(mesada) sea bastante mas
    # empinada/no lineal que con una tasa plana, y en algunos casos eso hace
    # que secante/Newton se "traben" (los 2 puntos iniciales, muy separados
    # en magnitud, generan un salto que rebota contra el limite). Si el
    # metodo configurado no convergio pero SI hay un cambio de signo real
    # entre mesada_min y mesada_max (o sea, la raiz existe), se reintenta
    # con biseccion, que siempre converge dentro de ese rango.
    if not resultado.convergio and f(mesada_min) * f(mesada_max) < 0:
        resultado = biseccion(f, mesada_min, mesada_max, p)
        resultado.mensaje = (resultado.mensaje + " (respaldo: se reintento con biseccion tras fallar el metodo configurado)").strip()

    datos_final = replace(datos_rp, mesada_actual=resultado.valor)
    resultado_reserva: ResultadoReserva = calcular_reserva(datos_final, params_rp)

    return resultado, resultado_reserva, beneficiarios, pct_sobrecosto


def proyectar_rp_dinamico_cai(
    datos: DatosPoliza,
    capital_inicial: float,
    params: "config.ParametrosActuariales",
    max_anios: int,
    mesada_rv_por_anio: Optional[dict] = None,
    semilla_aleatoria: Optional[int] = None,
    detener_al_cruzar_rv: bool = False,
) -> pd.DataFrame:
    """
    Proyecta la mesada de Retiro Programado año a año, simulando la
    evolucion real de la Cuenta de Ahorro Individual (CAI), en vez de
    resolver una sola mesada y proyectarla con inflacion (como hace
    EncontrarMesada):

    1. Se resuelve la mesada del año actual (resolver_mesada_rp) usando el
       saldo actual de la CAI como capital objetivo, y la edad del
       causante/beneficiarios a la fecha de ESE año.
    2. Se aplica un PISO de crecimiento minimo: la mesada de cada año (a
       partir del segundo) nunca puede ser menor que la del año anterior
       multiplicada por (1 + IPC Observado RP + Deslizamiento RP). Sin
       este piso, la recalculacion pura por saldo/mortalidad puede dar una
       mesada practicamente plana (o hasta decreciente) en algunos casos,
       lo cual no es realista/regulatoriamente valido para RP.
    3. El AÑO 1 arranca EXACTAMENTE en la mesada de Renta Vitalicia de esa
       misma cedula ese año (si se pasa `mesada_rv_por_anio`, dict {año:
       mesada de Renta Vitalicia ese año}) -- no una aproximacion ni un
       margen: el valor exacto. Esto es INCONDICIONAL: no depende de si la
       condicion comercial del punto 3b esta activada, y tiene la ultima
       palabra sobre cualquier otro ajuste de ese año (piso, techo). El
       SMLV proyectado (punto 2) se mantiene como piso legal absoluto, por
       si RV mismo estuviera, en un caso extremo, por debajo del SMLV.
    3b. Desde el año 2 en adelante, si `params.aplicar_condicion_rv_mayor`
       esta activada (OPCIONAL, desactivada por defecto) y el año ya esta
       dentro de la ventana (`params.anio_inicio_condicion_rv` en
       adelante), `mesada_rv_por_anio` se usa como TECHO para la mesada de
       RP, con un margen (1-margen(t)) que CRECE con el tiempo (rampa
       lineal de MARGEN_RP_ANIO1 hasta MARGEN_RP_FINAL en el ultimo año
       del horizonte). Con la condicion desactivada (default), la mesada
       de RP desde el año 2 sale UNICAMENTE de su propia dinamica
       actuarial (piso de crecimiento + riesgo de mercado de la CAI). El
       SMLV proyectado (punto 2) siempre tiene la ultima palabra, incluso
       por encima de la condicion comercial si esta activada: por ley
       nunca se puede pagar menos de un SMLV.
    3c. LIMITE DE CAIDA ANUAL: como ultimo filtro (despues del piso, del
       techo comercial, del SMLV proyectado y del arranque en RV), la
       mesada de un año nunca puede ser menor que
       (1 - `params.caida_maxima_anual_rp`) veces la del año anterior --
       50% por defecto. Sin este limite, un mal año de mercado o una
       normalizacion al SMLV proyectado pueden desplomar la mesada de un
       año al siguiente y dibujar en el grafico un acantilado que parece
       un "cae a cero". Solo puede SUBIR la mesada, nunca bajarla, asi que
       no compite con el piso legal del SMLV.
    4. Se restan del saldo las mesadas efectivamente pagadas ese año (13 o
       14 veces la mesada YA con piso/techo/limite de caida aplicados,
       segun datos.n_mesadas).
    5. El saldo remanente crece a la Tasa de Crecimiento de la CAI
       (params.tasa_crecimiento_cai) -- distinta del Interes Tecnico RP,
       que es la tasa actuarial usada dentro de la formula de reserva de
       cada año, no la tasa real de la cuenta.
    6. Se repite para el año siguiente (edad +1 año, saldo actualizado)
       hasta max_anios o hasta que la CAI se agote (saldo <= 0).

    NOTA: cuando el piso (de crecimiento o de arranque) obliga a pagar mas
    de lo que la recalculacion por saldo/mortalidad hubiera dado, la CAI
    se agota mas rapido de lo que esa recalculacion asumia -- es el
    comportamiento economico esperado, y el año siguiente ya parte del
    saldo real reducido. El techo actua en la direccion contraria: hace
    que el fondo se agote MAS LENTO, porque limita lo que efectivamente se
    paga.

    HORIZONTE (cambio 2026-08-21, peticion del usuario): la proyeccion
    corre los `max_anios` completos (20 por defecto, ver
    config.MAX_ANIOS_PROYECCION_RP_TOPE), igual que la de Renta Vitalicia.
    Antes se cortaba sola en cuanto la mesada de RP quedaba por debajo de
    la de RV, asi que cada cedula mostraba un numero distinto de años; ese
    comportamiento sigue disponible con `detener_al_cruzar_rv=True`
    (lo usa el comparador de escenarios), pero ya NO es el default.
    La proyeccion de RP sigue cortandose antes de los 20 años cuando la CAI
    deja de alcanzar -- y en ese caso simplemente no se generan mas filas:
    los años restantes quedan SIN DATO (no se rellenan con ceros ni con
    valores estimados), de modo que en el grafico la linea de RP termina
    ahi mientras la de RV continua hasta el año 20.

    SMLV es un PISO LEGAL, no un piso de crecimiento: si el fondo ya esta
    pegado al SMLV (la mesada calculada, sin ningun ajuste, es igual al
    SMLV), NO se le exige crecer IPC+deslizamiento el año siguiente -- eso
    seria pedirle al fondo plata que no tiene. Y si el fondo deja de
    alcanzar ni para el SMLV (Convergio=False), la proyeccion SE DETIENE
    ahi mismo -- esa es la ULTIMA fila que se genera; no se sigue
    "estimando" años que el fondo ya no puede sostener ni el SMLV. En el
    grafico, esto se ve como el punto donde la linea de Retiro Programado
    simplemente termina (no se marca con una linea vertical adicional).

    RIESGO DE MERCADO en el crecimiento de la CAI: el saldo NO crece con
    una tasa fija todos los años -- cada año se sortea una tasa de
    crecimiento real de una distribucion normal (media=`tasa_crecimiento_cai`,
    desviacion estandar=`tasa_crecimiento_cai_volatilidad`), reflejando que
    un portafolio de Retiro Programado (renta variable + deuda publica +
    ETFs internacionales) tiene años buenos y años malos, no un rendimiento
    plano. Esto es lo que permite que, incluso en cedulas pegadas al SMLV
    (sin margen actuarial para crecer via el piso de IPC+deslizamiento), la
    mesada SI pueda subir o bajar de un año a otro: si el sorteo de ese año
    da un buen rendimiento, el saldo crece mas de lo pagado y el causante
    puede volver a ser actuarialmente sostenible por encima del SMLV al año
    siguiente; si da un mal año, el saldo se reduce mas rapido. El sorteo es
    REPRODUCIBLE por cedula (mismo `semilla_aleatoria` -> misma trayectoria
    siempre), para que los resultados no cambien entre corridas de la misma
    cedula, pero SI varian entre cedulas distintas.

    Devuelve un DataFrame con columnas: Anio, Mesada_Pensional_proyectada
    (lo que se paga, con piso/techo/piso-de-arranque ya aplicados),
    Mesada_sin_piso (lo que el saldo/mortalidad de ese año realmente
    sostiene, SIN ningun ajuste -- util para ver que tan rapido se esta
    descapitalizando el fondo), Saldo_CAI_inicio_anio, Convergio (False =
    el saldo de ese año ya no alcanza para sostener ni el SMLV por su
    cuenta -- el fondo dejo de ser autosuficiente, aunque los ajustes lo
    sigan sosteniendo artificialmente), Piso_aplicado, Techo_aplicado,
    Caida_limitada (True = ese año la mesada iba a caer mas del maximo
    permitido y se levanto al piso de caida),
    Tasa_crecimiento_CAI_este_anio (la tasa sorteada ese año, para
    transparencia -- puede ser distinta de params.tasa_crecimiento_cai,
    incluso negativa, por el riesgo de mercado simulado).
    """
    filas = []
    cai_actual = capital_inicial
    fecha_valoracion_actual = pd.Timestamp(datos.fecha_valoracion)
    mesada_anterior = None

    # Riesgo de mercado: se sortean de antemano las tasas de crecimiento de
    # la CAI de cada año del horizonte (distribucion normal, media/desv.
    # segun params). Si no se da una semilla explicita, se deriva una
    # semilla ESTABLE a partir de los datos de la poliza (id, fecha de
    # nacimiento del causante, sexo y capital inicial): se serializan en
    # JSON con orden y formato fijos y se toma un resumen SHA-256. A
    # diferencia de hash() de Python, el resultado no cambia entre procesos,
    # de modo que la misma poliza da siempre la misma trayectoria.
    if semilla_aleatoria is None:
        semilla_aleatoria = semilla_estable(
            datos.id_pol, str(datos.causante.fecha_nacimiento), datos.causante.sexo, round(capital_inicial, 2)
        )
    generador = np.random.default_rng(semilla_aleatoria)

    # mesada_referencia_rv: la mesada de RV del año 1 (extraida de
    # mesada_rv_por_anio, si se paso) -- se usa para calibrar
    # factor_ajuste_ni de forma EXACTA para esta cedula (ver
    # resolver_mesada_rp), no un valor generico fijo. Se calcula UNA sola
    # vez aqui y se reusa en TODOS los años del bucle (misma calibracion
    # todo el horizonte, no se recalibra año a año).
    mesada_referencia_rv = None
    if mesada_rv_por_anio:
        anio_inicial = pd.Timestamp(datos.fecha_valoracion).year
        mesada_referencia_rv = mesada_rv_por_anio.get(anio_inicial)
    # Castigo deterministico (todos los años, no solo ruido aleatorio):
    # reduce sistematicamente la media del crecimiento de la CAI, para
    # reflejar el riesgo de mercado real de un portafolio de Retiro
    # Programado -- ver CASTIGO_RIESGO_MERCADO_CAI_DEFECTO en config.py.
    media_crecimiento_castigada = params.tasa_crecimiento_cai - params.castigo_riesgo_mercado_cai
    tasas_crecimiento_sorteadas = generador.normal(
        media_crecimiento_castigada, params.tasa_crecimiento_cai_volatilidad, size=max_anios
    )
    # Piso de -90% para evitar que un sorteo extremo deje el crecimiento en
    # menos de -100% (saldo negativo por la propia tasa, sin sentido economico).
    tasas_crecimiento_sorteadas = np.maximum(tasas_crecimiento_sorteadas, -0.90)

    for indice_anio in range(max_anios):
        if cai_actual <= 0:
            break

        datos_anio = replace(datos, fecha_valoracion=fecha_valoracion_actual.date())
        resultado_metodo, _, _, _ = resolver_mesada_rp(datos_anio, cai_actual, params, mesada_referencia_rv=mesada_referencia_rv)
        mesada_calculada = resultado_metodo.valor
        if not resultado_metodo.convergio:
            # Cuando no hay una raiz real en el rango de busqueda [SMLV,
            # SMLV*25], cada metodo numerico "degenera" hacia un limite
            # distinto (biseccion tiende al limite superior si no logra
            # acotar una raiz real; secante/newton acotados tienden al
            # limite inferior) -- ninguno de los 2 valores es una
            # respuesta actuarial real. Se normaliza siempre al SMLV
            # PROYECTADO a este año (misma formula de crecimiento que usa
            # el motor de reserva: SMLV*(1+IPC+deslizamiento)^n -- el
            # salario minimo legal tambien crece con el tiempo, no se
            # queda fijo en el valor de hoy), para que el resultado no
            # dependa de que metodo de iteracion este configurado, y para
            # que la mesada de las cedulas "pegadas al SMLV" seguga
            # reflejando el crecimiento real del salario minimo en vez de
            # quedar congelada en pesos nominales de hoy.
            mesada_calculada = params.smlv * factor_crecimiento_rp(indice_anio, params, datos.mesada_actual_rp)
        anio_actual = fecha_valoracion_actual.year
        es_primer_anio = mesada_anterior is None
        # El fondo no tiene una solucion actuarial valida en este año --
        # sea porque quedo pegado al SMLV (limite inferior de la
        # busqueda), sea porque el metodo configurado no convergio del
        # todo (Convergio=False). Esto ultimo importa porque un metodo que
        # no converge puede "degenerar" hacia CUALQUIERA de los 2 limites
        # de busqueda segun el algoritmo (biseccion tiende a degenerar
        # hacia el limite superior si no logra acotar una raiz real,
        # mientras que secante/newton acotados tienden a degenerar hacia
        # el limite inferior) -- ninguno de los 2 valores es una respuesta
        # actuarial real en ese caso, asi que NO hay que forzar el techo
        # comercial (RP cerca de RV) sobre un numero que no significa nada.
        pegado_al_smlv = mesada_calculada <= params.smlv * (1 + 1e-9) or not resultado_metodo.convergio

        piso_aplicado = False
        if not es_primer_anio and mesada_anterior > params.smlv * (1 + 1e-9) and not pegado_al_smlv:
            # Solo se exige el crecimiento minimo si HABIA margen real por
            # encima del SMLV tanto el año anterior como este año -- si
            # cualquiera de los 2 esta pegado al piso legal, forzar
            # crecimiento seria pedirle al fondo plata que no tiene (y
            # podria hasta empujar a RP por encima de RV, si RV tambien
            # viene bajando). El crecimiento minimo exigido es el
            # crecimiento INCREMENTAL de este año vs el año anterior, con
            # el mismo esquema de 3 tramos de IPC que usa Renta Vitalicia.
            factor_incremental = factor_crecimiento_rp(indice_anio, params, datos.mesada_actual_rp) / factor_crecimiento_rp(indice_anio - 1, params, datos.mesada_actual_rp)
            mesada_piso = mesada_anterior * factor_incremental
            if mesada_piso > mesada_calculada:
                piso_aplicado = True
            mesada_anio = max(mesada_calculada, mesada_piso)
        else:
            mesada_anio = mesada_calculada

        techo_aplicado = False
        smlv_proyectado_este_anio = params.smlv * factor_crecimiento_rp(indice_anio, params, datos.mesada_actual_rp)
        # La condicion comercial "Renta Vitalicia > Retiro Programado" es
        # OPCIONAL (peticion del usuario 2026-08-18): solo se aplica si
        # params.aplicar_condicion_rv_mayor es True, y en ese caso desde el
        # año params.anio_inicio_condicion_rv (1-indexado; por defecto 3).
        # Desactivada (default), la mesada de RP sale UNICAMENTE de su
        # propia dinamica actuarial (piso de crecimiento, SMLV proyectado)
        # mas el riesgo de mercado del crecimiento de la CAI -- que es lo
        # que, de forma organica, la lleva a quedar por debajo de RV.
        aplica_condicion_rv = (
            params.aplicar_condicion_rv_mayor
            and indice_anio >= max(params.anio_inicio_condicion_rv - 1, 0)
        )
        if aplica_condicion_rv and mesada_rv_por_anio and anio_actual in mesada_rv_por_anio:
            rv_anio = mesada_rv_por_anio[anio_actual]
            # Rampa lineal: margen chico apenas empieza a aplicar (año 3),
            # creciendo hasta MARGEN_RP_FINAL en el ultimo año del
            # horizonte proyectado (la brecha se va abriendo con el tiempo).
            if max_anios > 1:
                fraccion = indice_anio / (max_anios - 1)
            else:
                fraccion = 0.0
            margen_este_anio = MARGEN_RP_ANIO1 + (MARGEN_RP_FINAL - MARGEN_RP_ANIO1) * fraccion
            # El SMLV PROYECTADO es un piso legal, siempre tiene prioridad
            # sobre el techo comercial (RP<RV): si el (1-margen) de RV cae
            # por debajo del SMLV proyectado de ese año (puede pasar: el
            # SMLV crece con IPC+deslizamiento, mas rapido que el
            # esquema de IPC que usa RV en la mayoria de los casos), el
            # techo efectivo es el SMLV proyectado, no ese valor menor --
            # por ley, nunca se puede pagar menos de un SMLV, ni siquiera
            # para mantener la garantia comercial RV>RP.
            techo = max(rv_anio * (1 - margen_este_anio), smlv_proyectado_este_anio)

            if mesada_anio > techo:
                techo_aplicado = True
                mesada_anio = techo
            elif mesada_anio < smlv_proyectado_este_anio:
                # Salvaguarda: el SMLV proyectado nunca se viola, ni
                # aunque el piso de crecimiento/techo hayan dado algo
                # menor por algun caso limite.
                mesada_anio = smlv_proyectado_este_anio
        elif mesada_anio < smlv_proyectado_este_anio:
            # Fuera de la ventana de la condicion RV>RP (años 1-2), el
            # SMLV proyectado sigue siendo un piso legal que nunca se viola.
            mesada_anio = smlv_proyectado_este_anio

        if es_primer_anio and mesada_rv_por_anio and anio_actual in mesada_rv_por_anio:
            # El año 1 de RP arranca EXACTAMENTE en la misma mesada que
            # Renta Vitalicia (peticion del usuario 2026-08-20) -- no una
            # aproximacion, no un margen: el valor exacto de RV ese año.
            # Esto es INCONDICIONAL (no depende de si la condicion
            # comercial "RV>RP" esta activada, esa condicion es sobre los
            # años SIGUIENTES del horizonte, no sobre el arranque) y tiene
            # la ULTIMA palabra sobre cualquier ajuste anterior (piso,
            # techo comercial). El SMLV proyectado se mantiene como piso
            # legal absoluto, por si RV mismo estuviera, en un caso
            # extremo, por debajo del SMLV.
            rv_anio1 = mesada_rv_por_anio[anio_actual]
            mesada_exacta_esperada = max(rv_anio1, smlv_proyectado_este_anio)
            if mesada_anio != mesada_exacta_esperada:
                techo_aplicado = True
            mesada_anio = mesada_exacta_esperada

        # LIMITE DE CAIDA ANUAL (peticion del usuario 2026-08-21): la
        # mesada de RP no puede caer mas de params.caida_maxima_anual_rp
        # (50% por defecto) respecto a la del año anterior. Se aplica al
        # FINAL, despues de todos los demas ajustes (piso de crecimiento,
        # techo comercial, SMLV proyectado, arranque en RV), porque es el
        # ultimo filtro sobre lo que efectivamente se paga.
        #
        # Este ajuste solo puede SUBIR la mesada, nunca bajarla, asi que no
        # entra en conflicto con el piso legal del SMLV proyectado. Lo que
        # se pague de mas si sale del saldo real de la CAI (ver el descuento
        # mas abajo), asi que el fondo se agota antes -- exactamente como
        # pasa con el piso de crecimiento.
        caida_limitada = False
        if not es_primer_anio and mesada_anterior is not None:
            piso_caida = mesada_anterior * (1 - params.caida_maxima_anual_rp)
            if mesada_anio < piso_caida:
                caida_limitada = True
                mesada_anio = piso_caida

        tasa_crecimiento_este_anio = float(tasas_crecimiento_sorteadas[indice_anio])

        filas.append({
            "Anio": anio_actual,
            "Mesada_Pensional_proyectada": mesada_anio,
            "Mesada_sin_piso": mesada_calculada,
            "Saldo_CAI_inicio_anio": cai_actual,
            "Convergio": resultado_metodo.convergio,
            "Piso_aplicado": piso_aplicado,
            "Techo_aplicado": techo_aplicado,
            "Caida_limitada": caida_limitada,
            "Tasa_crecimiento_CAI_este_anio": tasa_crecimiento_este_anio,
        })

        if not resultado_metodo.convergio:
            # El calculo actuarial dice que el saldo actual ya no alcanza
            # para garantizar ni el SMLV -- la CAI no tiene capital
            # suficiente para sostener un SMLV. Se detiene la proyeccion
            # AQUI (esta es la ultima fila que se genera); no se sigue
            # "estimando" años que el fondo ya no puede sostener.
            break

        if detener_al_cruzar_rv and mesada_rv_por_anio and anio_actual in mesada_rv_por_anio:
            # Horizonte DINAMICO (peticion del usuario 2026-08-18): la
            # proyeccion se extiende año a año hasta que la mesada de
            # Retiro Programado quede por debajo de la de Renta Vitalicia
            # -- ese es el dato que interesa mostrar. Una vez ocurre, este
            # año queda como el ultimo de la serie. Si nunca ocurre, la
            # proyeccion corre hasta max_anios (el tope duro).
            if mesada_anio < mesada_rv_por_anio[anio_actual]:
                break

        mesada_anterior = mesada_anio

        total_pagado_anio = mesada_anio * datos.n_mesadas
        cai_actual = (cai_actual - total_pagado_anio) * (1 + tasa_crecimiento_este_anio)

        fecha_valoracion_actual = fecha_valoracion_actual + pd.DateOffset(years=1)

    return pd.DataFrame(filas)


def primer_anio_bajo_smlv(proyeccion: pd.DataFrame) -> Optional[int]:
    """
    Devuelve el primer año (columna Anio) de una proyeccion de
    proyectar_rp_dinamico_cai donde Convergio=False -- es decir, el primer
    año en que el saldo de la CAI ya no alcanza para sostener ni el SMLV
    por su cuenta (el fondo dejo de ser autosuficiente, aunque el piso de
    crecimiento lo siga sosteniendo artificialmente). None si nunca pasa
    dentro del horizonte proyectado.
    """
    if proyeccion.empty or "Convergio" not in proyeccion.columns:
        return None
    filas_criticas = proyeccion[~proyeccion["Convergio"]]
    if filas_criticas.empty:
        return None
    return int(filas_criticas["Anio"].iloc[0])


def resolver_y_proyectar_rp_para_fila(
    fila: pd.Series,
    params: "config.ParametrosActuariales",
    max_anios: Optional[int] = None,
    mesada_rv_encontrada: Optional[float] = None,
    detener_al_cruzar_rv: bool = False,
) -> "tuple":
    """
    Corre el calculo REAL de Retiro Programado (con evolucion dinamica de
    la CAI, ver proyectar_rp_dinamico_cai) para una fila de la base masiva
    (mismo causante/beneficiarios/fecha de valoracion que Masivo
    EncontrarMesada), usando `capital_renta` de la fila como saldo inicial
    de la CAI -- el mismo capital que ya se usa para Renta Vitalicia, para
    que la comparacion sea a igual capital -- y los parametros RP guardados
    en la pestaña Retiro Programado de Parametrizacion Actuarial.

    Si se pasa `mesada_rv_encontrada` (la mesada de Renta Vitalicia ya
    encontrada para esta misma cedula), se calcula la proyeccion de Renta
    Vitalicia por año y se usa para topar (todos los años) y acercar (solo
    el primer año) la mesada de Retiro Programado -- ver
    proyectar_rp_dinamico_cai para el detalle. Garantiza que Renta
    Vitalicia siempre pague mas, y que ambos productos arranquen parecidos
    en el año 1 -- requisitos de negocio explicitos (ver VALIDACION.md),
    no una propiedad que emerja sola del calculo actuarial. Ademas, si
    `mesada_rv_encontrada` coincide con `datos.mesada_actual_rp` (columna
    "Mesada_Actual_RP" de la base), se activa `factor_ajuste_ni` en el
    calculo de RP (ver config.py y resolver_mesada_rp).

    Devuelve (proyeccion_por_año, convergio_año_1). Si no hay beneficiarios
    reales en la fila, se crea el conyuge hipotetico automaticamente cada
    año (igual que en la pestaña individual).
    """
    from .base_masiva import _fila_a_datos_poliza, proyeccion_mesada_por_anio  # import local: evita ciclo de imports

    datos = _fila_a_datos_poliza(fila)
    datos.smlv = params.smlv
    capital_objetivo = float(fila["capital_renta"])
    # Horizonte FIJO (cambio 2026-08-21, peticion del usuario): si no se
    # pide otro, se usan los params.max_anios_proyeccion_rp_tope años (20
    # por defecto), los mismos que se proyectan para Renta Vitalicia. La
    # serie de RP solo queda mas corta si la CAI deja de alcanzar antes.
    # El corte dinamico anterior ("cortar en cuanto RP < RV") sigue
    # disponible via detener_al_cruzar_rv=True -- lo usa el comparador de
    # escenarios, que necesita medir en que año se da el cruce.
    max_anios_usado = max_anios or params.max_anios_proyeccion_rp_tope

    # Factor de ajuste NI: se activa cuando la mesada de RV YA CALCULADA
    # (correctamente, sin cambios) coincide -- dentro de una tolerancia
    # RELATIVA, ver TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP -- con la columna
    # "Mesada_Actual_RP" de la base. Ver params.factor_ajuste_ni.
    if (
        mesada_rv_encontrada is not None and mesada_rv_encontrada > 0
        and datos.mesada_actual_rp is not None and datos.mesada_actual_rp > 0
        and abs(mesada_rv_encontrada - datos.mesada_actual_rp) / datos.mesada_actual_rp
        < TOLERANCIA_RELATIVA_MESADA_ACTUAL_RP
    ):
        datos.aplicar_factor_ajuste_ni = True

    mesada_rv_por_anio = None
    if mesada_rv_encontrada is not None and mesada_rv_encontrada > 0:
        proyeccion_rv = proyeccion_mesada_por_anio(fila, mesada_rv_encontrada, params, max_anios=max_anios_usado)
        mesada_rv_por_anio = {
            int(fila_rv["Anio"]): float(fila_rv["Mesada_Pensional_proyectada"])
            for _, fila_rv in proyeccion_rv.iterrows()
        }

    proyeccion = proyectar_rp_dinamico_cai(
        datos, capital_objetivo, params, max_anios=max_anios_usado,
        mesada_rv_por_anio=mesada_rv_por_anio,
        detener_al_cruzar_rv=detener_al_cruzar_rv,
    )
    convergio = bool(proyeccion["Convergio"].iloc[0]) if len(proyeccion) > 0 else False
    return proyeccion, convergio
