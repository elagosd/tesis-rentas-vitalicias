"""
Control de acceso muy simple, basado en una sola clave compartida, para
restringir paginas sensibles (por ahora: Parametrizacion Actuarial) a
personas del equipo de actuaria.

No es un sistema de usuarios real (no hay login por persona, ni roles, ni
auditoria de quien entro) - es solo una clave compartida para evitar que
cualquiera que abra la app pueda cambiar los supuestos actuariales por
accidente. Si mas adelante se necesita control por usuario, esto se debe
reemplazar por un mecanismo de autenticacion real (por ejemplo streamlit-
authenticator, o el SSO de la compañia).

La clave se define en .streamlit/secrets.toml (ver secrets.toml.ejemplo):

    actuario_password = "la-clave-que-elijan"

Si no existe ese archivo (por ejemplo en una instalacion nueva sin
configurar), se usa una clave por defecto y se muestra una advertencia
clara para que la cambien antes de compartir la app con mas personas.
"""

import streamlit as st

CLAVE_POR_DEFECTO = "actuaria2026"


def _clave_configurada() -> str:
    try:
        return st.secrets["actuario_password"]
    except (KeyError, FileNotFoundError, AttributeError):
        return CLAVE_POR_DEFECTO


def exigir_acceso_actuario(titulo_pagina: str = "esta pagina") -> None:
    """
    Muestra un formulario de clave y detiene la ejecucion del resto de la
    pagina (st.stop()) hasta que se ingrese la clave correcta. Una vez
    ingresada correctamente, queda guardada en session_state para el resto
    de la sesion del navegador (no hay que volver a escribirla en cada
    rerun de Streamlit).
    """
    if st.session_state.get("acceso_actuario_ok"):
        return

    clave_correcta = _clave_configurada()

    st.title("Acceso restringido")
    st.write(f"Solo el equipo de actuaria puede entrar a {titulo_pagina}.")

    if clave_correcta == CLAVE_POR_DEFECTO:
        st.warning(
            "Esta instalacion todavia usa la clave por defecto. Antes de "
            "compartir la app, define tu propia clave en "
            "`.streamlit/secrets.toml` (ver secrets.toml.ejemplo)."
        )

    clave_ingresada = st.text_input("Clave de acceso", type="password")
    if st.button("Entrar"):
        if clave_ingresada == clave_correcta:
            st.session_state["acceso_actuario_ok"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")

    st.stop()
