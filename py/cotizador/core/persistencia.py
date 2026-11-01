"""
Persistencia en disco del proyecto "cotizador".

Usa SQLite (viene incluido en Python, no requiere instalar nada) para tres
cosas:

1. `parametrizacion_historial`: cada vez que se guarda la Parametrizacion
   Actuarial (vector IPC, curva MTM/TMR, SMLV, etc.) se agrega una fila
   nueva con un snapshot completo en JSON. Nunca se sobreescribe una
   version anterior -- asi queda el historial de cada actualizacion del
   IPC y de la TMR. Al abrir la app se carga automaticamente la ULTIMA
   fila guardada.

2. `calculos`: cada vez que se corre un calculo (individual o masivo, de
   mesada o de tasa equivalente) se guarda una fila por cedula con el
   input y el output completos (en JSON), mas algunas columnas sueltas
   (cedula, pagina, fecha) para poder filtrar facil.

3. `proyecciones_mesada`: cada vez que se corre un calculo masivo, se
   guarda ademas la proyeccion de mesada por año, para AMBOS productos
   (Renta Vitalicia y Retiro Programado), de CADA cedula de la base (no
   solo la que se ve en el grafico) -- ver core/proyecciones_masivo.py.
   Cada corrida masiva tiene un corrida_id propio para poder filtrarla sin
   mezclarla con corridas anteriores.

El archivo de base de datos vive en data/historial.db, dentro de la
carpeta del proyecto (se sincroniza solo si el proyecto esta en una
carpeta de OneDrive, como suele ser el caso aqui).
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from . import config

RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "historial.db"


@contextmanager
def _conexion():
    RUTA_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(RUTA_DB)
    try:
        _crear_tablas(con)
        yield con
        con.commit()
    finally:
        con.close()


def _crear_tablas(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS parametrizacion_historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            parametros_json TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS calculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            pagina TEXT NOT NULL,
            cedula TEXT,
            id_cotizacion TEXT,
            entrada_json TEXT NOT NULL,
            salida_json TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS proyecciones_mesada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            corrida_id TEXT NOT NULL,
            pagina TEXT NOT NULL,
            cedula TEXT,
            id_cotizacion TEXT,
            producto TEXT NOT NULL,
            anio INTEGER NOT NULL,
            mesada_proyectada REAL NOT NULL,
            convergio INTEGER NOT NULL
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_proyecciones_corrida ON proyecciones_mesada(corrida_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_proyecciones_cedula ON proyecciones_mesada(cedula)"
    )


# --- Parametrizacion (IPC, TMR, SMLV, etc.) ---------------------------------

def guardar_parametrizacion(params: "config.ParametrosActuariales") -> None:
    """Agrega una fila nueva al historial (nunca sobreescribe una anterior)."""
    datos = asdict(params)
    with _conexion() as con:
        con.execute(
            "INSERT INTO parametrizacion_historial (fecha_hora, parametros_json) VALUES (?, ?)",
            (datetime.now().isoformat(timespec="seconds"), json.dumps(datos)),
        )


def _migrar_parametros(datos: dict) -> dict:
    """
    Adapta una parametrizacion guardada en disco (posiblemente de una
    version anterior de la app) a la forma actual de
    config.ParametrosActuariales:

    1. Descarta llaves que ya no existen en el dataclass -- sin esto,
       renombrar o eliminar un parametro rompe la carga de todo lo ya
       guardado (TypeError: unexpected keyword argument).
    2. Rellena con los valores por defecto los parametros NUEVOS que la
       parametrizacion vieja no tenia (esto lo hace solo el dataclass).
    3. Horizonte de proyeccion: si el guardado trae exactamente el default
       ANTERIOR (40 años), se entiende que nadie lo cambio a proposito y se
       actualiza al default nuevo (20 años, ver
       config.MAX_ANIOS_PROYECCION_RP_TOPE). Si trae cualquier otro valor,
       se respeta -- alguien lo eligio.
    """
    campos_validos = {f.name for f in fields(config.ParametrosActuariales)}
    datos = {k: v for k, v in datos.items() if k in campos_validos}
    datos["curva_mtm_nodos"] = [tuple(x) for x in datos.get("curva_mtm_nodos", [])]

    if datos.get("max_anios_proyeccion_rp_tope") == config.MAX_ANIOS_PROYECCION_RP_TOPE_LEGACY:
        datos["max_anios_proyeccion_rp_tope"] = config.MAX_ANIOS_PROYECCION_RP_TOPE

    return datos


def cargar_ultima_parametrizacion() -> Optional["config.ParametrosActuariales"]:
    """Devuelve la ultima Parametrizacion Actuarial guardada, o None si nunca se ha guardado nada."""
    with _conexion() as con:
        fila = con.execute(
            "SELECT parametros_json FROM parametrizacion_historial ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if fila is None:
        return None
    return config.ParametrosActuariales(**_migrar_parametros(json.loads(fila[0])))


def cargar_parametrizacion_por_id(id_historial: int) -> Optional["config.ParametrosActuariales"]:
    with _conexion() as con:
        fila = con.execute(
            "SELECT parametros_json FROM parametrizacion_historial WHERE id = ?", (id_historial,)
        ).fetchone()
    if fila is None:
        return None
    return config.ParametrosActuariales(**_migrar_parametros(json.loads(fila[0])))


def listar_historial_parametrizacion(limite: int = 100) -> pd.DataFrame:
    """Tabla resumen del historial (una fila por cada vez que se guardo), mas reciente primero."""
    with _conexion() as con:
        df = pd.read_sql_query(
            "SELECT id, fecha_hora, parametros_json FROM parametrizacion_historial ORDER BY id DESC LIMIT ?",
            con, params=(limite,),
        )
    if df.empty:
        return df

    def _resumen(js):
        d = json.loads(js)
        n_nodos = len(d.get("curva_mtm_nodos", []))
        return pd.Series({
            "ipc_primer_anio_%": round(_ipc_primer_anio(d) * 100, 4),
            "ipc_segundo_anio_%": round(d.get("ipc_segundo_anio", 0) * 100, 4),
            "smlv": d.get("smlv"),
            "deslizamiento_%": round(d.get("delta_deslizamiento", 0) * 100, 4),
            "nodos_tmr_cargados": n_nodos,
            "metodo_iteracion": d.get("metodo_iteracion"),
        })

    resumen = df["parametros_json"].apply(_resumen)
    return pd.concat([df[["id", "fecha_hora"]], resumen], axis=1)


def _ipc_primer_anio(d: dict) -> float:
    producto = 1.0
    for v in d.get("vector_ipc_primer_anio", []):
        producto *= (1 + v)
    return producto - 1


# --- Historial de calculos (input + output) ---------------------------------

def registrar_calculo(pagina: str, cedula: str, id_cotizacion: str, entrada: dict, salida: dict) -> None:
    with _conexion() as con:
        con.execute(
            "INSERT INTO calculos (fecha_hora, pagina, cedula, id_cotizacion, entrada_json, salida_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                pagina,
                cedula,
                id_cotizacion,
                json.dumps(entrada, default=str),
                json.dumps(salida, default=str),
            ),
        )


def registrar_calculos_masivo(pagina: str, base: pd.DataFrame, resultados: pd.DataFrame) -> None:
    """
    Guarda una fila por cedula con el input (la fila de la base que se
    cargo) y el output (la fila de resultados calculada). Se usa despues
    de correr un calculo masivo (mesada o tasa equivalente).
    """
    base_por_cedula = {}
    if "id_0" in base.columns:
        for _, fila in base.iterrows():
            clave = str(int(fila["id_0"])) if pd.notna(fila.get("id_0")) else str(fila.get("id_cotizacion"))
            base_por_cedula[clave] = fila.to_dict()

    fecha = datetime.now().isoformat(timespec="seconds")
    filas = []
    for _, salida in resultados.iterrows():
        salida_dict = salida.to_dict()
        cedula = str(salida_dict.get("cedula", ""))
        id_cotizacion = str(salida_dict.get("id_cotizacion", ""))
        entrada_dict = base_por_cedula.get(cedula, {})
        filas.append((fecha, pagina, cedula, id_cotizacion, json.dumps(entrada_dict, default=str), json.dumps(salida_dict, default=str)))

    with _conexion() as con:
        con.executemany(
            "INSERT INTO calculos (fecha_hora, pagina, cedula, id_cotizacion, entrada_json, salida_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            filas,
        )


def obtener_historial_calculos(pagina: Optional[str] = None, limite: int = 1000) -> pd.DataFrame:
    with _conexion() as con:
        if pagina:
            df = pd.read_sql_query(
                "SELECT * FROM calculos WHERE pagina = ? ORDER BY id DESC LIMIT ?",
                con, params=(pagina, limite),
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM calculos ORDER BY id DESC LIMIT ?", con, params=(limite,)
            )
    return df


# Paginas que corresponden a corridas MASIVAS (no individuales) en la tabla
# 'calculos' -- deben coincidir con el string `pagina` que usan
# registrar_calculos_masivo en pages/2_Masivo_EncontrarMesada.py y
# pages/3_Masivo_Encontrar_Tasa_Equivalente.py.
PAGINAS_CALCULOS_MASIVOS = ("masivo_mesada", "masivo_tasa_equivalente")


def eliminar_calculos_masivos() -> int:
    """
    Elimina TODAS las filas de 'calculos' cuya pagina sea una corrida
    masiva (PAGINAS_CALCULOS_MASIVOS) -- deja intactos los calculos
    individuales (Encontrar Tasa Equivalente, Retiro Programado, etc.).
    Devuelve el numero de filas eliminadas. No se puede deshacer.
    """
    placeholders = ",".join("?" for _ in PAGINAS_CALCULOS_MASIVOS)
    with _conexion() as con:
        cursor = con.execute(
            f"DELETE FROM calculos WHERE pagina IN ({placeholders})",
            PAGINAS_CALCULOS_MASIVOS,
        )
        return cursor.rowcount


# --- Proyecciones de mesada por cedula, año y producto (RV / RP) -----------

def registrar_proyecciones_mesada(
    pagina: str,
    corrida_id: str,
    filas_proyeccion: list,
) -> None:
    """
    Guarda en bloque las proyecciones de mesada por año, cedula y producto.

    filas_proyeccion: lista de tuplas
    (cedula, id_cotizacion, producto, anio, mesada_proyectada, convergio),
    donde producto es "renta_vitalicia" o "retiro_programado".

    corrida_id identifica una corrida masiva completa (todas las filas de
    una misma corrida comparten el mismo corrida_id), para poder filtrar
    "la ultima corrida" sin mezclar corridas distintas.
    """
    if not filas_proyeccion:
        return
    fecha = datetime.now().isoformat(timespec="seconds")
    filas = [
        (fecha, corrida_id, pagina, cedula, id_cotizacion, producto, int(anio), float(mesada), int(bool(convergio)))
        for (cedula, id_cotizacion, producto, anio, mesada, convergio) in filas_proyeccion
    ]
    with _conexion() as con:
        con.executemany(
            "INSERT INTO proyecciones_mesada "
            "(fecha_hora, corrida_id, pagina, cedula, id_cotizacion, producto, anio, mesada_proyectada, convergio) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            filas,
        )


def obtener_proyecciones_mesada(
    pagina: Optional[str] = None,
    cedula: Optional[str] = None,
    corrida_id: Optional[str] = None,
    limite: int = 20000,
) -> pd.DataFrame:
    """Consulta las proyecciones guardadas, con filtros opcionales."""
    condiciones = []
    valores = []
    if pagina:
        condiciones.append("pagina = ?")
        valores.append(pagina)
    if cedula:
        condiciones.append("cedula = ?")
        valores.append(cedula)
    if corrida_id:
        condiciones.append("corrida_id = ?")
        valores.append(corrida_id)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    valores.append(limite)
    with _conexion() as con:
        df = pd.read_sql_query(
            f"SELECT * FROM proyecciones_mesada {where} ORDER BY id DESC LIMIT ?",
            con, params=tuple(valores),
        )
    return df


def listar_corridas_proyecciones(limite: int = 50) -> pd.DataFrame:
    """Resumen de corridas masivas que tienen proyecciones guardadas (para elegir cual ver/exportar)."""
    with _conexion() as con:
        df = pd.read_sql_query(
            "SELECT corrida_id, pagina, MIN(fecha_hora) AS fecha_hora, "
            "COUNT(DISTINCT cedula) AS n_cedulas, COUNT(*) AS n_filas "
            "FROM proyecciones_mesada GROUP BY corrida_id, pagina "
            "ORDER BY fecha_hora DESC LIMIT ?",
            con, params=(limite,),
        )
    return df
