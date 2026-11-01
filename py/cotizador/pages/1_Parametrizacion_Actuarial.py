"""
Pagina 1: Parametrizacion Actuarial (acceso restringido).

Tiene 4 subsecciones (pestañas), todas detras del mismo control de acceso:

1. Parametros generales: Vector IPC, SMLV, deslizamiento, curva MTM/TMR,
   recargos, metodo de iteracion (por defecto: secante). Usados por las
   paginas Masivo (2 y 4) y por las subsecciones de abajo.
2. Encontrar Tasa Equivalente: calculo individual (una sola cedula),
   replica la hoja EncontarTasaEquivalente del Excel.
3. Encontrar Mesada: calculo individual (una sola cedula), replica la hoja
   EncontrarMesada del Excel.
4. Retiro Programado: calculo individual de la mesada de un portafolio de
   retiro programado (fondo de pensiones privado colombiano). Ver
   core/retiro_programado.py para el detalle de las diferencias con
   EncontrarMesada (tabla sin factores de mejora, sobrecosto de mortalidad,
   beneficiario hipotetico, gastos RP).

Las subsecciones 2, 3 y 4 dejan elegir el numero de beneficiarios (0 a 9,
en Retiro Programado se crea un beneficiario hipotetico si se deja en 0) y
muestran la Duracion Macaulay del resultado.
"""

import streamlit as st
import pandas as pd
import altair as alt
from dataclasses import replace
from pathlib import Path

from core import config, persistencia
from core.auth import exigir_acceso_actuario
from core.encontrar_mesada_individual import encontrar_mesada
from core.estado import obtener_parametros
from core.formularios import formulario_beneficiarios, formulario_causante
from core.motor import DatosPoliza
from core.retiro_programado import (
    _RUTA_BENEFICIARIO_INVALIDOS,
    _RUTA_BENEFICIARIO_VALIDOS,
    _RUTA_SOBRECOSTO,
    edad_en_anios,
    primer_anio_bajo_smlv,
    proyectar_rp_dinamico_cai,
    resolver_mesada_rp,
    resolver_y_proyectar_rp_para_fila,
    sobrecosto_mortalidad,
)
from core.base_masiva import procesar_base, proyeccion_mesada_por_anio
from core.comparador_escenarios_rp import comparar_escenarios
from core.tasa_equivalente import resolver_tasa_y_mesada

exigir_acceso_actuario("Parametrizacion Actuarial")

st.title("Parametrizacion actuarial")

p: config.ParametrosActuariales = obtener_parametros()

tab_parametros, tab_tasa, tab_mesada, tab_rp = st.tabs(
    ["Parametros generales", "Encontrar Tasa Equivalente", "Encontrar Mesada", "Retiro Programado"]
)

