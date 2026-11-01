"""
Punto unico para obtener la Parametrizacion Actuarial vigente en cualquier
pagina. Si el navegador ya la tiene en session_state (porque la persona ya
navego por la app en esta sesion), se usa esa. Si no (primera vez que se
abre la app, o se reinicio el servidor), se intenta cargar la ULTIMA
parametrizacion guardada en disco (data/historial.db); si nunca se ha
guardado nada, se usan los valores por defecto de config.py.
"""

import streamlit as st

from . import config, persistencia


def obtener_parametros() -> "config.ParametrosActuariales":
    if "parametros" in st.session_state:
        return st.session_state["parametros"]

    guardados = persistencia.cargar_ultima_parametrizacion()
    params = guardados if guardados is not None else config.ParametrosActuariales()
    st.session_state["parametros"] = params
    st.session_state["parametros_vienen_de_disco"] = guardados is not None
    return params
