"""
Mapeo entre las columnas/codigos de la base masiva REAL
(base_polizas_10_polizas.xlsx, 116 columnas, encabezados en fila 1) y los
codigos que usa el motor actuarial (core/motor.py, core/mortalidad.py).

Confirmado contra el archivo base_polizas_10_polizas.xlsx el 2026-08-04.
Reemplaza el mapeo anterior (basado en la hoja Resultados_PrimaComercial del
Excel de nota tecnica), que ya no se usa.
"""

# --- Genero: la base usa cod_genero 1=Masculino, 0=Femenino ---
# El motor usa sexo: 1=Masculino, 2=Femenino
def cod_genero_a_sexo(cod_genero) -> int:
    if cod_genero is None or cod_genero == "" or (isinstance(cod_genero, float) and cod_genero != cod_genero):
        return 0
    return 1 if int(cod_genero) == 1 else 2


# --- Estado: coincide 1:1 entre la base y el motor ---
# cod_estado observado en la base: 1=VALIDO, 3=MUERTO (tambien existe 2=INVALIDO)
def cod_estado_a_estado(cod_estado) -> int:
    if cod_estado is None or cod_estado == "" or (isinstance(cod_estado, float) and cod_estado != cod_estado):
        return 0
    return int(cod_estado)


# --- Parentesco: la base trae el texto en la columna parentesco_N
# (CAUSANTE, CONYUGE, COMPANERO/A, HIJO/A, y potencialmente MADRE/PADRE/
# HERMANO). Se usa el texto porque es inequivoco; cod_parentesco_N usa una
# codificacion propia de esta base (0=causante,1=conyuge,2=companero/a,
# 3=hijo/a) que no coincide con los codigos del motor, asi que no se usa
# directamente. ---
MAPA_PARENTESCO_TEXTO_A_CODIGO = {
    "CAUSANTE": 1,
    "CONYUGE": 4,
    "CÓNYUGE": 4,
    "COMPANERO/A": 4,
    "COMPAÑERO/A": 4,
    "MADRE": 6,
    "PADRE": 5,
    "HIJO/A": 2,
    "HIJO": 2,
    "HERMANO": 6,
    "HERMANO/A": 6,
    "CONYUGE TEMPORAL": 7,
    "CÓNYUGE TEMPORAL": 7,
    0: 0,
    "0": 0,
}


def parentesco_texto_a_codigo(texto) -> int:
    if texto is None or texto == "" or (isinstance(texto, float) and texto != texto):
        return 0
    if isinstance(texto, (int, float)):
        return int(texto)
    return MAPA_PARENTESCO_TEXTO_A_CODIGO.get(str(texto).strip().upper(), 0)


# --- Columnas relevantes de la base masiva real (base_polizas_10_polizas.xlsx) ---
# Se usan directamente desde el archivo cargado por el usuario en la pagina Masivo.
# Los campos gastos_de_expedicion, gastos_de_administracion, ajuste_beneficiarios,
# factor_deslizamiento e IPC_12_meses que trae la base NO se usan: esos valores
# se toman de la pagina Parametrizacion Actuarial (globales para toda la corrida).
# tipo_calculo tampoco se usa: este proyecto siempre resuelve
# Reserva_Matematica(mesada) = capital_renta (equivalente a tipo_calculo="CAPITAL").
COLUMNAS_BASE_REQUERIDAS = [
    "id_cotizacion",     # identificador de la cotizacion
    "id_0",              # cedula del causante, usada para identificar cada registro en la UI
    "mesada",            # mesada actual (semilla)
    "no_mesada",         # numero de mesadas (13 o 14)
    "capital_renta",     # capital asegurado (KA), el objetivo a igualar
    "it_emision",        # tasa de interes real, ya en formato decimal (ej 0.0408 = 4.08%)
    "fecha_inicio_vigencia",  # fecha de valoracion
    "fecha_nacimiento_0", "cod_genero_0", "cod_estado_0", "parentesco_0",  # causante
]

# Beneficiarios 1 a 9 (columnas fecha_nacimiento_N, cod_genero_N, cod_estado_N,
# parentesco_N), todas opcionales: si no hay datos para el beneficiario N se omite.
MAX_BENEFICIARIOS_BASE = 9
