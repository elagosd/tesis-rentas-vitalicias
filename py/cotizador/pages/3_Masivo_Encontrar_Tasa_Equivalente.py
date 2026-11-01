"""
Pagina 4: Masivo Encontrar Tasa Equivalente.

Carga la base de calculo (misma estructura que base_polizas_10_polizas.xlsx),
y para cada cedula: (1) calcula el capital objetivo via la curva MTM/TMR
cargada en Parametrizacion Actuarial (con la mesada de la base como
referencia), (2) encuentra la tasa equivalente, (3) encuentra la mesada
final contra capital_renta de la base. Primero se itera la tasa, despues la
mesada (igual que la hoja EncontarTasaEquivalente).

Muestra:
- Proyeccion anual de la mesada pensional (maximo 20 años) para una cedula
  seleccionada.
- Analisis estadistico comparando mesada inicial vs mesada encontrada, para
  toda la base.
"""

import pandas as pd
import altair as alt
import streamlit as st

from core import config, persistencia
from core.base_masiva import (
    VERSION_ESQUEMA_BASE,
    _formatear_cedula,
    procesar_base_tasa_equivalente,
    proyeccion_mesada_por_anio,
)
from core.estado import obtener_parametros
from core.proyecciones_masivo import calcular_y_guardar_proyecciones_masivo
from core.retiro_programado import primer_anio_bajo_smlv, resolver_y_proyectar_rp_para_fila

MAX_ANIOS_GRAFICO = 20

st.title("Masivo: Encontrar Tasa Equivalente")
st.caption(f"Version del esquema de columnas cargado: `{VERSION_ESQUEMA_BASE}`")

params: config.ParametrosActuariales = obtener_parametros()

if not params.curva_expandida():
    st.error(
        "No hay una curva MTM/TMR cargada. Ve a la pagina 'Parametrizacion "
        "Actuarial' y carga la curva antes de usar esta pagina."
    )
    st.stop()

if "resultados_tasa_masivo" in st.session_state:
    if "cedula" not in st.session_state["resultados_tasa_masivo"].columns:
        del st.session_state["resultados_tasa_masivo"]
        st.session_state.pop("base_tasa_masivo", None)

with st.expander("Parametrizacion actuarial en uso"):
    st.write(f"SMLV: {params.smlv:,.0f} | Δ deslizamiento: {params.delta_deslizamiento*100:.4f}% | "
             f"% cambio grupo: {params.porcentaje_reserva_cambio_grupo*100:.2f}% | "
             f"% recargo gastos reserva: {params.porcentaje_recargo_gastos_reserva*100:.2f}% | "
             f"% recargo gastos prima: {params.porcentaje_recargo_gastos_prima*100:.2f}% | "
             f"Metodo: {params.metodo_iteracion} | Curva: {len(params.curva_expandida())} nodos anuales")

archivo = st.file_uploader(
    "Base de calculo (misma estructura de base_polizas_10_polizas.xlsx): "
    "id_cotizacion, id_0, mesada (referencia para la tasa), no_mesada, "
    "capital_renta (objetivo de la mesada), fecha_inicio_vigencia, "
    "fecha_nacimiento_0..9, cod_genero_0..9, cod_estado_0..9, parentesco_0..9)",
    type=["xlsx", "csv"],
    key="archivo_tasa",
)

