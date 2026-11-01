# -*- coding: utf-8 -*-
"""
Extrae, del código fuente, los fragmentos que se reproducen en el apéndice de
listados de la tesis.

Se hace con un script y no copiando y pegando a mano para que los listados del
documento no puedan divergir nunca del código que efectivamente se ejecutó: si
el código cambia, basta volver a correr este archivo.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ.parent / "tex" / "codigo"
DESTINO.mkdir(exist_ok=True)


def extraer(ruta: Path, desde: str, hasta: str | None = None,
            encabezado: str = "") -> str:
    """Devuelve el bloque de `ruta` que va desde la línea que contiene `desde`
    hasta (sin incluir) la que contiene `hasta`."""
    texto = ruta.read_text(encoding="utf-8")
    i = texto.index(desde)
    j = texto.index(hasta, i) if hasta else len(texto)
    cuerpo = texto[i:j].rstrip() + "\n"
    return (encabezado + "\n" if encabezado else "") + cuerpo


def escribir(nombre: str, contenido: str):
    (DESTINO / nombre).write_text(contenido, encoding="utf-8")
    n = contenido.count("\n")
    print(f"  {nombre:<34} {n:>5} líneas")


CORE = RAIZ / "cotizador" / "core"

print("Extractos de código para el apéndice:")

# --- 1. Derivadas laterales exactas (aporte central sobre el motor) ---
escribir("derivada_exacta.py", extraer(
    CORE / "motor.py",
    "    # --- Derivadas laterales exactas de la Reserva Matematica (opcional) ---",
    "    # Los componentes de la proyeccion de flujos se guardan SIEMPRE",
    encabezado="# Fragmento de core/motor.py :: calcular_reserva(...)\n"
               "# Se ejecuta solo cuando se invoca con calcular_derivada=True.",
))

# --- 2. Instrumentación del catálogo ---
escribir("instrumentacion.py", extraer(
    CORE / "metodos_iterativos.py",
    "class ContadorFuncion:",
    "@dataclass\nclass CriterioParada:",
    encabezado="# Fragmento de core/metodos_iterativos.py: instrumentación común.",
))

# --- 3. Métodos representativos, uno por familia ---
escribir("metodo_biseccion.py", extraer(
    CORE / "metodos_iterativos.py",
    "def biseccion(f, a: float, b: float,",
    "def _regula_falsi_generico(",
    encabezado="# core/metodos_iterativos.py :: familia de encaje",
))

escribir("metodo_regula_falsi.py", extraer(
    CORE / "metodos_iterativos.py",
    "def _regula_falsi_generico(",
    "def regula_falsi(f, a, b,",
    encabezado="# core/metodos_iterativos.py :: regula falsi y sus tres correcciones",
))

escribir("metodo_itp.py", extraer(
    CORE / "metodos_iterativos.py",
    "def itp(f, a, b,",
    "# =====================================================================\n"
    "# B. METODOS ABIERTOS",
    encabezado="# core/metodos_iterativos.py :: ITP (Oliveira y Takahashi, 2021)",
))

escribir("metodo_secante.py", extraer(
    CORE / "metodos_iterativos.py",
    "def secante(f, x0: float, x1: float,",
    "def newton_diferencias(",
    encabezado="# core/metodos_iterativos.py :: familia de métodos abiertos",
))

escribir("metodo_newton.py", extraer(
    CORE / "metodos_iterativos.py",
    "def newton_diferencias(",
    "def steffensen(f, x0: float,",
    encabezado="# core/metodos_iterativos.py :: Newton con diferencias finitas\n"
               "# y Newton con derivada analítica exacta",
))

escribir("metodo_semisuave.py", extraer(
    CORE / "metodos_iterativos.py",
    "def newton_semisuave(",
    "# =====================================================================\n"
    "# Registro del catalogo",
    encabezado="# core/metodos_iterativos.py :: métodos para el caso no suave",
))

# --- 4. Estimación robusta del orden de convergencia ---
escribir("estimacion_orden.py", extraer(
    CORE / "metodos_iterativos.py",
    "    def estimar_orden(self, raiz_referencia: float)",
    "    def indice_eficiencia(self, raiz_referencia: float)",
    encabezado="# core/metodos_iterativos.py :: ResultadoIteracion\n"
               "# Estimadores del orden y de la razón de convergencia.",
))

# --- 5. Construcción de la función objetivo y del B-subdiferencial ---
escribir("objetivo.py", extraer(
    CORE / "problema_tesis.py",
    "class ObjetivoActuarial:",
    "def valor_y_derivada(",
    encabezado="# core/problema_tesis.py :: construcción de f y de su subdiferencial",
))

# --- 6. Capital mínimo y detección de quiebres ---
escribir("capital_minimo.py", extraer(
    CORE / "problema_tesis.py",
    "def capital_minimo(",
    None,
    encabezado="# core/problema_tesis.py :: verificación numérica de la estructura",
))

# --- 7. Banco de pruebas ---
escribir("banco_pruebas.py", extraer(
    CORE / "banco_pruebas.py",
    "def ejecutar_catalogo(",
    "def resumen_por_metodo(",
    encabezado="# core/banco_pruebas.py :: protocolo de comparación",
))

# --- 8. Recursión de retiro programado ---
escribir("retiro_programado.py", extraer(
    CORE / "retiro_programado.py",
    "    for indice_anio in range(max_anios):",
    "    return pd.DataFrame(filas)",
    encabezado="# Fragmento de core/retiro_programado.py :: proyectar_rp_dinamico_cai\n"
               "# Bucle principal de la recursión año a año.",
))

print("\nListo. Los listados del apéndice se leen directamente de tex/codigo/.")