# =============================================================================
# Subseccion 1: Parametros generales
# =============================================================================
with tab_parametros:
    with st.expander("Historial de actualizaciones (IPC, TMR y demas parametros)"):
        historial = persistencia.listar_historial_parametrizacion()
        if historial.empty:
            st.write("Todavia no se ha guardado ninguna parametrizacion.")
        else:
            st.dataframe(historial, width='stretch')
            id_restaurar = st.selectbox(
                "Restaurar una version anterior (por id)",
                options=historial["id"].tolist(),
                format_func=lambda i: f"id {i} - {historial.set_index('id').loc[i, 'fecha_hora']}",
            )
            if st.button("Restaurar esta version"):
                restaurada = persistencia.cargar_parametrizacion_por_id(id_restaurar)
                if restaurada is not None:
                    st.session_state["parametros"] = restaurada
                    # Forzar la actualizacion de los campos manuales del vector
                    # IPC (mismo motivo que en la carga por archivo: pasar
                    # "value=" en el widget no alcanza una vez que ya se creo).
                    for i, v in enumerate(restaurada.vector_ipc_primer_anio):
                        st.session_state[f"ipc_mes_{i}"] = round(float(v) * 100, 6)
                    st.session_state["ipc_primer_anio_input"] = round(float(restaurada.ipc_primer_anio) * 100, 6)
                    st.success(f"Version id {id_restaurar} restaurada. Revisa los valores abajo y guarda de nuevo si quieres dejarla como la vigente.")
                    st.rerun()

    st.subheader("Vector IPC")
    st.caption(
        "El vector mensual de abajo se usa UNICAMENTE para el descuento tecnico "
        "de los primeros 12 meses de la proyeccion (igual que 'Vector Inflación'!"
        "E3:E14 del Excel). La inflacion esperada del año 1 usada para el "
        "**crecimiento** de la mesada es un dato aparte, mas abajo -- en el "
        "Excel viene de una encuesta (BANREP_ENCUESTA), no es el compuesto de "
        "este vector (pueden coincidir por casualidad, pero en general son "
        "numeros distintos)."
    )

    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    modo_carga = st.radio(
        "Como quieres cargar el vector mensual de inflacion (descuento primeros 12 meses)",
        ["Editar manualmente", "Cargar archivo (.xlsx o .csv)"],
        horizontal=True,
    )

    if modo_carga == "Cargar archivo (.xlsx o .csv)":
        archivo = st.file_uploader(
            "Archivo con 12 valores mensuales de inflacion (una columna, en formato decimal, ej 0.0118 = 1.18%). "
            "El encabezado es opcional; si lo incluyes, usa 'IPC' o 'Mes'.",
            type=["xlsx", "csv"],
        )
        if archivo is not None:
            import pandas as pd

            if archivo.name.endswith(".csv"):
                df_ipc = pd.read_csv(archivo, header=None)
            else:
                df_ipc = pd.read_excel(archivo, header=None)
            df_ipc = df_ipc.dropna(how="all")

            # El encabezado es opcional: si la primera fila no se puede leer
            # como numero (p.ej. trae texto tipo "IPC"), se descarta.
            if len(df_ipc) > 0:
                try:
                    float(df_ipc.iloc[0, 0])
                except (ValueError, TypeError):
                    df_ipc = df_ipc.iloc[1:]

            valores = df_ipc.iloc[:, 0].dropna().tolist()
            if len(valores) >= 12:
                vector_cargado = [float(v) for v in valores[:12]]
                # Actualiza directamente el estado de cada campo manual, para
                # que se vea reflejado de inmediato (pasar "value=" en el
                # number_input de abajo NO alcanza: Streamlit solo lo usa la
                # primera vez que se crea el widget, despues manda el estado
                # interno guardado bajo esa key).
                for i, v in enumerate(vector_cargado):
                    st.session_state[f"ipc_mes_{i}"] = round(v * 100, 6)

                # Sugerencia de "Inflacion esperada año 1": son datos
                # independientes (ver mas abajo), pero como punto de partida
                # comodo se pre-llena con el compuesto del vector recien
                # cargado. Queda editable por si el dato real es distinto.
                compuesto_sugerido = 1.0
                for v in vector_cargado:
                    compuesto_sugerido *= (1 + v)
                compuesto_sugerido -= 1
                st.session_state["ipc_primer_anio_input"] = round(compuesto_sugerido * 100, 6)

                st.success(
                    "Vector de 12 meses cargado correctamente (ya se ve reflejado abajo, en 'Editar "
                    "manualmente'). Tambien se sugirio un valor para 'Inflacion esperada año 1' -- "
                    "revisalo y cambialo si el dato real es distinto."
                )
            else:
                st.error(f"El archivo debe tener al menos 12 valores, tiene {len(valores)}.")

    cols = st.columns(6)
    nuevo_vector = []
    for i, mes in enumerate(meses):
        with cols[i % 6]:
            if f"ipc_mes_{i}" not in st.session_state:
                st.session_state[f"ipc_mes_{i}"] = float(p.vector_ipc_primer_anio[i]) * 100
            val = st.number_input(
                mes,
                step=0.01,
                format="%.4f",
                key=f"ipc_mes_{i}",
                help="Valor en % (ej: 1.18 para 1.18%)",
            )
            nuevo_vector.append(val / 100)

    compuesto_referencia = 1.0
    for v in nuevo_vector:
        compuesto_referencia *= (1 + v)
    compuesto_referencia -= 1
    st.caption(f"(Solo como referencia: el compuesto de estos 12 valores da {compuesto_referencia*100:.4f}%, "
               "pero NO es lo que se usa como inflacion del año 1 -- ver el campo de abajo.)")

    st.subheader("Inflacion esperada por año (crecimiento de la mesada)")
    col0, col1, col2 = st.columns(3)
    with col0:
        if "ipc_primer_anio_input" not in st.session_state:
            st.session_state["ipc_primer_anio_input"] = p.ipc_primer_anio * 100
        ipc_primer_anio = st.number_input(
            "Inflacion esperada año 1 (%)", step=0.01, format="%.4f",
            key="ipc_primer_anio_input",
            help="Dato independiente del vector mensual de arriba (en el Excel viene de BANREP_ENCUESTA). "
                 "Al cargar el vector por archivo se sugiere un valor de partida aqui, pero puedes cambiarlo.",
        )
    with col1:
        ipc_segundo_anio = st.number_input(
            "Inflacion esperada año 2 (%)", value=p.ipc_segundo_anio * 100, step=0.01, format="%.4f"
        )
    with col2:
        ipc_objetivo_largo_plazo = st.number_input(
            "Inflacion objetivo largo plazo (año 3 en adelante) (%)",
            value=p.ipc_objetivo_largo_plazo * 100,
            step=0.01,
            format="%.4f",
        )

    st.subheader("Otros parametros")
    col3, col4 = st.columns(2)
    with col3:
        smlv = st.number_input("SMLV", value=float(p.smlv), min_value=0.0, step=1000.0)
        delta_deslizamiento = st.number_input(
            "Δ Tasa de deslizamiento (%)", value=p.delta_deslizamiento * 100, step=0.01, format="%.4f"
        )
    with col4:
        porcentaje_reserva_cambio_grupo = st.number_input(
            "% Reserva de amparo basico por cambio de grupo",
            value=p.porcentaje_reserva_cambio_grupo * 100,
            min_value=0.0,
            max_value=100.0,
            step=0.1,
        )
        porcentaje_recargo_gastos_reserva = st.number_input(
            "% Recargo Gastos Reserva",
            value=p.porcentaje_recargo_gastos_reserva * 100,
            min_value=0.0,
            max_value=100.0,
            step=0.1,
        )
        porcentaje_recargo_gastos_prima = st.number_input(
            "% Recargo Gastos Prima",
            value=p.porcentaje_recargo_gastos_prima * 100,
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            help="Usado por Encontrar Tasa Equivalente (columna C21 'Recargo_Gastos_Prima' del Excel).",
        )

    st.subheader("Curva MTM / TMR")
    st.caption(
        "Usada por 'Encontrar Tasa Equivalente' y 'Masivo Encontrar Tasa "
        "Equivalente' (equivale a pegar la curva en la columna EG de la "
        "hoja EncontarTasaEquivalente del Excel). Carga pares (año nodo, "
        "tasa anual): un nodo por año 1, 2, 3... Si faltan años intermedios, "
        "se sostiene el ultimo nodo cargado (igual que el VLOOKUP de la "
        "hoja, sin interpolar)."
    )

    modo_curva = st.radio(
        "Como quieres cargar la curva MTM/TMR",
        ["Editar manualmente", "Cargar archivo (.xlsx o .csv)"],
        horizontal=True,
        key="modo_curva",
    )

    nodos_curva = list(p.curva_mtm_nodos)

    if modo_curva == "Cargar archivo (.xlsx o .csv)":
        archivo_curva = st.file_uploader(
            "Archivo con 2 columnas: año del nodo (1, 2, 3, ...) y tasa anual en "
            "formato decimal (ej 0.02 = 2%). El encabezado es opcional; si lo "
            "incluyes, usa 'Nodo' (o 'Año') y 'Tasa'.",
            type=["xlsx", "csv"],
            key="archivo_curva",
        )
        if archivo_curva is not None:
            import pandas as pd

            if archivo_curva.name.endswith(".csv"):
                df_curva = pd.read_csv(archivo_curva, header=None)
            else:
                df_curva = pd.read_excel(archivo_curva, header=None)
            df_curva = df_curva.dropna(how="all")

            if len(df_curva) > 0:
                primera_fila = df_curva.iloc[0]
                try:
                    float(primera_fila.iloc[0])
                    float(primera_fila.iloc[1])
                except (ValueError, TypeError):
                    df_curva = df_curva.iloc[1:]

            df_curva = df_curva.dropna()
            try:
                nodos_curva = [(int(a), float(t)) for a, t in zip(df_curva.iloc[:, 0], df_curva.iloc[:, 1])]
                st.success(f"Curva cargada: {len(nodos_curva)} nodos (año {nodos_curva[0][0]} a {nodos_curva[-1][0]}).")
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo leer la curva: {exc}")
    else:
        texto_defecto = "\n".join(f"{a},{t*100:.4f}" for a, t in nodos_curva) if nodos_curva else ""
        texto_curva = st.text_area(
            "Un nodo por linea, formato: año,tasa_en_porcentaje (ej: 1,2.00)",
            value=texto_defecto,
            height=150,
            placeholder="1,2.00\n2,2.35\n3,2.60\n...",
        )
        nodos_nuevos = []
        for linea in texto_curva.splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                a_str, t_str = linea.split(",")
                nodos_nuevos.append((int(a_str.strip()), float(t_str.strip()) / 100))
            except ValueError:
                st.warning(f"Linea ignorada, formato invalido: '{linea}'")
        if nodos_nuevos:
            nodos_curva = nodos_nuevos

    if nodos_curva:
        st.write(f"Curva actual: {len(nodos_curva)} nodos cargados (año {nodos_curva[0][0]} a {nodos_curva[-1][0]}).")
    else:
        st.info("Aun no hay curva MTM/TMR cargada. La subseccion 'Encontrar Tasa Equivalente' la necesita para funcionar.")

    st.subheader("Metodo de iteracion")
    metodo_iteracion = st.selectbox(
        "Metodo para encontrar la mesada / tasa",
        options=["secante", "biseccion", "newton"],
        index=["secante", "biseccion", "newton"].index(p.metodo_iteracion),
        help="Por defecto: secante.",
    )
    col5, col6 = st.columns(2)
    with col5:
        epsilon = st.number_input("Epsilon (tolerancia)", value=float(p.epsilon), min_value=0.0001)
    with col6:
        max_iteraciones = st.number_input(
            "Maximo de iteraciones", value=int(p.max_iteraciones), min_value=10, step=10
        )

    if st.button("Guardar parametrizacion", type="primary"):
        # replace(p, ...) en vez de construir un ParametrosActuariales desde
        # cero: asi solo se tocan los parametros que SI se editan en esta
        # pestaña y TODO lo demas se conserva tal como estaba. Construyendolo
        # desde cero habia que acordarse de re-listar a mano cada parametro
        # de otras pestañas, y cualquiera que se olvidara se reseteaba en
        # silencio a su valor por defecto al guardar desde aqui (le estaba
        # pasando a deslizamiento_rp_bajo, ipc_observado_rp, factor_ajuste_ni
        # y los de Smith-Wilson).
        nuevos_parametros = replace(
            p,
            vector_ipc_primer_anio=nuevo_vector,
            ipc_primer_anio=ipc_primer_anio / 100,
            ipc_segundo_anio=ipc_segundo_anio / 100,
            ipc_objetivo_largo_plazo=ipc_objetivo_largo_plazo / 100,
            smlv=smlv,
            delta_deslizamiento=delta_deslizamiento / 100,
            porcentaje_reserva_cambio_grupo=porcentaje_reserva_cambio_grupo / 100,
            porcentaje_recargo_gastos_reserva=porcentaje_recargo_gastos_reserva / 100,
            porcentaje_recargo_gastos_prima=porcentaje_recargo_gastos_prima / 100,
            metodo_iteracion=metodo_iteracion,
            epsilon=epsilon,
            max_iteraciones=int(max_iteraciones),
            curva_mtm_nodos=nodos_curva,
            # Los parametros de Retiro Programado se editan en la pestaña
            # 'Retiro Programado', no aqui: replace() los conserva solos.
        )
        st.session_state["parametros"] = nuevos_parametros
        st.session_state["parametros_vienen_de_disco"] = True
        persistencia.guardar_parametrizacion(nuevos_parametros)
        p = nuevos_parametros
        st.success(
            "Parametrizacion guardada (queda en el historial de arriba, "
            "no se pierde al cerrar la app)."
        )