if archivo is not None:
    if archivo.name.endswith(".csv"):
        base = pd.read_csv(archivo)
    else:
        base = pd.read_excel(archivo)

    st.write(f"Base cargada: {len(base)} cedulas.")
    columnas_faltantes = [c for c in ["id_cotizacion", "id_0", "mesada", "no_mesada", "capital_renta", "fecha_inicio_vigencia", "fecha_nacimiento_0"] if c not in base.columns]
    if columnas_faltantes:
        st.error(f"Faltan columnas requeridas en la base: {columnas_faltantes}")
        st.stop()

    comparar_rp = st.checkbox(
        "Comparar con Retiro Programado",
        value=True,
        key="comparar_rp_tasa",
        help=(
            "Si se activa, ademas de la mesada de Renta Vitalicia se calcula la proyeccion de "
            "Retiro Programado de cada cedula (con evolucion de la CAI año a año) y se agrega la "
            "segunda linea al grafico. Si se desactiva, la corrida solo calcula Renta Vitalicia y "
            "es bastante mas rapida, porque Retiro Programado tiene que correr el motor actuarial "
            "completo una vez por cada año proyectado de cada cedula."
        ),
    )

    if st.button("Calcular tasa equivalente y mesada para toda la base", type="primary"):
        barra = st.progress(0, text="Procesando...")

        def actualizar(completadas, total):
            barra.progress(completadas / total, text=f"Procesando {completadas}/{total}")

        with st.spinner("Calculando..."):
            resultados = procesar_base_tasa_equivalente(base, params, callback_progreso=actualizar)
        barra.progress(1.0, text="Listo")

        st.session_state["resultados_tasa_masivo"] = resultados
        st.session_state["base_tasa_masivo"] = base
        # Se recuerda la eleccion de la casilla junto con los resultados,
        # para que la seccion del grafico (que se vuelve a dibujar en cada
        # rerun de Streamlit) sepa si debe mostrar la linea de RP o no.
        st.session_state["masivo_tasa_incluye_rp"] = comparar_rp
        persistencia.registrar_calculos_masivo("masivo_tasa_equivalente", base, resultados)
        st.success(f"Se calcularon {len(resultados)} cedulas (input y output quedaron guardados en el historial).")

        etiqueta_productos = "Renta Vitalicia y Retiro Programado" if comparar_rp else "Renta Vitalicia"
        barra_proy = st.progress(0, text=f"Guardando proyeccion de mesada ({etiqueta_productos}) por cedula...")

        def actualizar_proy(completadas, total):
            barra_proy.progress(completadas / total, text=f"Guardando proyecciones {completadas}/{total}")

        with st.spinner(f"Calculando proyecciones año a año ({etiqueta_productos}) por cedula..."):
            try:
                corrida_id, df_resumen_rp = calcular_y_guardar_proyecciones_masivo(
                    "masivo_tasa_equivalente", base, resultados, params,
                    callback_progreso=actualizar_proy, incluir_rp=comparar_rp,
                )
                barra_proy.progress(1.0, text="Listo")
                st.success(
                    f"Proyecciones por año ({etiqueta_productos}) guardadas para las "
                    f"{len(resultados)} cedulas (corrida {corrida_id})."
                )

                if comparar_rp:
                    n_criticas = df_resumen_rp["anio_critico_rp"].notna().sum()
                    if n_criticas > 0:
                        st.warning(
                            f"⚠️ En {n_criticas} de {len(df_resumen_rp)} cedulas, el saldo de la CAI deja de "
                            "sostener el SMLV en algun año del horizonte proyectado bajo Retiro Programado "
                            "(columna 'año_critico_rp' en la tabla de resultados abajo)."
                        )

                    resultados = resultados.copy()
                    resultados["año_critico_rp_smlv"] = df_resumen_rp["anio_critico_rp"].values
                    st.session_state["resultados_tasa_masivo"] = resultados
            except Exception as exc:  # noqa: BLE001
                st.warning(f"No se pudieron guardar las proyecciones por cedula: {exc}")

