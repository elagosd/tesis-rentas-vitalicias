"""
Configuracion y constantes del motor actuarial "cotizador".

Estas constantes replican exactamente la hoja EncontrarMesada del Excel
"Nueva_nota_tecnica_30_jul_2026.xlsm" (filas 27-1466, columnas AI:AR para
la tabla de mortalidad). No deben cambiarse sin volver a validar contra
el Excel, ya que estan atadas a la estructura de esa hoja.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Numero de meses proyectados: la hoja EncontrarMesada tiene datos desde la
# fila 28 (t=1) hasta la fila 1466 (t=1439).
N_MESES = 1439

# La "vigencia" general de la poliza (columna E) se apaga a partir de t=1321
# (fila 1348 del Excel) hasta el final de la proyeccion.
VIGENCIA_CORTE_T = 1321

# Tabla de mortalidad: edades 0 a 122 (columna AI, filas 28 a 150 => 123 filas)
FILAS_TABLA_MORTALIDAD = 123

# Limites de la tabla de mortalidad mensualizada (en "Edad_meses"), tomados
# de las formulas de nPx / Qx_t de la hoja (limite de tabla ~ 110 anios).
LIMITE_QX_MEJORADA_EDAD_MESES = 1320
LIMITE_QX_T_EDAD_MESES = 1319
LIMITE_NPX_EDAD_MESES = 1331

# Duracion maxima de un beneficio en meses (edad limite de la tabla == 1331
# meses de edad), usada por defecto para causante y beneficiarios sin regla
# especial.
DURA_Y_LIMITE = 1331

# Codigos de tipo de beneficiario (columna "Tipo de beneficiario" del Excel)
COD_CAUSANTE = 1
COD_HIJO = 2
COD_CONYUGE = 4
COD_PADRE = 5
COD_MADRE = 6
COD_CONYUGE_TEMPORAL = 7

MAPA_TIPO_BENEFICIARIO_TEXTO = {
    "CAUSANTE": 1,
    "AFILIADO": 1,
    "AFILIADO(A)": 1,
    "HIJO": 2,
    "HIJO/A": 2,
    "HIJO(A)": 2,
    "CONYUGE": 4,
    "CÓNYUGE": 4,
    "COMPANERO/A": 4,
    "COMPAÑERO/A": 4,
    "PADRE": 5,
    "MADRE": 6,
    "CONYUGE TEMPORAL": 7,
    "CÓNYUGE TEMPORAL": 7,
    "COMPAÑERO/A MENOR 30": 7,
}

# Codigos de estado
ESTADO_VALIDO = 1
ESTADO_INVALIDO = 2
ESTADO_MUERTO = 3

# Numero maximo de beneficiarios soportados en las paginas individuales
# (Encontrar Mesada, Encontrar Tasa Equivalente) y en la base masiva
# (id_1..id_9 de base_polizas_10_polizas.xlsx).
MAX_BENEFICIARIOS = 9

# Ruta a la tabla de mortalidad extraida del Excel (columnas AI:AR de
# EncontrarMesada). Ver data/tabla_mortalidad.csv
RUTA_TABLA_MORTALIDAD = Path(__file__).resolve().parent.parent / "data" / "tabla_mortalidad.csv"

# --- Parametros actuariales por defecto (Parametrizacion actuarial) ---

SMLV_DEFECTO = 1_750_905.0
DELTA_DESLIZAMIENTO_DEFECTO = 0.0013
PORCENTAJE_RESERVA_CAMBIO_GRUPO_DEFECTO = 0.006  # 0.6%
PORCENTAJE_RECARGO_GASTOS_RESERVA_DEFECTO = 0.05  # 5%
PORCENTAJE_RECARGO_GASTOS_PRIMA_DEFECTO = 0.05  # 5%
EPSILON_DEFECTO = 1.0
MAX_ITERACIONES_DEFECTO = 200
PASO_DERIVADA_DEFECTO = 1.0

# Biseccion de la tasa equivalente (macro EncontrarValorCercanoACero del
# Excel): rango de busqueda de la tasa real [0%, 50%].
TASA_EQUIVALENTE_MIN_DEFECTO = 0.0
TASA_EQUIVALENTE_MAX_DEFECTO = 0.5

# Numero de nodos anuales que soporta la curva (columnas EG27:EG146 de la
# hoja EncontarTasaEquivalente = 120 nodos, uno por año 1..120).
NODOS_CURVA_MTM = 120

# Vector de inflacion mensual del primer año (12 valores, Ene-Dic), tal como
# se carga en 'Vector Inflación'!E3:E14. Se usa UNICAMENTE para el descuento
# tecnico mensual de los primeros 12 meses de la proyeccion (columna FE);
# NO determina la inflacion anual del primer año (ver ipc_primer_anio abajo,
# que es un dato independiente -- en el Excel viene de BANREP_ENCUESTA, no
# es el compuesto de este vector). Valores por defecto tomados del ejemplo
# validado del Excel (politica 4).
VECTOR_IPC_PRIMER_ANIO_DEFECTO: List[float] = [
    0.0118, 0.0108, 0.0078,
    0.0034758674674324475, 0.0034758674674324475, 0.0034758674674324475,
    0.0034758674674324475, 0.0034758674674324475, 0.0034758674674324475,
    0.0034758674674324475, 0.0034758674674324475, 0.0034758674674324475,
]
IPC_PRIMER_ANIO_DEFECTO = 0.0634
IPC_SEGUNDO_ANIO_DEFECTO = 0.0477
IPC_OBJETIVO_LARGO_PLAZO_DEFECTO = 0.03

# Retiro Programado (pestaña dentro de Parametrizacion Actuarial)
INTERES_TECNICO_RP_DEFECTO = 0.0420
DESLIZAMIENTO_RP_DEFECTO = 0.0423
# Deslizamiento RP "bajo" -- se usa en vez del de arriba cuando la mesada
# actual RP de la cedula (columna "Mesada_Actual_RP" de la base) es
# DISTINTA del SMLV. El de arriba (4.23%) se usa cuando la mesada actual
# RP es exactamente el SMLV -- mismo criterio que ya usa Renta Vitalicia
# para decidir si el crecimiento de la mesada incluye deslizamiento.
DESLIZAMIENTO_RP_BAJO_DEFECTO = 0.0253
GASTOS_RP_DEFECTO = 0.015
# Tasa de crecimiento de la Cuenta de Ahorro Individual (CAI): rendimiento
# real que se asume para el saldo remanente de la cuenta, año a año, al
# recalcular la mesada de Retiro Programado (distinta del Interes Tecnico
# RP, que es la tasa actuarial usada dentro de la formula de reserva).
TASA_CRECIMIENTO_CAI_DEFECTO = 0.05
# Volatilidad (desviacion estandar anual) de la Tasa de Crecimiento de la
# CAI -- refleja el riesgo de mercado real del portafolio de Retiro
# Programado (no crece igual todos los años). ESTIMACION, no un calculo
# historico exacto: no se pudo descargar la serie diaria completa de
# Rentabilidad de Retiro Programado (datos.gov.co, dataset gfy9-fpbr,
# requiere acceso API que no esta disponible aqui). Se estimo a partir de
# 2 referencias reales de Colfondos: la rentabilidad de Retiro Programado
# vario de 4.64% (1er trimestre 2025, anualizado) a 11.31% (promedio de
# los ultimos 4 años a jun-2026) -- una dispersion real notable -- y de la
# composicion del portafolio (~73% deuda publica, ~27% renta variable/ETF
# internacional/fondos de capital privado, un perfil moderado-conservador).
# Se recomienda reemplazar este valor si el fondo tiene acceso a la serie
# historica completa de rentabilidad mensual/diaria real.
TASA_CRECIMIENTO_CAI_VOLATILIDAD_DEFECTO = 0.06
# Castigo (haircut) DETERMINISTICO restado de la Tasa de Crecimiento de la
# CAI todos los años, para reflejar el riesgo de mercado de forma
# sistematica (no solo como ruido aleatorio via la volatilidad de arriba).
# Calibrado empiricamente (ver VALIDACION.md) sobre las 9 polizas reales de
# ejemplos/base_polizas_10_polizas.xlsx: 5% es el castigo MINIMO que logra
# que las 9 polizas terminen con Retiro Programado por debajo de Renta
# Vitalicia de forma PERMANENTE dentro de un horizonte de 10 años (de
# forma organica, sin depender del techo comercial RV>RP, que solo aplica
# desde el año 3). El año exacto del cruce varia bastante entre polizas
# (desde el año 1 hasta el año 10, segun cuanto capital tenga cada cedula
# relativo a lo que necesita) -- no hay un castigo unico que logre que
# TODAS crucen exactamente en el mismo año 5-7; ese es el minimo que
# garantiza que ninguna quede permanentemente por encima.
#
# CAMBIO (2026-08-18, peticion del usuario): se pone en 0 por defecto.
# El usuario pidio explicitamente proyectar con "5% de rentabilidad real y
# 6% de volatilidad" -- con un castigo de 5% la rentabilidad ESPERADA
# efectiva quedaba en 0% (5% - 5%), que no es lo pedido. Dejandolo en 0,
# la media efectiva del sorteo es exactamente TASA_CRECIMIENTO_CAI_DEFECTO
# (5%) con desviacion TASA_CRECIMIENTO_CAI_VOLATILIDAD_DEFECTO (6%). El
# parametro sigue existiendo y es editable en la app por si se quiere
# volver a un escenario mas conservador.
CASTIGO_RIESGO_MERCADO_CAI_DEFECTO = 0.0
# Condicion comercial "Renta Vitalicia > Retiro Programado": OPCIONAL
# (peticion del usuario 2026-08-18). Antes se aplicaba siempre desde el
# año 3; ahora queda desactivada por defecto y se puede activar (y elegir
# desde que año aplica) en Parametrizacion Actuarial > Retiro Programado.
# Con la condicion desactivada, la mesada de RP sale unicamente de su
# propia dinamica actuarial + riesgo de mercado.
APLICAR_CONDICION_RV_MAYOR_DEFECTO = False
ANIO_INICIO_CONDICION_RV_DEFECTO = 3
# Horizonte de la proyeccion, en años, para AMBOS productos (Renta
# Vitalicia y Retiro Programado).
#
# CAMBIO (2026-08-21, peticion del usuario): antes esto era solo un "tope
# duro" de 40 años y el horizonte REAL de cada cedula era dinamico -- la
# proyeccion de RP se cortaba sola en cuanto su mesada quedaba por debajo
# de la de RV, asi que cada cedula mostraba un numero distinto de años.
# Ahora el horizonte es FIJO en 20 años para las dos lineas: RV siempre
# proyecta los 20 años completos, y RP proyecta hasta 20 años tambien,
# cortandose antes SOLO si la CAI deja de alcanzar (ver
# proyectar_rp_dinamico_cai). En ese caso la linea de RP simplemente
# TERMINA en ese año -- no se rellenan los años restantes con ceros ni con
# valores estimados.
MAX_ANIOS_PROYECCION_RP_TOPE = 20

# Valor que tenia MAX_ANIOS_PROYECCION_RP_TOPE antes del cambio a 20 años.
# Se usa unicamente para migrar parametrizaciones ya guardadas en disco
# (ver core/persistencia.py::_migrar_parametros): si una parametrizacion
# vieja trae exactamente el default anterior, se entiende que nadie lo
# cambio a proposito y se actualiza al nuevo default de 20.
MAX_ANIOS_PROYECCION_RP_TOPE_LEGACY = 40

# Caida maxima permitida en la mesada de Retiro Programado de un año al
# siguiente (peticion del usuario 2026-08-21): la mesada de un año nunca
# puede ser menor que (1 - este valor) veces la del año anterior. Con 0.50,
# la mesada no puede caer mas de un 50% año a año.
#
# Por que existe: la mesada de RP se recalcula cada año contra el saldo
# real de la CAI, y cuando el saldo se deteriora (mal año de mercado, o el
# solver deja de encontrar una mesada >= SMLV y se normaliza al SMLV
# proyectado) el valor puede desplomarse de un año a otro, dibujando en el
# grafico un acantilado que parece un "cae a cero" aunque no lo sea. Este
# limite amortigua esa caida. Es un suavizado de PRESENTACION/negocio sobre
# el pago, no un cambio en el calculo actuarial: la mesada asi ajustada SI
# se descuenta del saldo de la CAI (igual que el piso de crecimiento), asi
# que el fondo se agota mas rapido y la proyeccion se corta antes -- que es
# el comportamiento economico correcto.
CAIDA_MAXIMA_ANUAL_RP_DEFECTO = 0.50
# Factor de ajuste "NI" (No Informado): multiplicador sobre la Reserva
# Matematica RP, para corregir un factor actuarial no documentado que solo
# se manifiesta cuando la mesada de Renta Vitalicia (ya calculada,
# correctamente, sin cambios) coincide exactamente con la columna
# "Mesada_Actual_RP" de la base. Calibrado empiricamente (ver
# VALIDACION.md) sobre los 4 casos de
# base_cotizacion_prueba_7_casos.xlsx donde esto se cumple: el factor
# EXACTO necesario para que la reserva de RP, a la mesada de RV, iguale
# el capital disponible, vario entre 1.1531 y 1.2326 (promedio 1.1918).
# Se uso el promedio redondeado.
FACTOR_AJUSTE_NI_DEFECTO = 1.19
# Smith-Wilson: la curva de descuento de RP usa Interes Tecnico RP como el
# unico punto observado (año 1) y converge hacia este UFR para plazos largos.
SMITH_WILSON_UFR_DEFECTO = 0.03
SMITH_WILSON_ALPHA_DEFECTO = 0.10


@dataclass
class ParametrosActuariales:
    """Todos los parametros configurables desde la pagina Parametrizacion Actuarial."""

    vector_ipc_primer_anio: List[float] = field(default_factory=lambda: list(VECTOR_IPC_PRIMER_ANIO_DEFECTO))
    ipc_primer_anio: float = IPC_PRIMER_ANIO_DEFECTO
    ipc_segundo_anio: float = IPC_SEGUNDO_ANIO_DEFECTO
    ipc_objetivo_largo_plazo: float = IPC_OBJETIVO_LARGO_PLAZO_DEFECTO
    smlv: float = SMLV_DEFECTO
    delta_deslizamiento: float = DELTA_DESLIZAMIENTO_DEFECTO
    porcentaje_reserva_cambio_grupo: float = PORCENTAJE_RESERVA_CAMBIO_GRUPO_DEFECTO
    porcentaje_recargo_gastos_reserva: float = PORCENTAJE_RECARGO_GASTOS_RESERVA_DEFECTO
    porcentaje_recargo_gastos_prima: float = PORCENTAJE_RECARGO_GASTOS_PRIMA_DEFECTO
    metodo_iteracion: str = "secante"
    epsilon: float = EPSILON_DEFECTO
    max_iteraciones: int = MAX_ITERACIONES_DEFECTO
    paso_derivada: float = PASO_DERIVADA_DEFECTO
    tasa_equivalente_min: float = TASA_EQUIVALENTE_MIN_DEFECTO
    tasa_equivalente_max: float = TASA_EQUIVALENTE_MAX_DEFECTO
    # Curva MTM/TMR: lista de (año_nodo, tasa) tal como la carga el usuario.
    # Se expande a NODOS_CURVA_MTM (120) valores anuales con curva_expandida.
    curva_mtm_nodos: List[tuple] = field(default_factory=list)
    # Retiro Programado
    interes_tecnico_rp: float = INTERES_TECNICO_RP_DEFECTO
    deslizamiento_rp: float = DESLIZAMIENTO_RP_DEFECTO
    deslizamiento_rp_bajo: float = DESLIZAMIENTO_RP_BAJO_DEFECTO
    ipc_observado_rp: float = IPC_PRIMER_ANIO_DEFECTO
    gastos_rp: float = GASTOS_RP_DEFECTO
    tasa_crecimiento_cai: float = TASA_CRECIMIENTO_CAI_DEFECTO
    tasa_crecimiento_cai_volatilidad: float = TASA_CRECIMIENTO_CAI_VOLATILIDAD_DEFECTO
    castigo_riesgo_mercado_cai: float = CASTIGO_RIESGO_MERCADO_CAI_DEFECTO
    aplicar_condicion_rv_mayor: bool = APLICAR_CONDICION_RV_MAYOR_DEFECTO
    anio_inicio_condicion_rv: int = ANIO_INICIO_CONDICION_RV_DEFECTO
    max_anios_proyeccion_rp_tope: int = MAX_ANIOS_PROYECCION_RP_TOPE
    caida_maxima_anual_rp: float = CAIDA_MAXIMA_ANUAL_RP_DEFECTO
    factor_ajuste_ni: float = FACTOR_AJUSTE_NI_DEFECTO
    # Smith-Wilson (curva de descuento de RP, converge a smith_wilson_ufr)
    smith_wilson_ufr: float = SMITH_WILSON_UFR_DEFECTO
    smith_wilson_alpha: float = SMITH_WILSON_ALPHA_DEFECTO

    def curva_expandida(self) -> List[float]:
        """
        Expande curva_mtm_nodos (pares año-tasa, posiblemente dispersos o
        incompletos) a un arreglo de NODOS_CURVA_MTM (120) tasas, una por
        año 1..120 - equivalente a lo que el usuario pegaria manualmente en
        EG27:EG146 de la hoja EncontarTasaEquivalente.

        Regla: para cada año 1..120, se usa la tasa del nodo cargado en ese
        año exacto si existe; si no, se usa la tasa del nodo cargado
        inmediatamente anterior (se mantiene plana / "carry forward"); los
        años anteriores al primer nodo cargado usan la tasa del primer nodo.
        Esto replica el VLOOKUP de coincidencia exacta de la hoja: no hay
        interpolacion lineal entre nodos, se sostiene el ultimo valor
        conocido.
        """
        if not self.curva_mtm_nodos:
            return []
        nodos = sorted(self.curva_mtm_nodos, key=lambda x: x[0])
        mapa = {int(anio): float(tasa) for anio, tasa in nodos}
        primer_tasa = nodos[0][1]
        curva = []
        ultima = primer_tasa
        for anio in range(1, NODOS_CURVA_MTM + 1):
            if anio in mapa:
                ultima = mapa[anio]
            curva.append(ultima)
        return curva

    def curva_smith_wilson_rp(self) -> List[float]:
        """
        Curva de descuento de Retiro Programado: usa interes_tecnico_rp
        como el unico punto observado (año 1) y converge suavemente hacia
        smith_wilson_ufr para los años siguientes (modelo Smith-Wilson).
        Devuelve NODOS_CURVA_MTM (120) tasas anuales, una por año 1..120.
        """
        from .smith_wilson import curva_smith_wilson

        curva = curva_smith_wilson(
            tasas_observadas={1.0: self.interes_tecnico_rp},
            ufr=self.smith_wilson_ufr,
            alpha=self.smith_wilson_alpha,
            n_anios=NODOS_CURVA_MTM,
        )
        return list(curva)
