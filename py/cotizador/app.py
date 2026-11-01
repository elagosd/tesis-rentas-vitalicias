"""
Cotizador - App principal.

Paginas (ver carpeta pages/):
1) Parametrizacion Actuarial (acceso restringido)
2) Masivo EncontrarMesada
3) Masivo Encontrar Tasa Equivalente
4) Historial

Ejecutar con: streamlit run app.py
"""

import streamlit as st

from core.estado import obtener_parametros

st.set_page_config(page_title="Cotizador", layout="wide")

st.title("Cotizador")
st.write(
    "Herramienta para encontrar la mesada pensional a partir de un capital "
    "asegurado (KA) o de una curva de interes MTM/TMR, replicando las hojas "
    "**EncontrarMesada** y **EncontarTasaEquivalente** del Excel de nota "
    "tecnica."
)

st.markdown(
    """
    Usa el menu de la izquierda para navegar:

    1. **Parametrizacion Actuarial** *(acceso restringido)*: define IPC,
       SMLV, deslizamiento, curva MTM/TMR, recargos y el metodo de
       iteracion (por defecto: secante). Incluye los calculos individuales
       de mesada, tasa equivalente y retiro programado.
    2. **Masivo EncontrarMesada**: carga la base de calculo (cedulas) y
       encuentra la mesada de cada una, con graficos individuales y
       estadisticos de toda la base.
    3. **Masivo Encontrar Tasa Equivalente**: calculo de la tasa
       equivalente y de la mesada para toda la base, a partir de la curva
       MTM/TMR.
    4. **Historial**: parametrizaciones guardadas, calculos realizados y
       proyecciones por año.
    """
)

params = obtener_parametros()
if st.session_state.get("parametros_vienen_de_disco"):
    st.caption("Parametrizacion actuarial cargada automaticamente desde el ultimo guardado.")
else:
    st.caption("Usando la parametrizacion actuarial por defecto (nadie ha guardado una todavia).")

st.info(
    "Estado actual del motor de calculo: validado contra el Excel en la "
    "tasa de descuento tecnico y el crecimiento de la mesada (0 diferencia). "
    "La mortalidad conjunta tiene un desfase de ~0.2%-0.4% en la reserva/"
    "prima, localizado unicamente en el tramo final de la tabla (edades "
    "~110+ años), pendiente de cerrar. Ver VALIDACION.md."
)