# =============================================================================
# Subseccion 2: Encontrar Tasa Equivalente (individual)
# =============================================================================
with tab_tasa:
    st.caption(
        "Replica la hoja EncontarTasaEquivalente del Excel para una sola "
        "cedula: (1) con la mesada de referencia fija y la curva MTM/TMR de "
        "arriba, calcula el Capital Acumulado; (2) encuentra la tasa "
        "equivalente; (3) con esa tasa fija, encuentra la mesada."
    )

    if not p.curva_expandida():
        st.error("No hay una curva MTM/TMR cargada. Cargala en la pestaña 'Parametros generales' primero.")
    else:
        with st.expander("Parametrizacion actuarial en uso"):
            st.write(f"SMLV: {p.smlv:,.0f} | Δ deslizamiento: {p.delta_deslizamiento*100:.4f}% | "
                     f"% cambio grupo: {p.porcentaje_reserva_cambio_grupo*100:.2f}% | "
                     f"% recargo gastos reserva: {p.porcentaje_recargo_gastos_reserva*100:.2f}% | "
                     f"% recargo gastos prima: {p.porcentaje_recargo_gastos_prima*100:.2f}% | "
                     f"Metodo: {p.metodo_iteracion} | Curva: {len(p.curva_expandida())} nodos anuales")

        st.subheader("Datos de la poliza")
        col1, col2, col3 = st.columns(3)
        with col1:
            t_n_mesadas = st.selectbox("Numero de mesadas", options=[13, 14], index=1, key="tasa_n_mesadas")
        with col2:
            t_fecha_valoracion = st.date_input("Fecha de valoracion", value=__import__("datetime").date(2026, 4, 1), key="tasa_fecha_val")
        with col3:
            t_mesada_actual = st.number_input("Mesada actual (referencia para hallar la tasa)", min_value=0.0, value=7_924_320.0, step=10000.0, key="tasa_mesada_actual")

        t_causante = formulario_causante("tasa")
        t_beneficiarios = formulario_beneficiarios("tasa")

        st.subheader("Capital objetivo para la mesada (paso 2)")
        t_usar_mismo_capital = st.checkbox(
            "Usar el mismo Capital Acumulado del paso 1 (como en la hoja de ejemplo del Excel)",
            value=True, key="tasa_usar_mismo_capital",
        )
        t_capital_objetivo_manual = None
        if not t_usar_mismo_capital:
            t_capital_objetivo_manual = st.number_input(
                "Capital objetivo (p.ej. el capital realmente acumulado de la cedula)",
                min_value=0.0, value=0.0, step=1_000_000.0, key="tasa_capital_manual",
            )

        if st.button("Calcular tasa equivalente y mesada", type="primary", key="tasa_calcular"):
            datos = DatosPoliza(
                id_pol="individual", n_mesadas=t_n_mesadas, fecha_valoracion=t_fecha_valoracion,
                smlv=p.smlv, mesada_actual=t_mesada_actual, tasa_interes_real=0.0,
                causante=t_causante, beneficiarios=t_beneficiarios,
            )

            with st.spinner("Calculando..."):
                capital_objetivo = None if t_usar_mismo_capital else t_capital_objetivo_manual
                resultado = resolver_tasa_y_mesada(datos, p, capital_objetivo_mesada=capital_objetivo)

            st.divider()
            st.subheader("Resultados")

            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Capital objetivo (paso 1, via curva)", f"{resultado.capital_objetivo_tasa:,.2f}")
                st.metric("Tasa equivalente", f"{resultado.tasa_equivalente*100:.4f}%")
                st.write("Convergio:", "Si" if resultado.convergio_tasa else "**No**")
            with col_b:
                st.metric("Capital objetivo (paso 2, mesada)", f"{resultado.capital_objetivo_mesada:,.2f}")
                st.metric("Mesada encontrada", f"{resultado.mesada_encontrada:,.2f}")
                st.write("Convergio:", "Si" if resultado.convergio_mesada else "**No**")

            col_c, col_d = st.columns(2)
            with col_c:
                st.metric("Prima final (con tasa y mesada encontradas)", f"{resultado.prima_final:,.2f}")
            with col_d:
                st.metric("Duracion Macaulay", f"{resultado.duracion_macaulay:,.2f} años")

            if not resultado.convergio_tasa or not resultado.convergio_mesada:
                st.warning("Alguno de los dos pasos no convergio dentro del numero maximo de iteraciones configurado arriba.")

            persistencia.registrar_calculo(
                pagina="individual_tasa_equivalente",
                cedula=t_causante.fecha_nacimiento.isoformat(),
                id_cotizacion="individual",
                entrada={
                    "n_mesadas": t_n_mesadas, "fecha_valoracion": str(t_fecha_valoracion),
                    "mesada_actual": t_mesada_actual, "causante_fecha_nacimiento": str(t_causante.fecha_nacimiento),
                    "causante_sexo": t_causante.sexo, "causante_estado": t_causante.estado,
                    "n_beneficiarios": len(t_beneficiarios),
                    "usar_mismo_capital": t_usar_mismo_capital, "capital_objetivo_manual": t_capital_objetivo_manual,
                },
                salida={
                    "capital_objetivo_tasa": resultado.capital_objetivo_tasa,
                    "tasa_equivalente": resultado.tasa_equivalente,
                    "convergio_tasa": resultado.convergio_tasa,
                    "capital_objetivo_mesada": resultado.capital_objetivo_mesada,
                    "mesada_encontrada": resultado.mesada_encontrada,
                    "convergio_mesada": resultado.convergio_mesada,
                    "prima_final": resultado.prima_final,
                    "duracion_macaulay": resultado.duracion_macaulay,
                },
            )
            st.caption("Este calculo quedo guardado en el historial (input y output).")

