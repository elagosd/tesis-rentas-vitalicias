"""
Formularios reutilizables de Streamlit para las secciones individuales
(Encontrar Mesada y Encontrar Tasa Equivalente dentro de Parametrizacion
Actuarial).
"""

from datetime import date

import streamlit as st

from . import config
from .motor import Persona

OPCIONES_TIPO_BENEFICIARIO = [
    ("Hijo(a)", 2),
    ("Conyuge/Compañero(a)", 4),
    ("Padre", 5),
    ("Madre", 6),
    ("Compañero(a) menor 30 (conyuge temporal)", 7),
]

OPCIONES_SEXO = [("Masculino", 1), ("Femenino", 2)]
OPCIONES_ESTADO = [("Valido(a)", 1), ("Invalido(a)", 2), ("Muerto(a)", 3)]

# Rango amplio de fechas de nacimiento seleccionables (Streamlit, si no se le
# pasan min_value/max_value, limita el calendario a solo +/-10 años del
# "value" inicial -- por eso hay que ser explicito aqui).
FECHA_NACIMIENTO_MIN = date(1800, 1, 1)
FECHA_NACIMIENTO_MAX = date.today()


def formulario_causante(key_prefix: str) -> Persona:
    st.subheader("Causante")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_nac = st.date_input(
            "Fecha de nacimiento (causante)", value=date(1960, 1, 1),
            min_value=FECHA_NACIMIENTO_MIN, max_value=FECHA_NACIMIENTO_MAX,
            key=f"{key_prefix}_causante_fn",
        )
    with col2:
        sexo = st.selectbox("Sexo (causante)", options=OPCIONES_SEXO, format_func=lambda x: x[0], key=f"{key_prefix}_causante_sexo")[1]
    with col3:
        estado = st.selectbox("Estado (causante)", options=OPCIONES_ESTADO, format_func=lambda x: x[0], key=f"{key_prefix}_causante_estado")[1]
    return Persona(fecha_nacimiento=fecha_nac, tipo_beneficiario=1, sexo=sexo, estado=estado)


def formulario_beneficiarios(key_prefix: str, max_beneficiarios: int = config.MAX_BENEFICIARIOS) -> list:
    """Selector desplegable de cuantos beneficiarios hay (0..max_beneficiarios,
    por defecto 9) y un formulario por cada uno."""
    st.subheader("Beneficiarios")
    n_beneficiarios = st.selectbox(
        "Numero de beneficiarios",
        options=list(range(0, max_beneficiarios + 1)),
        index=0,
        key=f"{key_prefix}_n_beneficiarios",
    )

    beneficiarios = []
    for n in range(1, n_beneficiarios + 1):
        with st.expander(f"Beneficiario {n}", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                tipo = st.selectbox(
                    "Tipo", options=OPCIONES_TIPO_BENEFICIARIO, format_func=lambda x: x[0], key=f"{key_prefix}_ben_tipo_{n}"
                )[1]
            with c2:
                fecha_nac = st.date_input(
                    "Fecha de nacimiento", value=date(1990, 1, 1),
                    min_value=FECHA_NACIMIENTO_MIN, max_value=FECHA_NACIMIENTO_MAX,
                    key=f"{key_prefix}_ben_fn_{n}",
                )
            with c3:
                sexo = st.selectbox("Sexo", options=OPCIONES_SEXO, format_func=lambda x: x[0], key=f"{key_prefix}_ben_sexo_{n}")[1]
            with c4:
                estado = st.selectbox("Estado", options=OPCIONES_ESTADO, format_func=lambda x: x[0], key=f"{key_prefix}_ben_estado_{n}")[1]
            beneficiarios.append(Persona(fecha_nacimiento=fecha_nac, tipo_beneficiario=tipo, sexo=sexo, estado=estado))

    return beneficiarios
