# -*- coding: utf-8 -*-
"""Rutas del proyecto, relativas a la ubicacion de este archivo.

Permiten ejecutar los scripts desde cualquier carpeta y en cualquier
sistema operativo. Las bases de polizas se buscan primero en
``datos_privados/`` (no se publica) y, si no estan, se usan las bases
ficticias de ``py/cotizador/ejemplos/``.
"""
import sys
from pathlib import Path

PY = Path(__file__).resolve().parent
RAIZ = PY.parent
COTIZADOR = PY / "cotizador"
SAL = RAIZ / "salidas"
TEX = RAIZ / "tex"
FIGURAS = TEX / "figuras"
TABLAS = TEX / "tablas"
PRIVADOS = RAIZ / "datos_privados"
EJEMPLOS = COTIZADOR / "ejemplos"

for _carpeta in (SAL, FIGURAS, TABLAS):
    _carpeta.mkdir(parents=True, exist_ok=True)

if str(COTIZADOR) not in sys.path:
    sys.path.insert(0, str(COTIZADOR))


def _base(nombre_privado: str, nombre_ejemplo: str) -> str:
    privada = PRIVADOS / nombre_privado
    return str(privada if privada.exists() else EJEMPLOS / nombre_ejemplo)


# Cotizaciones de renta vitalicia y registros con informacion de retiro programado
BASE_RV = _base("base_polizas_10_polizas.xlsx", "base_polizas_ejemplo.xlsx")
BASE_RP = _base("base_cotizacion_prueba_7_casos.xlsx", "base_cotizacion_ejemplo.xlsx")
USA_DATOS_PRIVADOS = (PRIVADOS / "base_polizas_10_polizas.xlsx").exists()