# =============================================================================
# Subseccion 3: Encontrar Mesada (individual)
# =============================================================================
with tab_mesada:
    st.caption(
        "Replica la hoja EncontrarMesada del Excel para una sola cedula: "
        "busca la mesada que hace que la Reserva Matematica iguale el "
        "capital asegurado, con la tasa de interes real como dato fijo "
        "(a diferencia de Encontrar Tasa Equivalente, aqui no se usa la "
        "curva MTM/TMR). En esta hoja el recargo usado es el de "
        "**% Recargo Gastos Prima** (asi esta etiquetado en el Excel, "
        "aunque alimente la celda 'Reserva Matematica'); el % Recargo "
        "Gastos Reserva no se usa en esta subseccion."
    )

    with st.expander("Parametrizacion actuarial en uso", expanded=False):
        st.write(f"SMLV: {p.smlv:,.0f} | Δ deslizamiento: {p.delta_deslizamiento*100:.4f}% | "
                 f"% cambio grupo: {p.porcentaje_reserva_cambio_grupo*100:.2f}% | "
                 f"% recargo gastos prima: {p.porcentaje_recargo_gastos_prima*100:.2f}% | "
                 f"Metodo: {p.metodo_iteracion}")

    st.subheader("Datos de la poliza")
    col1, col2, col3 = st.columns(3)
    with col1:
        m_n_mesadas = st.selectbox("Numero de mesadas", options=[13, 14], index=1, key="mesada_n_mesadas")
    with col2:
        m_fecha_valoracion = st.date_input("Fecha de valoracion", value=__import__("datetime").date(2026, 4, 30), key="mesada_fecha_val")
    with col3:
        m_tasa_interes_real = st.number_input("Tasa de interes real (%)", min_value=0.0, value=3.92, step=0.01, format="%.4f", key="mesada_tasa") / 100

    m_capital_asegurado = st.number_input(
        "Capital asegurado (KA) - objetivo que debe igualar la Reserva Matematica",
        min_value=0.0, value=366_347_345.0, step=1_000_000.0, key="mesada_capital_asegurado",
    )

    m_causante = formulario_causante("mesada")
    m_beneficiarios = formulario_beneficiarios("mesada")

    if st.button("Calcular mesada", type="primary", key="mesada_calcular"):
        datos = DatosPoliza(
            id_pol="individual", n_mesadas=m_n_mesadas, fecha_valoracion=m_fecha_valoracion,
            smlv=p.smlv, mesada_actual=p.smlv, tasa_interes_real=m_tasa_interes_real,
            causante=m_causante, beneficiarios=m_beneficiarios,
        )

        with st.spinner("Calculando..."):
            resultado_metodo, resultado_reserva = encontrar_mesada(datos, m_capital_asegurado, p)

        st.divider()
        st.subheader("Resultados")

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Mesada encontrada", f"{resultado_metodo.valor:,.2f}")
            st.metric("Reserva Matematica final", f"{resultado_reserva.prima:,.2f}")
            st.write("Convergio:", "Si" if resultado_metodo.convergio else "**No**")
        with col_b:
            st.metric("Duracion Macaulay", f"{resultado_reserva.duracion_macaulay:,.2f} años")
            st.metric("Iteraciones", resultado_metodo.iteraciones)

        if not resultado_metodo.convergio:
            st.warning("No convergio dentro del numero maximo de iteraciones configurado arriba.")

        with st.expander("Detalle de la reserva"):
            st.write(f"Reserva de amparo basico: {resultado_reserva.reserva_amparo_basico:,.2f}")
            st.write(f"Reserva cambio de grupo: {resultado_reserva.reserva_amparo_basico_cambio_grupo:,.2f}")
            st.write(f"Auxilio funerario: {resultado_reserva.auxilio_funerario:,.2f}")
            st.write(f"Recargo gastos prima: {resultado_reserva.recargo_gastos_prima:,.2f}")

        persistencia.registrar_calculo(
            pagina="individual_mesada",
            cedula=m_causante.fecha_nacimiento.isoformat(),
            id_cotizacion="individual",
            entrada={
                "n_mesadas": m_n_mesadas, "fecha_valoracion": str(m_fecha_valoracion),
                "tasa_interes_real": m_tasa_interes_real, "capital_asegurado": m_capital_asegurado,
                "causante_fecha_nacimiento": str(m_causante.fecha_nacimiento),
                "causante_sexo": m_causante.sexo, "causante_estado": m_causante.estado,
                "n_beneficiarios": len(m_beneficiarios),
            },
            salida={
                "mesada_encontrada": resultado_metodo.valor,
                "convergio": resultado_metodo.convergio,
                "reserva_matematica": resultado_reserva.prima,
                "duracion_macaulay": resultado_reserva.duracion_macaulay,
            },
        )
        st.caption("Este calculo quedo guardado en el historial (input y output).")