if "resultados_tasa_masivo" in st.session_state:
    resultados = st.session_state["resultados_tasa_masivo"]
    base = st.session_state["base_tasa_masivo"]

    base = base.copy()
    base["_cedula"] = base["id_0"].apply(_formatear_cedula)

    errores = resultados[resultados["error"] != ""]
    if len(errores) > 0:
        st.warning(f"{len(errores)} cedulas presentaron errores. Revisa la columna 'error'.")

    no_convergio = resultados[~resultados["convergio_tasa"] | ~resultados["convergio_mesada"]]
    if len(no_convergio) > 0:
        st.warning(f"{len(no_convergio)} cedulas no convergieron en tasa y/o mesada. Revisa las columnas 'convergio_tasa' / 'convergio_mesada'.")

    st.subheader("Resultados")
    with st.expander("Columnas de depuracion (por si algo no cuadra)"):
        st.write("Columnas de 'resultados':", resultados.columns.tolist())
        st.write("Columnas de 'base':", base.columns.tolist())
    st.dataframe(resultados, width='stretch')

    csv = resultados.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar resultados (.csv)", data=csv, file_name="resultados_masivo_tasa_equivalente.csv")

    st.divider()
    st.subheader("Proyeccion de mesada por año - cedula individual")
    mostrar_rp = st.session_state.get("masivo_tasa_incluye_rp", True)
    st.caption(
        f"Horizonte fijo de {params.max_anios_proyeccion_rp_tope} años para ambos productos. "
        "La linea de Renta Vitalicia cubre siempre el horizonte completo. La de Retiro Programado "
        "puede terminar antes: si el saldo de la CAI deja de alcanzar, la linea simplemente TERMINA "
        "en ese año -- los años siguientes quedan sin dato, no en cero."
    )
    id_seleccionado = st.selectbox("Selecciona una cedula", resultados["cedula"].tolist())

    fila_resultado = resultados[resultados["cedula"] == id_seleccionado].iloc[0]
    fila_base = base[base["_cedula"] == str(id_seleccionado)].iloc[0]

    if fila_resultado["mesada_encontrada"] > 0:
        max_anios_grafico = params.max_anios_proyeccion_rp_tope
        proyeccion_rv = proyeccion_mesada_por_anio(
            fila_base, fila_resultado["mesada_encontrada"], params, max_anios=max_anios_grafico
        ).rename(columns={"Mesada_Pensional_proyectada": "Renta Vitalicia"})
        proyeccion_comparativa = proyeccion_rv

        anio_critico_rp = None
        if mostrar_rp:
            try:
                proyeccion_rp, convergio_rp = resolver_y_proyectar_rp_para_fila(
                    fila_base, params, max_anios=max_anios_grafico,
                    mesada_rv_encontrada=fila_resultado["mesada_encontrada"],
                )
                anio_critico_rp = primer_anio_bajo_smlv(proyeccion_rp)
                proyeccion_rp = proyeccion_rp.rename(columns={"Mesada_Pensional_proyectada": "Retiro Programado"})
                # merge "left" (no "inner"): el eje X lo manda Renta
                # Vitalicia, que siempre cubre el horizonte completo. Si la
                # proyeccion de RP termino antes porque la CAI dejo de
                # alcanzar, los años restantes quedan como NaN -- Altair
                # simplemente no dibuja esos puntos, asi que la linea de RP
                # TERMINA ahi en vez de desplomarse a cero, que es
                # justamente lo que se queria evitar.
                proyeccion_comparativa = proyeccion_rv.merge(
                    proyeccion_rp[["Anio", "Retiro Programado"]], on="Anio", how="left"
                )
                if not convergio_rp:
                    st.warning("El calculo de Retiro Programado para esta cedula no convergio; la linea puede no ser exacta.")
                if anio_critico_rp is not None:
                    st.warning(
                        f"⚠️ La proyeccion de Retiro Programado para esta cedula termina en "
                        f"**{anio_critico_rp}**: el saldo de la CAI ya no alcanza para sostener ni el "
                        f"SMLV por su cuenta. La linea del grafico se corta ahi; no se estiman mas años."
                    )
            except Exception as exc:  # noqa: BLE001
                proyeccion_comparativa = proyeccion_rv
                st.warning(f"No se pudo calcular Retiro Programado para esta cedula: {exc}")

        columnas_grafico = [c for c in ["Renta Vitalicia", "Retiro Programado"] if c in proyeccion_comparativa.columns]
        colores_grafico = {"Renta Vitalicia": "#1f77b4", "Retiro Programado": "#FFFFFF"}

        base_chart = alt.Chart(proyeccion_comparativa).encode(x=alt.X("Anio:O", title="Año"))
        capas = []
        for col in columnas_grafico:
            capas.append(
                base_chart.mark_line(color=colores_grafico[col], point=True).encode(
                    y=alt.Y(f"{col}:Q", title="Mesada"),
                    tooltip=["Anio", col],
                )
            )
        st.altair_chart(alt.layer(*capas).resolve_scale(y="shared"), width='stretch')
        if mostrar_rp:
            st.caption(
                "La linea 'Retiro Programado' se calcula con el motor real de la pestaña 'Retiro "
                "Programado' de Parametrizacion Actuarial (mortalidad sin mejora, sobrecosto de "
                "mortalidad, beneficiario hipotetico si no hay uno real, Gastos RP), usando el mismo "
                "capital de la base (capital_renta) como objetivo -- para comparar a igual capital. "
                f"Su mesada nunca cae mas de {params.caida_maxima_anual_rp*100:.0f}% de un año al "
                "siguiente."
            )
        else:
            st.caption(
                "Solo se grafica Renta Vitalicia: la comparacion con Retiro Programado quedo "
                "desactivada en esta corrida. Para verla, activa la casilla 'Comparar con Retiro "
                "Programado' y vuelve a calcular."
            )
    else:
        st.warning("Esta cedula no convergio, no se puede graficar su proyeccion.")

    st.divider()
    st.subheader("Analisis estadistico - mesada inicial vs mesada encontrada (toda la base)")

    resultados_validos = resultados[resultados["mesada_encontrada"] > 0].copy()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Mesada inicial promedio", f"{resultados_validos['mesada_inicial'].mean():,.0f}")
        st.metric("Mesada encontrada promedio", f"{resultados_validos['mesada_encontrada'].mean():,.0f}")
        st.metric("Tasa equivalente promedio", f"{resultados_validos['tasa_equivalente'].mean()*100:,.4f}%")
    with col2:
        variacion_promedio = (
            (resultados_validos["mesada_encontrada"] - resultados_validos["mesada_inicial"])
            / resultados_validos["mesada_inicial"]
        ).mean() * 100
        st.metric("Variacion promedio", f"{variacion_promedio:,.2f}%")
        st.metric("Cedulas convergidas (tasa y mesada)", f"{len(resultados_validos)} / {len(resultados)}")

    max_val = max(resultados_validos["mesada_inicial"].max(), resultados_validos["mesada_encontrada"].max())
    puntos = alt.Chart(resultados_validos).mark_circle(size=60, opacity=0.6).encode(
        x=alt.X("mesada_inicial", title="Mesada inicial"),
        y=alt.Y("mesada_encontrada", title="Mesada encontrada"),
        tooltip=["cedula", "mesada_inicial", "mesada_encontrada", "tasa_equivalente"],
    )
    referencia = alt.Chart(pd.DataFrame({"x": [0, max_val], "y": [0, max_val]})).mark_line(
        strokeDash=[5, 5], color="gray"
    ).encode(x="x", y="y")
    st.altair_chart((puntos + referencia).properties(title="Mesada inicial vs mesada encontrada"), width='stretch')

    resultados_validos["variacion_pct"] = (
        (resultados_validos["mesada_encontrada"] - resultados_validos["mesada_inicial"])
        / resultados_validos["mesada_inicial"] * 100
    )
    histograma = alt.Chart(resultados_validos).mark_bar().encode(
        x=alt.X("variacion_pct", bin=alt.Bin(maxbins=40), title="Variacion %"),
        y=alt.Y("count()", title="Numero de cedulas"),
    ).properties(title="Distribucion de la variacion % (mesada encontrada vs inicial)")
    st.altair_chart(histograma, width='stretch')
