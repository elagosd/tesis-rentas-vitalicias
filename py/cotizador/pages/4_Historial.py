"""
Pagina 5: Historial.

Muestra lo que quedo guardado en data/historial.db:
- Cada calculo corrido (individual o masivo, de mesada o de tasa
  equivalente), con su input y su output completos.
- Las proyecciones de mesada por año (Renta Vitalicia y Retiro Programado),
  cedula por cedula, de cada corrida masiva.
- El historial de actualizaciones de la Parametrizacion Actuarial (IPC,
  TMR, etc.) -- resumen; el detalle completo esta en la pagina 1.

Permite filtrar por pagina/tipo de calculo y descargar el resultado en CSV.
"""

import json

import pandas as pd
import streamlit as st

from core import persistencia

st.title("Historial")
st.caption(f"Base de datos: `{persistencia.RUTA_DB}`")

tab_calculos, tab_proyecciones, tab_parametrizacion = st.tabs(
    ["Calculos (input/output)", "Proyecciones por año (RV / RP)", "Parametrizacion actuarial"]
)

with tab_calculos:
    with st.expander("🗑️ Limpiar todas las corridas masivas"):
        st.caption(
            "Borra TODOS los calculos guardados de 'Masivo EncontrarMesada' y 'Masivo Encontrar "
            "Tasa Equivalente'. Los calculos individuales (Encontrar Tasa Equivalente, Retiro "
            "Programado, etc.) NO se tocan. Esta accion no se puede deshacer."
        )
        if "confirmar_limpieza_masivos" not in st.session_state:
            st.session_state["confirmar_limpieza_masivos"] = False

        if not st.session_state["confirmar_limpieza_masivos"]:
            if st.button("Limpiar todas las corridas masivas"):
                st.session_state["confirmar_limpieza_masivos"] = True
                st.rerun()
        else:
            st.warning("¿Seguro? Esto borra permanentemente todas las corridas masivas guardadas.")
            col_confirmar, col_cancelar = st.columns(2)
            with col_confirmar:
                if st.button("Si, borrar todo", type="primary", key="confirmar_borrado_masivos"):
                    n_borradas = persistencia.eliminar_calculos_masivos()
                    st.session_state["confirmar_limpieza_masivos"] = False
                    st.success(f"Se borraron {n_borradas} corridas masivas del historial.")
                    st.rerun()
            with col_cancelar:
                if st.button("Cancelar", key="cancelar_borrado_masivos"):
                    st.session_state["confirmar_limpieza_masivos"] = False
                    st.rerun()

    opciones_pagina = {
        "Todas": None,
        "Masivo EncontrarMesada": "masivo_mesada",
        "Individual Tasa Equivalente": "individual_tasa_equivalente",
        "Masivo Tasa Equivalente": "masivo_tasa_equivalente",
        "Individual Retiro Programado": "individual_retiro_programado",
    }
    seleccion = st.selectbox("Filtrar por pagina", options=list(opciones_pagina.keys()))
    limite = st.number_input("Maximo de filas a mostrar", min_value=10, max_value=20000, value=500, step=100)

    df = persistencia.obtener_historial_calculos(pagina=opciones_pagina[seleccion], limite=int(limite))

    if df.empty:
        st.info("Todavia no hay calculos guardados. Corre un calculo en alguna de las paginas y vuelve aqui.")
    else:
        st.write(f"{len(df)} filas.")
        st.dataframe(df[["id", "fecha_hora", "pagina", "cedula", "id_cotizacion"]], width='stretch')

        st.download_button(
            "Descargar todo (CSV, incluye input/output en columnas JSON)",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="historial_calculos.csv",
        )

        st.divider()
        st.subheader("Ver el detalle de una fila")
        id_detalle = st.selectbox("Elige el id de la fila", options=df["id"].tolist())
        fila = df[df["id"] == id_detalle].iloc[0]
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Input**")
            st.json(json.loads(fila["entrada_json"]))
        with col2:
            st.write("**Output**")
            st.json(json.loads(fila["salida_json"]))