# =============================================================================
# Subseccion 4: Retiro Programado (individual)
# =============================================================================
with tab_rp:
    st.caption(
        "Calcula la mesada de un portafolio de retiro programado (RP) de un "
        "fondo de pensiones privado colombiano. Se parte del mismo motor de "
        "Encontrar Mesada (mortalidad, crecimiento, descuento, auxilio "
        "funerario), con 4 diferencias: tabla de mortalidad SIN factores de "
        "mejora, un recargo adicional de sobrecosto de mortalidad (segun "
        "edad y sexo del causante), un beneficiario conyuge hipotetico si "
        "el pensionado no tiene beneficiarios reales, y un recargo de "
        "Gastos RP."
    )

    st.subheader("Parametros de Retiro Programado")
    col_rp1, col_rp2, col_rp3, col_rp4 = st.columns(4)
    with col_rp1:
        rp_interes_tecnico = st.number_input(
            "Interes Tecnico RP (%)", value=p.interes_tecnico_rp * 100, step=0.01, format="%.4f",
            help="Equivalente al 'it_emision' que se usa en las bases masivas.",
        )
    with col_rp2:
        rp_deslizamiento = st.number_input(
            "Deslizamiento RP (%)", value=p.deslizamiento_rp * 100, step=0.01, format="%.4f",
        )
    with col_rp3:
        rp_gastos = st.number_input(
            "Gastos RP (%)", value=p.gastos_rp * 100, step=0.01, format="%.4f",
            help="Se aplica como recargo, misma formula que los demas recargos: ((1/(1-%))-1)*base.",
        )
    with col_rp4:
        rp_tasa_crecimiento_cai = st.number_input(
            "Tasa de crecimiento de la CAI (%)", value=p.tasa_crecimiento_cai * 100, step=0.01, format="%.4f",
            help=(
                "Rendimiento real PROMEDIO asumido para el saldo remanente de la Cuenta de Ahorro "
                "Individual, año a año (distinta del Interes Tecnico RP, que es la tasa actuarial "
                "usada dentro de la formula de reserva). Cada año se sortea una tasa real distinta "
                "alrededor de este promedio -- ver 'Volatilidad de la CAI' abajo."
            ),
        )

    col_rp5, _, _, _ = st.columns(4)
    with col_rp5:
        rp_volatilidad_cai = st.number_input(
            "Volatilidad de la CAI (desviacion estandar anual, %)",
            value=p.tasa_crecimiento_cai_volatilidad * 100, step=0.01, format="%.4f",
            help=(
                "Refleja el riesgo de mercado real del portafolio de Retiro Programado (no crece igual "
                "todos los años -- tiene años buenos y años malos). Cada año se sortea una tasa de "
                "crecimiento real de una distribucion normal (media=Tasa de crecimiento de la CAI, "
                "desviacion=este valor). Reproducible por cedula: la misma cedula siempre da la misma "
                "trayectoria de riesgo. Valor por defecto ESTIMADO a partir de la variabilidad real "
                "observada en Retiro Programado de Colfondos (4.64% en 1 trimestre de 2025 vs 11.31% "
                "de promedio en los ultimos 4 años) y la composicion del portafolio -- se recomienda "
                "reemplazarlo si el fondo tiene acceso a la serie historica completa."
            ),
        )


    col_rp6, _, _, _ = st.columns(4)
    with col_rp6:
        rp_castigo_riesgo = st.number_input(
            "Castigo CAI por riesgo de mercado (%)",
            value=p.castigo_riesgo_mercado_cai * 100, step=0.01, format="%.4f",
            help=(
                "Reduccion SISTEMATICA (todos los años, no solo ruido aleatorio) de la Tasa de "
                "Crecimiento de la CAI, para reflejar el riesgo de mercado de forma mas conservadora. "
                "Calibrado empiricamente para que, de forma organica, Retiro Programado quede por "
                "debajo de Renta Vitalicia dentro del horizonte proyectado -- ver VALIDACION.md."
            ),
        )

    st.markdown("**Condicion comercial: Renta Vitalicia mayor que Retiro Programado**")
    rp_aplicar_condicion_rv = st.checkbox(
        "Forzar que la mesada de Retiro Programado quede por debajo de la de Renta Vitalicia",
        value=p.aplicar_condicion_rv_mayor,
        help=(
            "OPCIONAL (desactivada por defecto). Si se activa, la mesada de RP se topa contra la de "
            "Renta Vitalicia de la misma cedula a partir del año indicado abajo. Si se deja "
            "desactivada, la mesada de RP sale unicamente de su propia dinamica actuarial mas el "
            "riesgo de mercado de la CAI -- que es lo que, de forma organica, la lleva a quedar por "
            "debajo de Renta Vitalicia."
        ),
    )
    col_cond1, _, _, _ = st.columns(4)
    with col_cond1:
        rp_anio_inicio_condicion = st.number_input(
            "Aplicar la condicion desde el año",
            min_value=1, max_value=40, value=int(p.anio_inicio_condicion_rv), step=1,
            disabled=not rp_aplicar_condicion_rv,
            help="Solo aplica si la condicion de arriba esta activada. Año 1 = primer año de la proyeccion.",
        )

    col_tope1, col_tope2, _, _ = st.columns(4)
    with col_tope1:
        rp_tope_anios = st.number_input(
            "Años de proyeccion (Renta Vitalicia y Retiro Programado)",
            min_value=5, max_value=80, value=int(p.max_anios_proyeccion_rp_tope), step=1,
            help=(
                "Horizonte FIJO, en años, de las dos lineas de los graficos de proyeccion (20 por "
                "defecto). Renta Vitalicia siempre proyecta el horizonte completo. Retiro Programado "
                "tambien, salvo que el saldo de la CAI deje de alcanzar antes: en ese caso su linea "
                "simplemente termina en ese año (los años restantes quedan sin dato, no en cero)."
            ),
        )
    with col_tope2:
        rp_caida_maxima = st.number_input(
            "Caida maxima anual de la mesada RP (%)",
            min_value=0.0, max_value=100.0,
            value=p.caida_maxima_anual_rp * 100, step=1.0, format="%.2f",
            help=(
                "La mesada de Retiro Programado no puede caer mas de este porcentaje de un año al "
                "siguiente. Amortigua los desplomes que aparecen cuando el saldo de la CAI se "
                "deteriora (mal año de mercado, o normalizacion al SMLV proyectado) y que en el "
                "grafico se ven como un acantilado. Solo puede subir la mesada, nunca bajarla, y lo "
                "que se paga de mas si sale del saldo real de la CAI -- o sea que el fondo se agota "
                "antes y la proyeccion se corta antes. Con 0% la mesada quedaria congelada a la baja; "
                "con 100% se desactiva el limite."
            ),
        )

    with st.expander("🔬 Comparador de escenarios (para decidir castigo vs condicion comercial)"):
        st.caption(
            "Corre una base de polizas bajo varios escenarios y muestra que pasa con la mesada de "
            "Retiro Programado en cada uno, para poder decidir con datos cual adoptar. Las 2 palancas "
            "que se comparan son: el CASTIGO por riesgo de mercado (hace que el fondo crezca mas "
            "despacio, de modo que RP quede bajo RV de forma organica) y la CONDICION COMERCIAL "
            "(topa RP contra RV por regla, desde el año que se indique). No cambia nada guardado: "
            "solo simula."
        )

        archivo_comp = st.file_uploader(
            "Base de polizas para la comparacion (.xlsx)", type=["xlsx"], key="comp_base"
        )
        ruta_ejemplo = Path(__file__).resolve().parents[1] / "ejemplos" / "base_cotizacion_ejemplo.xlsx"
        if archivo_comp is None and ruta_ejemplo.exists():
            st.caption(f"Sin archivo cargado se usa la base de ejemplo incluida: {ruta_ejemplo.name}")

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            castigos_texto = st.text_input(
                "Castigos a probar (%, separados por coma)", value="0, 3, 5",
                help="Cada valor genera un escenario SIN condicion comercial, para ver si el castigo "
                     "por si solo logra que RP quede bajo RV.",
            )
        with col_e2:
            anios_condicion_texto = st.text_input(
                "Condicion comercial: años a probar", value="3",
                help="Cada valor genera un escenario CON la condicion activada desde ese año "
                     "(y sin castigo). Dejar vacio para no probar la condicion.",
            )

        if st.button("Comparar escenarios", key="comp_correr"):
            try:
                base_comp = pd.read_excel(archivo_comp) if archivo_comp is not None else pd.read_excel(ruta_ejemplo)
            except Exception as exc:  # noqa: BLE001
                base_comp = None
                st.error(f"No se pudo leer la base: {exc}")

            if base_comp is not None:
                escenarios = []
                for txt in castigos_texto.split(","):
                    txt = txt.strip()
                    if not txt:
                        continue
                    try:
                        c = float(txt.replace("%", "")) / 100
                    except ValueError:
                        continue
                    escenarios.append({
                        "nombre": f"Castigo {c*100:.0f}% (sin condicion)",
                        "castigo": c, "condicion": False, "anio_condicion": 3,
                    })
                for txt in anios_condicion_texto.split(","):
                    txt = txt.strip()
                    if not txt:
                        continue
                    try:
                        a = int(txt)
                    except ValueError:
                        continue
                    escenarios.append({
                        "nombre": f"Condicion comercial desde año {a}",
                        "castigo": 0.0, "condicion": True, "anio_condicion": a,
                    })

                if not escenarios:
                    st.warning("No se pudo interpretar ningun escenario de los valores ingresados.")
                else:
                    # Parametrizacion "en vivo" para la comparacion: se usan
                    # los valores actualmente en pantalla (no los guardados),
                    # excepto castigo/condicion, que los define cada escenario.
                    params_comp = replace(
                        p,
                        interes_tecnico_rp=rp_interes_tecnico / 100,
                        deslizamiento_rp=rp_deslizamiento / 100,
                        gastos_rp=rp_gastos / 100,
                        tasa_crecimiento_cai=rp_tasa_crecimiento_cai / 100,
                        tasa_crecimiento_cai_volatilidad=rp_volatilidad_cai / 100,
                        max_anios_proyeccion_rp_tope=int(rp_tope_anios),
                        caida_maxima_anual_rp=rp_caida_maxima / 100,
                    )
                    with st.spinner(f"Corriendo {len(escenarios)} escenarios sobre {len(base_comp)} polizas..."):
                        detalle, resumen = comparar_escenarios(base_comp, params_comp, escenarios)
                    if resumen.empty:
                        st.warning("La comparacion no produjo resultados (revisa que la base tenga el formato esperado).")
                    else:
                        st.markdown("**Resumen por escenario**")
                        st.dataframe(resumen, width='stretch', hide_index=True)
                        st.caption(
                            "'% cruzan' = en cuantas cedulas la mesada de RP llega a quedar por debajo de "
                            "la de RV. 'Control de Saldos' = la CAI dejo de sostener un SMLV. "
                            "'CAI agotada' = el saldo se acabo sin que RP llegara a bajar de RV."
                        )
                        st.markdown("**Detalle por cedula**")
                        st.dataframe(detalle, width='stretch', hide_index=True)
                        st.download_button(
                            "Descargar detalle (CSV)",
                            detalle.to_csv(index=False).encode("utf-8"),
                            file_name="comparacion_escenarios_rp.csv", mime="text/csv",
                        )
                        st.info(
                            "Como leer esto: si un castigo logra un '% cruzan' alto, la separacion entre "
                            "RP y RV se consigue de forma economica (sin imponer reglas). Si aun con "
                            "castigos altos muchas cedulas terminan en 'CAI agotada' sin cruzar, la unica "
                            "forma de garantizar RV>RP es activar la condicion comercial."
                        )

    if st.button("Guardar parametros RP", key="rp_guardar_parametros"):
        parametros_rp_guardados = replace(
            p,
            interes_tecnico_rp=rp_interes_tecnico / 100,
            deslizamiento_rp=rp_deslizamiento / 100,
            gastos_rp=rp_gastos / 100,
            tasa_crecimiento_cai=rp_tasa_crecimiento_cai / 100,
            castigo_riesgo_mercado_cai=rp_castigo_riesgo / 100,
            aplicar_condicion_rv_mayor=rp_aplicar_condicion_rv,
            anio_inicio_condicion_rv=int(rp_anio_inicio_condicion),
            max_anios_proyeccion_rp_tope=int(rp_tope_anios),
            caida_maxima_anual_rp=rp_caida_maxima / 100,
            tasa_crecimiento_cai_volatilidad=rp_volatilidad_cai / 100,
        )
        st.session_state["parametros"] = parametros_rp_guardados
        st.session_state["parametros_vienen_de_disco"] = True
        persistencia.guardar_parametrizacion(parametros_rp_guardados)
        p = parametros_rp_guardados
        st.success(
            "Parametros RP guardados (quedan en el historial). Ya se usaran en el proximo calculo "
            "de esta pestaña y en la linea 'Retiro Programado' de los graficos de Masivo."
        )

    st.info(
        "El IPC usado para el crecimiento de la mesada/SMLV proyectado de Retiro Programado es el "
        "MISMO esquema de 3 tramos (año1/año2/año3+) que se configura en la pestaña 'Parametros "
        "generales' -- ya no hay un 'IPC Observado RP' separado."
    )

    with st.expander("Sobrecosto de mortalidad (sobrecosto_mortalidad_RP.xlsx) -- solo consulta"):
        st.caption("Se aplica automaticamente segun la edad y el sexo del causante, con la misma formula de recargos.")
        st.dataframe(pd.read_csv(_RUTA_SOBRECOSTO), width='stretch')

    with st.expander("Beneficiarios hipoteticos (tablas_sobrecosto_beneficiario_hipotetico.xlsx) -- solo consulta"):
        st.caption(
            "Si el pensionado no tiene beneficiarios, se crea automaticamente un conyuge hipotetico "
            "(siempre valido) segun estas tablas, con la edad y el sexo del causante."
        )
        st.write("Válidos")
        st.dataframe(pd.read_csv(_RUTA_BENEFICIARIO_VALIDOS), width='stretch')
        st.write("Inválidos")
        st.dataframe(pd.read_csv(_RUTA_BENEFICIARIO_INVALIDOS), width='stretch')

    st.divider()
    st.subheader("Datos Pensionado")
    col_rp5, col_rp6, col_rp7 = st.columns(3)
    with col_rp5:
        rp_n_mesadas = st.selectbox("Numero de mesadas", options=[13, 14], index=0, key="rp_n_mesadas")
    with col_rp6:
        rp_fecha_valoracion = st.date_input("Fecha de valoracion", value=__import__("datetime").date.today(), key="rp_fecha_val")
    with col_rp7:
        rp_capital_objetivo = st.number_input(
            "Capital disponible en la cuenta (objetivo que debe igualar la Reserva Matematica RP)",
            min_value=0.0, value=300_000_000.0, step=1_000_000.0, key="rp_capital_objetivo",
        )

    rp_causante = formulario_causante("rp")
    rp_beneficiarios = formulario_beneficiarios("rp")
    if not rp_beneficiarios:
        st.info(
            "No se cargaron beneficiarios: al calcular se creara automaticamente un conyuge "
            "hipotetico segun la edad y el sexo del causante (ver tablas arriba)."
        )

    if st.button("Calcular mesada Retiro Programado", type="primary", key="rp_calcular"):
        p_actualizado = replace(
            p,
            interes_tecnico_rp=rp_interes_tecnico / 100,
            deslizamiento_rp=rp_deslizamiento / 100,
            gastos_rp=rp_gastos / 100,
            tasa_crecimiento_cai=rp_tasa_crecimiento_cai / 100,
            castigo_riesgo_mercado_cai=rp_castigo_riesgo / 100,
            aplicar_condicion_rv_mayor=rp_aplicar_condicion_rv,
            anio_inicio_condicion_rv=int(rp_anio_inicio_condicion),
            max_anios_proyeccion_rp_tope=int(rp_tope_anios),
            caida_maxima_anual_rp=rp_caida_maxima / 100,
            tasa_crecimiento_cai_volatilidad=rp_volatilidad_cai / 100,
        )

        datos = DatosPoliza(
            id_pol="retiro_programado", n_mesadas=rp_n_mesadas, fecha_valoracion=rp_fecha_valoracion,
            smlv=p.smlv, mesada_actual=p.smlv, tasa_interes_real=0.0,
            causante=rp_causante, beneficiarios=rp_beneficiarios,
        )

        with st.spinner("Calculando..."):
            resultado_metodo, resultado_reserva, beneficiarios_usados, pct_sobrecosto = resolver_mesada_rp(
                datos, rp_capital_objetivo, p_actualizado,
            )

        st.divider()
        st.subheader("Resultados")

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Mesada Retiro Programado encontrada", f"{resultado_metodo.valor:,.2f}")
            st.metric("Reserva Matematica RP", f"{resultado_reserva.reserva_matematica_rp:,.2f}")
            st.write("Convergio:", "Si" if resultado_metodo.convergio else "**No**")
        with col_b:
            st.metric("Duracion Macaulay RP", f"{resultado_reserva.duracion_macaulay_rp:,.2f} años")
            st.metric("% Sobrecosto de mortalidad aplicado", f"{pct_sobrecosto*100:.2f}%")

        if len(rp_beneficiarios) == 0:
            ben_h = beneficiarios_usados[0]
            edad_ben_h = edad_en_anios(ben_h.fecha_nacimiento, rp_fecha_valoracion)
            st.caption(
                f"Beneficiario conyuge hipotetico usado: {'Femenino' if ben_h.sexo == 2 else 'Masculino'}, "
                f"{edad_ben_h} años, valido."
            )

        if not resultado_metodo.convergio:
            st.warning("No convergio dentro del numero maximo de iteraciones configurado en 'Parametros generales'.")

        with st.expander("Detalle de la reserva RP"):
            st.write(f"Reserva de amparo basico: {resultado_reserva.reserva_amparo_basico:,.2f}")
            st.write(f"Reserva cambio de grupo: {resultado_reserva.reserva_amparo_basico_cambio_grupo:,.2f}")
            st.write(f"Auxilio funerario: {resultado_reserva.auxilio_funerario:,.2f}")
            st.write(f"Recargo sobrecosto de mortalidad: {resultado_reserva.recargo_sobrecosto_mortalidad:,.2f}")
            st.write(f"Recargo gastos RP: {resultado_reserva.recargo_gastos_rp:,.2f}")

        st.divider()
        st.subheader(
            f"Proyeccion de la mesada por año "
            f"({p_actualizado.max_anios_proyeccion_rp_tope} años, con evolucion de la CAI)"
        )
        st.caption(
            "Cada año se recalcula la mesada con el saldo remanente de la CAI: se restan las "
            f"mesadas pagadas ese año y el saldo crece a la Tasa de Crecimiento de la CAI "
            f"(promedio {p_actualizado.tasa_crecimiento_cai*100:.2f}%, castigada "
            f"{p_actualizado.castigo_riesgo_mercado_cai*100:.2f}% por riesgo de mercado, con "
            f"variacion aleatoria año a año). La mesada pagada nunca crece menos que el mismo "
            "esquema de IPC de 3 tramos + Deslizamiento RP que usa Renta Vitalicia, "
            "pero eso puede exigirle al fondo mas de lo que puede sostener por si solo -- la linea "
            "'Mesada sin piso' muestra lo que el saldo/mortalidad de cada año realmente sostiene. "
            f"La mesada tampoco puede caer mas de {p_actualizado.caida_maxima_anual_rp*100:.0f}% de "
            "un año al siguiente. La condicion 'Renta Vitalicia > Retiro Programado' solo se evalua "
            "desde el año configurado arriba, y solo si esta activada."
        )
        # Horizonte dinamico: se usa el tope duro y la proyeccion se corta
        # sola cuando la CAI deja de sostener el SMLV. (En la pestaña
        # individual no hay una mesada de RV de referencia con la cual
        # comparar, asi que aqui no aplica el corte por "RP < RV".)
        proyeccion = proyectar_rp_dinamico_cai(
            datos, rp_capital_objetivo, p_actualizado,
            max_anios=p_actualizado.max_anios_proyeccion_rp_tope,
        )
        anio_critico = primer_anio_bajo_smlv(proyeccion)

        if anio_critico is not None:
            st.warning(
                f"⚠️ La proyeccion se detiene en **{anio_critico}**: el saldo de la CAI ya no "
                f"alcanza para sostener ni el SMLV por su cuenta (el fondo dejo de ser "
                f"autosuficiente). No se siguen estimando mas años despues de este punto."
            )
        else:
            st.success("El fondo se mantiene autosuficiente (por encima del SMLV) durante todo el horizonte proyectado.")

        proyeccion_grafico = proyeccion.rename(columns={
            "Mesada_Pensional_proyectada": "Mesada pagada (con piso)",
            "Mesada_sin_piso": "Mesada sin piso (lo que el fondo sostiene)",
        })
        base_chart = alt.Chart(proyeccion_grafico).encode(x=alt.X("Anio:O", title="Año"))
        linea_pagada = base_chart.mark_line(color="#1f77b4", point=True).encode(
            y=alt.Y("Mesada pagada (con piso):Q", title="Mesada"),
            tooltip=["Anio", "Mesada pagada (con piso)"],
        )
        linea_sin_piso = base_chart.mark_line(color="#FFA500", point=True, strokeDash=[4, 2]).encode(
            y="Mesada sin piso (lo que el fondo sostiene):Q",
            tooltip=["Anio", "Mesada sin piso (lo que el fondo sostiene)"],
        )
        capas = [linea_pagada, linea_sin_piso]
        st.altair_chart(alt.layer(*capas).resolve_scale(y="shared"), width='stretch')

        with st.expander("Detalle año a año (saldo CAI, piso aplicado y convergencia)"):
            st.dataframe(proyeccion, width='stretch', hide_index=True)

        persistencia.registrar_calculo(
            pagina="individual_retiro_programado",
            cedula=rp_causante.fecha_nacimiento.isoformat(),
            id_cotizacion="retiro_programado",
            entrada={
                "n_mesadas": rp_n_mesadas, "fecha_valoracion": str(rp_fecha_valoracion),
                "capital_objetivo": rp_capital_objetivo,
                "interes_tecnico_rp": rp_interes_tecnico, "deslizamiento_rp": rp_deslizamiento,
                "gastos_rp": rp_gastos, "castigo_riesgo_mercado_cai": rp_castigo_riesgo,
                "causante_fecha_nacimiento": str(rp_causante.fecha_nacimiento),
                "causante_sexo": rp_causante.sexo, "causante_estado": rp_causante.estado,
                "n_beneficiarios": len(rp_beneficiarios),
            },
            salida={
                "mesada_encontrada": resultado_metodo.valor,
                "convergio": resultado_metodo.convergio,
                "reserva_matematica_rp": resultado_reserva.reserva_matematica_rp,
                "duracion_macaulay_rp": resultado_reserva.duracion_macaulay_rp,
                "pct_sobrecosto_mortalidad": pct_sobrecosto,
                "beneficiario_hipotetico_usado": len(rp_beneficiarios) == 0,
            },
        )
        st.caption("Este calculo quedo guardado en el historial (input y output).")

st.divider()
if st.button("Cerrar sesion de actuaria"):
    st.session_state["acceso_actuario_ok"] = False
    st.rerun()