with tab_proyecciones:
    st.caption(
        "Proyeccion de mesada por año, cedula por cedula, para Renta Vitalicia y Retiro "
        "Programado, guardada automaticamente cada vez que se corre un calculo masivo (paginas "
        "'Masivo EncontrarMesada' y 'Masivo Encontrar Tasa Equivalente')."
    )

    corridas = persistencia.listar_corridas_proyecciones()
    if corridas.empty:
        st.info(
            "Todavia no hay proyecciones guardadas. Corre 'Calcular mesada para toda la base' en "
            "alguna de las paginas Masivo y vuelve aqui."
        )
    else:
        # La corrida se identifica en pantalla UNICAMENTE por su fecha y
        # hora (peticion del usuario): el corrida_id es un hash interno que
        # no le dice nada a nadie. Se sigue usando por debajo como llave de
        # filtrado -- es lo que garantiza que dos corridas distintas no se
        # mezclen -- pero no se muestra ni se exporta.
        corridas_vista = corridas.copy()
        corridas_vista["fecha_hora"] = corridas_vista["fecha_hora"].str.replace("T", " ", regex=False)
        st.dataframe(
            corridas_vista[["fecha_hora", "pagina", "n_cedulas", "n_filas"]],
            width='stretch', hide_index=True,
        )

        # Etiqueta visible -> corrida_id real. La etiqueta DEBE ser unica: es
        # la llave del selectbox, asi que si dos corridas generaran la misma
        # una de ellas desapareceria del filtro sin aviso. fecha_hora se
        # guarda con precision de SEGUNDOS, asi que dos corridas seguidas si
        # pueden coincidir. Se desempata primero con la pagina de origen y,
        # si aun asi coinciden (dos corridas de la misma pagina en el mismo
        # segundo), con un consecutivo.
        etiquetas_por_corrida = {}
        repetidas = corridas_vista["fecha_hora"].duplicated(keep=False)
        for i, fila_corrida in corridas_vista.iterrows():
            etiqueta = fila_corrida["fecha_hora"]
            if repetidas.loc[i]:
                etiqueta = f"{etiqueta} ({fila_corrida['pagina']})"
            etiqueta_base = etiqueta
            consecutivo = 2
            while etiqueta in etiquetas_por_corrida:
                etiqueta = f"{etiqueta_base} #{consecutivo}"
                consecutivo += 1
            etiquetas_por_corrida[etiqueta] = fila_corrida["corrida_id"]

        opciones_corrida = ["Todas las corridas"] + list(etiquetas_por_corrida.keys())
        corrida_elegida = st.selectbox("Filtrar por corrida (fecha y hora)", options=opciones_corrida)
        corrida_id_filtro = etiquetas_por_corrida.get(corrida_elegida)

        cedula_filtro = st.text_input("Filtrar por cedula (opcional, dejar vacio para ver todas)")

        df_proy = persistencia.obtener_proyecciones_mesada(
            corrida_id=corrida_id_filtro, cedula=cedula_filtro or None
        )

        if df_proy.empty:
            st.info("No hay proyecciones para ese filtro.")
        else:
            df_proy_vista = df_proy.copy()
            df_proy_vista["fecha_hora"] = df_proy_vista["fecha_hora"].str.replace("T", " ", regex=False)
            columnas_vista = [
                "fecha_hora", "pagina", "cedula", "id_cotizacion",
                "producto", "anio", "mesada_proyectada", "convergio",
            ]
            st.write(f"{len(df_proy_vista)} filas.")
            st.dataframe(df_proy_vista[columnas_vista], width='stretch')
            st.download_button(
                "Descargar proyecciones (CSV)",
                data=df_proy_vista[columnas_vista].to_csv(index=False).encode("utf-8"),
                file_name="proyecciones_mesada.csv",
                key="descargar_proyecciones",
            )

            if cedula_filtro:
                st.divider()
                st.subheader(f"Grafico: {cedula_filtro}")
                pivot = df_proy.pivot_table(
                    index="anio", columns="producto", values="mesada_proyectada", aggfunc="last"
                )
                pivot = pivot.rename(columns={"renta_vitalicia": "Renta Vitalicia", "retiro_programado": "Retiro Programado"})
                columnas_disponibles = [c for c in ["Renta Vitalicia", "Retiro Programado"] if c in pivot.columns]
                st.line_chart(pivot[columnas_disponibles], color=["#1f77b4", "#FFFFFF"][: len(columnas_disponibles)])

with tab_parametrizacion:
    historial_params = persistencia.listar_historial_parametrizacion()
    if historial_params.empty:
        st.info("Todavia no se ha guardado ninguna parametrizacion.")
    else:
        st.dataframe(historial_params, width='stretch')
        st.caption("Para restaurar una version anterior, ve a la pagina 'Parametrizacion Actuarial'.")
