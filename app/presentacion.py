# -*- coding: utf-8 -*-
"""
Presentación interactiva de la tesis
«Métodos numéricos iterativos aplicados en la cotización de rentas vitalicias».

Ejecutar con:   streamlit run presentacion.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

# Garantiza que estilo.py y nucleo.py se encuentren aunque la aplicación se
# lance desde otra carpeta o con una versión de Streamlit que no añade la
# carpeta del script a la ruta de importación.
_AQUI = str(Path(__file__).resolve().parent)
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import estilo
import nucleo as N
from core.metodos_iterativos import CriterioParada

st.set_page_config(page_title="Métodos iterativos · Rentas vitalicias",
                   page_icon="∮", layout="wide",
                   initial_sidebar_state="expanded")
estilo.aplicar()

# Nombre del director, tal como debe aparecer en la portada. Vacío = no se muestra.
DIRECTOR = "Vladimir Moreno Gutiérrez"


# =====================================================================
# Utilidades
# =====================================================================

def dec(x: float, d: int = 2) -> str:
    """Número con coma decimal y punto de miles (convención colombiana)."""
    return f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


_SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def sci(x: float, d: int = 1) -> str:
    """Notación científica con coma decimal: 1,9·10⁻²."""
    if x == 0 or not np.isfinite(x):
        return "0" if x == 0 else "—"
    mant, exp = f"{x:.{d}e}".split("e")
    exp = int(exp)
    if exp == 0:
        return mant.replace(".", ",")
    return f"{mant.replace('.', ',')}·10{str(exp).translate(_SUP)}"


def sci_html(x: float, d: int = 1) -> str:
    """Como sci(), con el exponente en <sup>: las cifras grandes usan una fuente
    serif que no trae todos los superíndices Unicode."""
    if x == 0 or not np.isfinite(x):
        return "0" if x == 0 else "—"
    mant, exp = f"{x:.{d}e}".split("e")
    exp = int(exp)
    if exp == 0:
        return mant.replace(".", ",")
    return f"{mant.replace('.', ',')}·10<sup>{str(exp).replace('-', '−')}</sup>"


N_ANIOS_MAX = 110      # años de vigencia máxima: número de factores de deslizamiento


def C(nombre: str, respaldo: str = "—") -> str:
    """Cifra citada del documento (macro \\datoX de tex/datos_numericos.tex)."""
    return N.cifra(nombre, respaldo)


def ancho_racimo(p) -> float:
    """Extensión multiplicativa de cada racimo de quiebres (Teorema 4.10):
    el racimo que nace en kS va de kS a kS·ancho. Dos años con IPC propio
    (primer y segundo año) y el resto con el IPC de largo plazo."""
    desl, lp = p.delta_deslizamiento, p.ipc_objetivo_largo_plazo
    rho = (1 + lp + desl) / (1 + lp)
    return (rho ** (N_ANIOS_MAX - 2)
            * (1 + p.ipc_primer_anio + desl) * (1 + p.ipc_segundo_anio + desl)
            / ((1 + p.ipc_primer_anio) * (1 + p.ipc_segundo_anio)))


# =====================================================================
# Navegación
# =====================================================================

SECCIONES = [
    "Portada",
    "1 · El problema",
    "2 · Anatomía de la función",
    "3 · ¿Cuándo hay solución?",
    "4 · La derivada es el factor de renta",
    "5 · Los métodos, uno a uno",
    "6 · La carrera",
    "7 · Terminación finita",
    "8 · Laboratorio de sensibilidad",
    "9 · Renta vitalicia vs. retiro programado",
    "10 · Las variables del modelo",
    "11 · Del teorema a producción",
    "12 · Conclusiones y trabajo futuro",
]


def _ir_a(indice: int) -> None:
    st.session_state["seccion"] = SECCIONES[indice]


with st.sidebar:
    st.markdown(
        '<div class="marca"><span>Tesis de maestría en matemáticas</span>'
        'Métodos numéricos iterativos aplicados en la cotización de rentas vitalicias</div>',
        unsafe_allow_html=True)
    seccion = st.radio("Secciones", SECCIONES, key="seccion", label_visibility="collapsed")
    INDICE = SECCIONES.index(seccion)
    st.progress(INDICE / (len(SECCIONES) - 1))
    st.caption(f"Sección {INDICE} de {len(SECCIONES) - 1}" if INDICE else "Portada")
    st.markdown("---")
    st.caption("Eduardo Lagos Durán")
    if DIRECTOR:
        st.caption(f"Director: {DIRECTOR}")
    st.caption("Pontificia Universidad Javeriana")

P = N.parametros()
S = P.smlv
ANCHO = ancho_racimo(P)


# =====================================================================
# Portada
# =====================================================================

if seccion == SECCIONES[0]:
    director = f'<div class="sub" style="font-size:1rem;margin:.4rem 0 0 0">Director: {DIRECTOR}</div>' \
        if DIRECTOR else ""
    st.markdown(f"""
    <div class="portada">
      <div class="kicker">Pontificia Universidad Javeriana · Facultad de Ciencias · Maestría en Matemáticas</div>
      <h1>Métodos numéricos iterativos<br>aplicados en la cotización de rentas vitalicias</h1>
      <div class="sub">Estructura no suave, convergencia finita y eficiencia computacional
      en la ecuación de equivalencia actuarial</div>
      <div class="autor">Eduardo Lagos Durán</div>
      {director}
    </div>
    """, unsafe_allow_html=True)

    estilo.lead(
        "Cotizar una renta vitalicia inmediata es resolver una ecuación no lineal: hallar "
        "la mesada inicial <em>M</em> que iguala el valor presente actuarial de las "
        "obligaciones incluidas con el capital objetivo, sobre una misma base de "
        "valoración. Esta presentación estudia esa ecuación en un modelo particular —el "
        "cotizador implementado—, qué estructura tiene la función que hay que invertir, "
        "qué garantías se siguen de ella y cuánto cuesta resolverla con cada método.")

    estilo.cifras([
        ("VP(M) = KA", "la ecuación"),
        (C("NMetodos", "19"), "métodos comparados", "naranja"),
        (C("NEscenarios", "25"), "escenarios de valoración", "naranja"),
        (f"{C('AceleracionNewton', '10,8')}×", "razón de llamadas<br>bisección / Newton analítico",
         "verde"),
        (f"{C('AhorroDerivada', '59')} %", "menos llamadas que con<br>diferencias finitas", "verde"),
    ])

    st.markdown("### Tres resultados estructurales, bajo las hipótesis del modelo")
    c1, c2, c3 = st.columns(3)
    with c1:
        estilo.bloque("Región plana y capital mínimo",
                      "La extensión de <i>VP</i> a <i>M</i>&nbsp;&ge;&nbsp;0 es <b>constante</b> en "
                      "[0,&nbsp;SMLV], por el piso pensional. En el dominio admisible "
                      "<i>M</i>&nbsp;&ge;&nbsp;SMLV existe una solución única si y solo si "
                      "KA&nbsp;&ge;&nbsp;VP(SMLV); en la igualdad, <i>M</i>&nbsp;=&nbsp;SMLV.")
    with c2:
        estilo.bloque("Afín a trozos, en tres racimos",
                      f"<i>VP</i> es <b>afín a trozos</b>, con a lo sumo {C('NQuiebresMax', '333')} "
                      "umbrales candidatos agrupados en tres racimos geométricos alrededor de "
                      "1, 5 y 10 salarios mínimos, para la parametrización considerada. Un "
                      "umbral candidato puede no producir un salto efectivo.")
    with c3:
        estilo.bloque("Pérdida de convexidad",
                      "El auxilio funerario <b>puede destruir la convexidad</b>: entre los racimos "
                      "II y III la pendiente decrece. La convexidad deja entonces de justificar "
                      "la convergencia monótona de Newton.")

    estilo.bloque(
        "Consecuencia para los métodos",
        "Las derivadas laterales y el <i>B</i>-subdiferencial de <i>VP</i> tienen expresión "
        "cerrada, interpretable como factor marginal de renta actuarial. Newton con la "
        "pendiente exacta alcanza la raíz <b>en un paso</b> cuando la clausura del tramo "
        "seleccionado contiene también la solución; el número de pasos no se identifica con "
        "el de tramos atravesados. Una salvaguarda de encaje con <b>bisección periódica</b> "
        "da convergencia global bajo las condiciones establecidas. Las mesadas de la muestra "
        "examinada caen en un tramo afín; eso no describe la cartera completa ni el mercado.",
        "aporte")

    estilo.nota("Use el menú lateral o los botones al pie de cada sección para recorrer la "
                "presentación. Las gráficas se calculan en vivo sobre el motor actuarial; las "
                "cifras consolidadas que se citan del documento (tablas y macros numéricas) se "
                "leen de <code>tex/</code>, la copia del proyecto de Overleaf.")


# =====================================================================
# 1 · El problema
# =====================================================================

elif seccion == SECCIONES[1]:
    st.markdown("# El problema de cotización")
    estilo.lead(
        "En la renta vitalicia inmediata, el capital destinado a financiar la pensión se "
        "transfiere a una aseguradora a cambio de los pagos que correspondan mientras el "
        "afiliado o sus beneficiarios conserven el derecho. En el modelo del cotizador, la "
        "equivalencia iguala el capital objetivo con el valor presente esperado de las "
        "obligaciones incluidas; la igualdad no identifica por sí sola esa reserva con una "
        "prima comercial completa.")

    n_meses = C("NMeses", "1439")
    n_meses_txt = dec(float(n_meses), 0) if n_meses.isdigit() else n_meses
    corte = C("VigenciaCorte", "1321")
    corte_txt = dec(float(corte), 0) if corte.isdigit() else corte

    c1, c2 = st.columns([1.05, 1])
    with c1:
        st.latex(r"\text{hallar } M^*\ge S_0:\qquad f(M^*)\;=\;VP(M^*)\;-\;KA\;=\;0")
        st.markdown("donde la reserva matemática es")
        st.latex(r"VP(M)=\frac{(1+\gamma)\,RAB(M)+AUF(M)}{1-g}")
        st.markdown("""
La función combina supervivencias tabuladas, indexación, un piso pensional
expresado con un máximo y un auxilio funerario acotado entre 5 y 10 salarios
mínimos, expresado con un recorte. En cada tramo afín la inversión es algebraica,
pero localizar el tramo pertinente y controlar los casos de frontera es lo que
justifica estudiar los métodos iterativos que resuelven la ecuación.
""")

    with c2:
        ms = N.tiempo_por_llamada_ms()
        estilo.bloque("Por qué importa el método",
                      "La cotización repetida y la proyección anual del retiro programado "
                      "resuelven muchos problemas de raíz. Cada llamada al motor construye "
                      "flujos y probabilidades del grupo familiar y los descuenta sobre "
                      f"{n_meses_txt} meses: en este equipo, unos "
                      f"<b>{dec(ms, 1)} ms</b>. Ese trabajo domina las operaciones escalares "
                      "del método; por eso el costo se mide en <b>llamadas efectivas al "
                      "motor</b>, no en iteraciones.")
        estilo.cifras([(n_meses_txt, "meses proyectados"),
                       (f"≈ {dec(ms, 1)} ms", "por llamada al motor<br>en este equipo", "naranja"),
                       (f"≈ {C('AniosVigencia', '110,1')}",
                        f"años hasta el corte<br>de vigencia (mes {corte_txt})")])

    st.markdown("con el valor presente actuarial del amparo básico")
    st.latex(r"RAB(M)=\sum_{t=1}^{%s}" % n_meses + r"""
    \underbrace{\max\{M\tau_t,\,S_t\}}_{\text{mesada con piso legal}}\;
    \underbrace{\nu_t\,\kappa_t}_{\text{vigencia y pagos}}\;
    \underbrace{CONAB(t{+}1)}_{\text{supervivencia}}\;
    \underbrace{v_{t+1}}_{\text{descuento}}""")

    st.markdown("## El grupo asegurado y su supervivencia")
    st.markdown("La renta se paga mientras **al menos uno** de los integrantes conserve "
                "el derecho. Eso es lo que convierte el problema en multivida.")
    st.latex(r"CONAB(t)=\mathbb{P}\!\left(\max_{y\in Y}T_y>t\right)"
             r"=1-\prod_{y\in Y}\bigl(1-{}_tp_y\bigr)")

    con_hijo = st.toggle("Añadir un hijo menor al grupo", value=False,
                         help="Hijo con derecho temporal hasta los 25 años.")
    with st.spinner("Construyendo las tablas de supervivencia…"):
        sv = N.supervivencia(con_hijo)
    d_ref = N.poliza(con_hijo=con_hijo)
    etiquetas = {"causante": f"causante (hombre, {N.edad_en(d_ref.causante.fecha_nacimiento)})"}
    for b in d_ref.beneficiarios:
        if b.tipo_beneficiario == N.config.COD_CONYUGE:
            etiquetas["cónyuge"] = f"cónyuge (mujer, {N.edad_en(b.fecha_nacimiento)})"
        elif b.tipo_beneficiario == N.config.COD_HIJO:
            etiquetas["hijo"] = f"hijo ({N.edad_en(b.fecha_nacimiento)}, derecho hasta los 25)"
    colores = {"causante": N.AZUL, "cónyuge": N.NARANJA, "hijo": N.MORADO}

    vidas = [c for c in sv.columns if c not in ("t", "CONAB")]
    tope = 55.0
    sv = sv[sv.t <= tope]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sv.t, y=sv[vidas].max(axis=1), line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=sv.t, y=sv.CONAB, line=dict(color=N.VERDE, width=3),
                             fill="tonexty", fillcolor="rgba(0,158,115,.16)",
                             name="conjunta CONAB(t)",
                             hovertemplate="t = %{x:.1f} años<br>CONAB = %{y:.4f}<extra></extra>"))
    for v in vidas:
        fig.add_trace(go.Scatter(x=sv.t, y=sv[v], line=dict(color=colores.get(v, N.GRIS), width=1.8),
                                 name=etiquetas.get(v, v),
                                 hovertemplate="t = %{x:.1f} años<br>p = %{y:.4f}<extra></extra>"))
    t_mitad = float(sv.t[sv.CONAB <= 0.5].iloc[0]) if (sv.CONAB <= 0.5).any() else tope
    fig.add_annotation(x=min(t_mitad + 4, tope - 6), y=0.72, text="ganancia de<br>diversificación",
                       showarrow=False, font=dict(color=N.VERDE, size=12))
    fig.update_layout(**N.plantilla_plotly(), height=420,
                      xaxis_title="t  [años desde la valoración]", yaxis_title="probabilidad",
                      title="Supervivencia individual y conjunta con las tablas colombianas RV-08")
    estilo.grafica(fig)
    if con_hijo:
        estilo.nota("El hijo añade años de derecho, pero en un periodo en que ambos padres siguen "
                    "vivos con alta probabilidad: en esta póliza su aporte a CONAB es pequeño. "
                    "La regla «más beneficiarios, más caro» depende de cuánto se superpongan "
                    "los periodos de derecho. CONAB supone independencia entre vidas, una "
                    "hipótesis del modelo cuyo efecto no se cuantifica aquí.")


# =====================================================================
# 2 · Anatomía de la función
# =====================================================================

elif seccion == SECCIONES[2]:
    st.markdown("# Anatomía de la función de valoración")
    estilo.lead(
        "Esta es la sección central. Los controles de la izquierda alteran las hipótesis "
        "del modelo; observe qué le ocurre a la <b>pendiente</b> de <i>VP</i>. "
        "Los racimos de quiebres los separa el deslizamiento del salario mínimo: sin "
        "deslizamiento colapsan en tres quiebres aislados.")

    ctrl, graf = st.columns([1, 2.6])
    with ctrl:
        st.markdown("### Hipótesis")
        desl = st.slider("Deslizamiento del salario mínimo (%)", 0.0, 3.0,
                         P.delta_deslizamiento * 100, 0.05, format="%.2f",
                         help="Excedente con que el salario mínimo crece por encima "
                              "de la inflación. Es el parámetro que genera los quiebres.")
        ipc_lp = st.slider("IPC de largo plazo (%)", 1.0, 8.0,
                           P.ipc_objetivo_largo_plazo * 100, 0.25, format="%.2f")
        tasa = st.slider("Interés técnico real (%)", 1.0, 8.0, 4.20, 0.10)
        st.markdown("### Ventana")
        rango = st.radio("Rango en múltiplos del SMLV",
                         options=["0 – 15", "0,8 – 1,4", "4,8 – 6,0", "9,8 – 11,4"],
                         index=0, horizontal=True,
                         help="Las tres últimas ventanas acercan la vista a cada racimo "
                              "de quiebres.")
        con_hijo = st.checkbox("Añadir un hijo menor", value=False)

    lims = {"0 – 15": (0.02, 15.0), "0,8 – 1,4": (0.80, 1.40),
            "4,8 – 6,0": (4.80, 6.00), "9,8 – 11,4": (9.80, 11.40)}[rango]

    p2 = N.parametros(delta_deslizamiento=desl / 100,
                      ipc_objetivo_largo_plazo=ipc_lp / 100)
    d2 = N.poliza(tasa=tasa / 100, con_hijo=con_hijo)
    clave = N._clave(d2, p2)

    with graf:
        with st.spinner("Evaluando el motor actuarial en 300 puntos…"):
            df = N.curva_vp(d2, p2, clave, lims[0] * S, lims[1] * S, 300)

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.56, 0.44], vertical_spacing=0.07,
                            subplot_titles=("Valor presente actuarial VP(M)",
                                            "Derivada lateral derecha VP′₊(M)"))
        x = df.M / S
        fig.add_trace(go.Scatter(x=x, y=df.VP, line=dict(color=N.AZUL, width=2.4),
                                 name="VP(M)", hovertemplate="M = %{x:.3f} SMLV<br>"
                                 "VP = %{y:,.0f}<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df.dVP_der, line=dict(color=N.ROJO, width=2.0),
                                 name="VP′₊(M)", hovertemplate="M = %{x:.3f} SMLV<br>"
                                 "VP′ = %{y:.4f}<extra></extra>"), row=2, col=1)

        rho = (1 + ipc_lp / 100 + desl / 100) / (1 + ipc_lp / 100)
        ancho = ancho_racimo(p2)
        for base in (1.0, 5.0, 10.0):
            x0, x1 = base, base * ancho
            if x1 >= lims[0] and x0 <= lims[1]:
                for r in (1, 2):
                    fig.add_vrect(x0=max(x0, lims[0]), x1=min(x1, lims[1]),
                                  fillcolor=N.NARANJA, opacity=.16, line_width=0,
                                  row=r, col=1)
        if lims[0] < 1.0:
            for r in (1, 2):
                fig.add_vrect(x0=lims[0], x1=1.0, fillcolor="#999", opacity=.13,
                              line_width=0, row=r, col=1)

        fig.update_layout(**N.plantilla_plotly(), height=560, showlegend=False,
                          hovermode="x unified")
        fig.update_xaxes(title_text="mesada inicial M  [múltiplos del SMLV]", row=2, col=1)
        fig.update_yaxes(title_text="pesos", row=1, col=1)
        fig.update_yaxes(title_text="pendiente", row=2, col=1)
        estilo.grafica(fig)

    c1, c2 = st.columns(2)
    with c1:
        estilo.bloque(
            "Teorema · Caracterización de los quiebres",
            "Los puntos de no diferenciabilidad de <i>VP</i> están <b>contenidos</b> en "
            "{<i>S</i><sub>0</sub>&rho;<sub>n</sub>} &cup; {5<i>S</i><sub>0</sub>&rho;<sub>n</sub>} &cup; "
            "{10<i>S</i><sub>0</sub>&rho;<sub>n</sub>}, <i>n</i> = 0,…,110, con "
            "&rho;<sub>n</sub>=&phi;<sub>n</sub>/&tau;<sub>n</sub> creciente: a lo sumo 333 umbrales candidatos en "
            f"tres racimos geométricos de razón <b>{dec(rho, 6)}</b> por año, que se extienden "
            f"hasta <b>{dec(ancho, 4)}</b> veces su origen. El horizonte finito acota los "
            "candidatos; no todos producen un salto efectivo.")
    with c2:
        if desl < 0.02:
            estilo.bloque("Sin deslizamiento, sin racimos",
                          "Con deslizamiento nulo los tres racimos colapsan en tres puntos "
                          "aislados: <i>VP</i> pasa a tener solo tres quiebres y el problema "
                          "se vuelve trivial. Suba el control y véalos abrirse.", "aporte")
        elif ancho > 4.0:
            estilo.bloque("Racimos solapados",
                          "Con este deslizamiento los racimos se ensanchan hasta solaparse y "
                          "<b>desaparece</b> la región afín entre ellos: la raíz deja de estar, "
                          "en general, en un tramo largo. La estructura favorable del caso "
                          "examinado depende de la política salarial.", "critica")
        else:
            estilo.bloque(
                "Corolario · Región afín",
                f"En [<b>{dec(ancho, 3)}</b>,&nbsp;<b>5</b>] salarios mínimos la función es "
                "<b>afín</b>. Las mesadas de los dos conjuntos reales examinados "
                f"({C('NReales', '9')} cotizaciones de renta vitalicia y {C('NRealesRP', '7')} "
                f"registros adicionales) caen ahí, entre {C('MultMin', '1,43')} y "
                f"{C('MultMax', '2,28')} SMLV; la observación no describe la cartera completa. "
                "Con la pendiente exacta y arrancando en el mismo tramo, Newton termina en un paso.",
                "aporte")

    st.markdown("### La no linealidad, amplificada")
    st.markdown("A escala natural *VP* parece una recta. Restándole la cuerda que une sus "
                "extremos, la estructura lineal a trozos aparece amplificada mil veces. "
                "La gráfica usa las mismas hipótesis de los controles.")
    with st.spinner("Evaluando el motor actuarial en 360 puntos…"):
        dr = N.curva_vp(d2, p2, clave, 1.0 * S, 15.0 * S, 360)
    xr = dr.M / S
    cuerda = dr.VP.iloc[0] + (dr.VP.iloc[-1] - dr.VP.iloc[0]) * (dr.M - dr.M.iloc[0]) / (dr.M.iloc[-1] - dr.M.iloc[0])
    resid = dr.VP - cuerda
    amp = float(np.abs(resid).max() / (dr.VP.iloc[-1] - dr.VP.iloc[0]))
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.09,
                        subplot_titles=("(a) VP a escala natural: indistinguible de una recta",
                                        "(b) VP menos su cuerda: aparece la estructura"))
    fig.add_trace(go.Scatter(x=xr, y=dr.VP, line=dict(color=N.AZUL, width=2.2),
                             hovertemplate="M = %{x:.3f} SMLV<br>VP = %{y:,.0f}<extra></extra>"),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=xr, y=resid, line=dict(color=N.ROJO, width=2.0),
                             hovertemplate="M = %{x:.3f} SMLV<br>VP − cuerda = %{y:,.0f}<extra></extra>"),
                  row=1, col=2)
    for base in (1.0, 5.0, 10.0):
        if base <= 15:
            fig.add_vrect(x0=base, x1=min(base * ancho, 15.0), fillcolor=N.NARANJA,
                          opacity=.18, line_width=0, row=1, col=2)
    fig.add_hline(y=0, line=dict(color="#444", width=1), row=1, col=2)
    fig.add_annotation(xref="x2 domain", yref="y2 domain", x=0.5, y=0.04, showarrow=False,
                       text=f"amplitud relativa ≈ {sci(amp)}", font=dict(size=11, color=N.GRIS))
    fig.update_layout(**N.plantilla_plotly(), height=360, showlegend=False)
    fig.update_xaxes(title_text="M  [múltiplos del SMLV]")
    estilo.grafica(fig)


# =====================================================================
# 3 · ¿Cuándo hay solución?
# =====================================================================

elif seccion == SECCIONES[3]:
    st.markdown("# ¿Cuándo hay solución?")
    estilo.lead(
        "La existencia y la unicidad suelen justificarse con monotonía estricta. Pero la "
        "extensión de <i>VP</i> a [0,&nbsp;SMLV] es <b>constante</b> (teorema de la región "
        "plana): por debajo del salario mínimo, el piso pensional domina y el costo del "
        "contrato deja de depender de la mesada nominal contratada.")

    d = N.poliza()
    clave = N._clave(d, P)
    ka_min = N.vp_en(d, P, clave, S)

    st.markdown("### Mueva el capital disponible y observe los tres regímenes")
    frac = st.slider("Capital disponible, en múltiplos del capital mínimo",
                     0.70, 2.20, 1.45, 0.01)
    ka = ka_min * frac

    with st.spinner("Evaluando el motor actuarial en 220 puntos…"):
        df = N.curva_vp(d, P, clave, 0.15 * S, 3.4 * S, 220)

    fig = go.Figure()
    fig.add_vrect(x0=0.15, x1=1.0, fillcolor="#999", opacity=.14, line_width=0,
                  annotation_text="región plana", annotation_position="top left",
                  annotation_font_size=11)
    fig.add_trace(go.Scatter(x=df.M / S, y=df.VP - ka, line=dict(color=N.AZUL, width=2.6),
                             name="f(M) = VP(M) − KA",
                             hovertemplate="M = %{x:.3f} SMLV<br>f = %{y:,.0f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#444", width=1))

    igual = abs(frac - 1.0) < 1e-9
    if frac > 1.0:
        m = df.M.to_numpy(); v = (df.VP - ka).to_numpy()
        i = int(np.argmin(np.abs(v)))
        fig.add_trace(go.Scatter(x=[m[i] / S], y=[0], mode="markers",
                                 marker=dict(color=N.VERDE, size=14, symbol="circle"),
                                 name="solución única"))
    elif igual:
        fig.add_trace(go.Scatter(x=[1.0], y=[0], mode="markers",
                                 marker=dict(color=N.VERDE, size=14, symbol="circle"),
                                 name="solución admisible M = SMLV"))
        fig.add_shape(type="line", x0=0.15, x1=1.0, y0=0, y1=0,
                      line=dict(color=N.ROJO, width=4, dash="dot"))
    fig.update_layout(**N.plantilla_plotly(), height=420,
                      xaxis_title="mesada inicial M  [múltiplos del SMLV]",
                      yaxis_title="f(M)  [pesos]")
    estilo.grafica(fig)
    estilo.nota("El dominio admisible del problema es M ≥ SMLV. La franja gris es la "
                "extensión matemática a [0, SMLV], que se usa para estudiar la estructura.")

    c1, c2 = st.columns([1, 1.25])
    with c1:
        estilo.cifras([
            (N.millones(ka_min), "capital mínimo KA<sub>mín</sub> = VP(SMLV)"),
            (N.millones(ka), "capital disponible", "naranja"),
        ])
    with c2:
        if frac < 1.0:
            estilo.bloque("Sin solución",
                          "El capital no alcanza ni para financiar la pensión mínima: <i>f</i> "
                          "nunca corta el eje. La insuficiencia debe diagnosticarse comparando "
                          "KA con VP(SMLV), con una sola evaluación. El fracaso de un método no "
                          "basta: también puede deberse a estancamiento o a una raíz por encima "
                          "del extremo superior del intervalo (sección 11).", "critica")
        elif igual:
            estilo.bloque("Capital exactamente mínimo",
                          "En el dominio admisible [SMLV,&nbsp;&infin;) la solución es "
                          "<b>única</b>: M&nbsp;=&nbsp;SMLV. Solo en la extensión a "
                          "[0,&nbsp;&infin;) aparece un <b>continuo</b> de soluciones, todo "
                          "[0,&nbsp;SMLV] (línea punteada): es ahí donde la monotonía estricta "
                          "falla.", "critica")
        else:
            estilo.bloque("Solución única",
                          "Por encima del mínimo, <i>VP</i> es continua y estrictamente "
                          "creciente en [SMLV,&nbsp;&infin;), y tiende a infinito. "
                          "Existe una única mesada admisible, M*&nbsp;&gt;&nbsp;SMLV.", "aporte")

    estilo.bloque(
        "Corolario · Condición de capital mínimo",
        "Sea KA<sub>mín</sub>&nbsp;=&nbsp;VP(SMLV). En el dominio admisible [SMLV,&nbsp;&infin;) el "
        "problema tiene <b>ninguna</b> solución si KA&nbsp;&lt;&nbsp;KA<sub>mín</sub>, la solución "
        "única <b>M&nbsp;=&nbsp;SMLV</b> si KA&nbsp;=&nbsp;KA<sub>mín</sub> y <b>una única</b> "
        "M&nbsp;&gt;&nbsp;SMLV si KA&nbsp;&gt;&nbsp;KA<sub>mín</sub>. En la extensión a "
        "[0,&nbsp;&infin;), la igualdad tiene como conjunto de soluciones todo [0,&nbsp;SMLV]. "
        f"Para la póliza de referencia, KA<sub>mín</sub>&nbsp;=&nbsp;{C('KAmin')} pesos.")
    estilo.bloque(
        "Crítica · Diagnóstico de insuficiencia y fallo numérico",
        "La implementación busca la raíz en [S<sub>0</sub>,&nbsp;25S<sub>0</sub>]. La "
        "insuficiencia se diagnostica comparando KA con VP(S<sub>0</sub>). El fracaso de un "
        "método no basta: también puede deberse a estancamiento o a una raíz por encima del "
        "extremo superior. Devolver el salario mínimo en esos casos no certifica la igualdad "
        "actuarial (recomendación R1, sección 11).", "critica")


# =====================================================================
# 4 · La derivada es el factor de renta
# =====================================================================

elif seccion == SECCIONES[4]:
    st.markdown("# La derivada es el factor de renta")
    estilo.lead(
        "Una función lineal a trozos no tiene derivada en sus quiebres, pero sí tiene "
        "dos derivadas laterales, y ambas admiten expresión cerrada. Ese par es el "
        "<i>B</i>-subdiferencial que usa el método de Newton semisuave, y resulta tener "
        "un significado actuarial preciso.")

    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.latex(r"VP'_{+}(M)=\sum_{t:\,a_tM\,\ge\, b_t} w_t a_t"
                 r"\;+\sum_{t:\,5b_t\,\le\, a_tM\,<\,10b_t} c_t a_t")
        st.latex(r"VP'_{-}(M)=\sum_{t:\,a_tM\,>\, b_t} w_t a_t"
                 r"\;+\sum_{t:\,5b_t\,<\, a_tM\,\le\, 10b_t} c_t a_t")
        st.markdown(r"$\partial_B VP(M)=\{VP'_-(M),\,VP'_+(M)\}$ y el subdiferencial de Clarke "
                    r"es el intervalo entre ambos. Fuera de los quiebres coinciden y $VP$ es "
                    r"diferenciable. El cálculo reutiliza los vectores ya construidos para evaluar "
                    r"$VP$ y añade tres productos escalares sobre máscaras booleanas.")
    with c2:
        estilo.bloque(
            "Teorema · Interpretación actuarial",
            "Donde todos los términos de renta están activos y ninguno del auxilio lo está,"
            "<div style='text-align:center;margin:.5rem 0'><i>VP</i>′(<i>M</i>) = "
            "(1+&gamma;)/(1&minus;<i>g</i>) &middot; <i>ä</i><sub><i>Y</i></sub><sup>(&tau;)</sup></div>"
            "La derivada respecto de la mesada <b>es el factor de renta actuarial</b> del grupo, "
            "recargado por gastos y cambio de grupo. El paso de Newton &minus;<i>f</i>/<i>VP</i>′ "
            "es el exceso de capital dividido por el costo de un peso de mesada: exactamente "
            "el ajuste que un actuario haría a mano.", "aporte")

    st.markdown("### Explórela en cualquier punto")
    d = N.poliza()
    clave = N._clave(d, P)
    m_smlv = st.slider("Mesada M (múltiplos del SMLV)", 0.90, 12.0, 2.41, 0.01,
                       help="1,00 · 5,00 · 10,00 son quiebres exactos: pruébelos.")
    M = m_smlv * S
    v = N.valor_y_derivadas(d, P, clave, M)
    en_quiebre = abs(v["izq"] - v["der"]) > 1e-9 * max(1.0, abs(v["der"]))
    if v["der"] > 0:
        estilo.cifras([
            (dec(v["izq"], 4), "VP′₋(M)"),
            (dec(v["der"], 4), "VP′₊(M)", "rojo" if en_quiebre else ""),
            (dec(1e6 / v["der"], 1), "pesos de mesada por<br>millón de capital", "verde"),
            (dec(v["VP"] / (M * v["der"]), 4), "condicionamiento<br>relativo κ", "naranja"),
        ])
    else:
        estilo.cifras([(dec(v["izq"], 4), "VP′₋(M)"), (dec(v["der"], 4), "VP′₊(M)", "rojo"),
                       ("—", "región plana: VP no depende de M", "naranja")])

    if m_smlv < 1.0:
        estilo.bloque("Región plana", "Por debajo del salario mínimo ambas derivadas son "
                      "<b>cero</b>: el piso legal domina en todos los periodos. Es la "
                      "<i>BD</i>-regularidad la que falla aquí, y la razón por la que el "
                      "problema solo está bien planteado por encima de SMLV.", "critica")
    elif en_quiebre:
        estilo.bloque("M está en un quiebre",
                      f"El subdiferencial tiene dos elementos: {dec(v['izq'], 4)} por la "
                      f"izquierda y {dec(v['der'], 4)} por la derecha. Los dos corresponden a "
                      "incluir o excluir del factor de renta los periodos en que la mesada "
                      "queda exactamente sobre el piso legal o sobre una frontera del auxilio "
                      "funerario. Mire abajo qué hacen aquí las diferencias finitas.", "critica")
    else:
        estilo.bloque("M está en un tramo afín",
                      f"Cada peso adicional de mesada mensual cuesta <b>{dec(v['der'], 2)}</b> "
                      f"pesos de capital. Hay {dec(v['renta'], 0)} periodos de renta y {dec(v['auf'], 0)} del "
                      "auxilio funerario activos. El condicionamiento relativo "
                      f"κ = VP/(M·VP′) = {dec(v['VP'] / (M * v['der']), 4)}: un error relativo "
                      "en el capital pasa a la mesada casi sin amplificarse. Ese buen "
                      "condicionamiento facilita el problema, pero no garantiza por sí solo que "
                      "todo método alcance precisión de máquina: también intervienen su "
                      "convergencia, las tolerancias y el redondeo.", "aporte")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Diferencias finitas contra la derivada exacta")
        pasos = (1.0, 100.0, 10_000.0)
        aprox = N.diferencias_centrales(d, P, clave, M, pasos)
        estilo.tabla(pd.DataFrame({
            "Paso h (pesos)": [dec(h, 0) for h in pasos],
            "(VP(M+h) − VP(M−h)) / 2h": [dec(a, 6) for a in aprox],
            "Error frente a VP′₊": [sci(abs(a - v['der'])) for a in aprox],
        }))
        st.caption("Si la ventana [M−h, M+h] no contiene quiebres, la diferencia centrada es "
                   "exacta en aritmética exacta; lo que se ve es redondeo, acotado por "
                   "(η₊+η₋)/2h. En un quiebre exacto da la pendiente media: pertenece al "
                   "subdiferencial de Clarke, pero no es ninguna de las dos derivadas laterales "
                   "que usa Newton semisuave. Si la ventana contiene un quiebre y M no lo es, "
                   "mezcla pendientes y no tiene por qué ser la derivada en M. Cuesta además "
                   "dos llamadas adicionales al motor por iteración.")
    with c2:
        st.markdown("### Newton como una división")
        dKA = st.slider("Exceso de capital ΔKA (millones de pesos)", -200, 200, 50, 5)
        paso = dKA * 1e6 / v["der"] if v["der"] > 0 else float("nan")
        if np.isfinite(paso):
            vp_nuevo = N.valor_y_derivadas(d, P, clave, M + paso)["VP"]
            residuo = vp_nuevo - (v["VP"] + dKA * 1e6)
            estilo.cifras([(N.pesos(paso), "ΔM = ΔKA / VP′₊(M)"),
                           (sci_html(abs(residuo)), "residuo tras un paso<br>(pesos de capital)",
                            "verde" if abs(residuo) < 1e-2 else "rojo")])
            st.caption("Si M y M+ΔM caen en el mismo tramo afín, un único paso de Newton da la "
                       "raíz en aritmética exacta: el residuo es redondeo de máquina. Si el paso "
                       "cruza un racimo, el residuo deja de ser nulo y hacen falta más pasos.")
        else:
            st.caption("En la región plana la pendiente es cero y el paso de Newton no está definido.")

    estilo.bloque(
        "Un detalle de implementación con consecuencias analíticas · R2",
        "En <i>M</i>&nbsp;=&nbsp;<i>S</i><sub>0</sub> el motor original calculaba la derivada "
        "sobre la rama de crecimiento equivocada. El <b>valor</b> de <i>VP</i> es el mismo por "
        "las dos ramas; la <b>derivada</b>, no: la fórmula ingenua devuelve 249,06 frente al "
        f"valor correcto 7,23, un factor de 34. El motor corregido da hoy "
        f"<b>{dec(N.valor_y_derivadas(d, P, clave, S)['der'], 4)}</b> en ese punto "
        "(póngalo en 1,00 arriba). Una bisección o una secante que arrancan en el extremo "
        "inferior del intervalo, como en producción, evalúan justamente ahí.", "critica")


# =====================================================================
# 5 · Los métodos, uno a uno
# =====================================================================

elif seccion == SECCIONES[5]:
    st.markdown("# Los métodos, uno a uno")
    estilo.lead("Elija un método y observe cómo construye su sucesión de aproximaciones "
                "sobre la función de valoración de la póliza de referencia. El costo se cuenta "
                "como en el banco de pruebas: llamadas efectivas al motor, con memoria propia "
                "por ejecución.")

    c1, c2, c3 = st.columns([1.1, 1, 1])
    with c1:
        metodo = st.selectbox("Método", N.METODOS_DISPONIBLES,
                              index=N.METODOS_DISPONIBLES.index("Newton semisuave"))
    with c2:
        objetivo_smlv = st.slider("Raíz objetivo (múltiplos del SMLV)", 1.02, 12.0, 2.41, 0.01)
    with c3:
        tol = st.select_slider("Tolerancia en el residuo",
                               options=[100.0, 10.0, 1.0, 0.1, 0.001, 1e-6],
                               value=1.0, format_func=lambda v: f"{v:g} peso" + ("" if v == 1 else "s"))

    d = N.poliza()
    clave = N._clave(d, P)
    capital = N.vp_en(d, P, clave, objetivo_smlv * S)
    f, df_ = N.objetivo(d, P, capital)
    crit = CriterioParada(epsilon_f=tol, epsilon_x=1e-10, max_iteraciones=200, paso_derivada=1.0)

    with st.spinner("Iterando…"):
        r = N.ejecutar(metodo, f, df_, S, 25 * S, 13 * S, crit)

    estilo.cifras([
        ("✓" if r.convergio else "✗", "convergencia",
         "verde" if r.convergio else "rojo"),
        (f"{r.iteraciones}", "iteraciones"),
        (f"{r.evaluaciones_funcion}", "llamadas al motor", "naranja"),
        (sci_html(abs(r.raiz - objetivo_smlv * S)), "error final (pesos)"),
        (f"{N.ORDEN_NOMINAL[metodo]:g}".replace(".", ","), "orden nominal"),
    ])
    if r.convergio and r.estado:
        st.caption(f"Estado de salida: {r.estado}"
                   + (f" (cota de error {sci(r.cota_error)} pesos de mesada)." if r.cota_error else ".")
                   + (" Valor y derivada se calculan en una sola llamada por punto."
                      if metodo in N.CON_DERIVADA_CONJUNTA else "")
                   + (" Incluye la derivada inicial que prepara la relajación."
                      if metodo in ("Punto fijo relajado", "Aitken-Steffensen", "Steffensen escalado")
                      else ""))

    if not r.convergio and r.mensaje:
        st.warning(f"**No convergió.** {r.mensaje}")
        if metodo == "Steffensen":
            estilo.bloque(
                "Un fracaso instructivo",
                "Steffensen no es un mal método: está mal escalado. Su incremento auxiliar "
                "es <i>x<sub>k</sub></i>&nbsp;+&nbsp;<i>f</i>(<i>x<sub>k</sub></i>), pero <i>f</i> se mide en pesos de capital (~10⁸) y "
                "<i>x</i> en pesos de mesada (~10⁶). El incremento es cien veces mayor que "
                "la propia incógnita. Pruebe con «Steffensen escalado».", "critica")

    izq, der = st.columns([1.5, 1])
    with izq:
        h = r.historial[:14]
        xs_it = [it.x / S for it in h if np.isfinite(it.x) and 0 < it.x / S <= 25.0]
        lo = max(1.0, min([objetivo_smlv * 0.45] + xs_it))
        hi = min(25.0, max([objetivo_smlv * 2.6] + xs_it) * 1.03)
        dfc = N.curva_vp(d, P, clave, lo * S, hi * S, 200)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dfc.M / S, y=dfc.VP - capital,
                                 line=dict(color="#B9C0C6", width=3), name="f(M)",
                                 hoverinfo="skip"))
        fig.add_hline(y=0, line=dict(color="#444", width=1))
        fig.add_vline(x=objetivo_smlv, line=dict(color=N.ROJO, width=1, dash="dot"))
        fig.add_trace(go.Scatter(
            x=[it.x / S for it in h], y=[it.fx for it in h],
            mode="lines+markers+text",
            text=[f"x{k}" for k in range(len(h))], textposition="top right",
            textfont=dict(size=10),
            line=dict(color=N.COLOR_FAMILIA[N.FAMILIA[metodo]], width=1.2, dash="dash"),
            marker=dict(size=8), name="iterados",
            hovertemplate="%{text}<br>M = %{x:.4f} SMLV<extra></extra>"))
        fig.update_layout(**N.plantilla_plotly(), height=420,
                          xaxis_title="M / SMLV", yaxis_title="f(M)  [pesos]",
                          title=f"{metodo} — trayectoria de los iterados")
        estilo.grafica(fig)

    with der:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=[it.evaluaciones_acumuladas for it in r.historial],
            y=[max(abs(it.fx), 1e-14) for it in r.historial],
            mode="lines+markers",
            line=dict(color=N.COLOR_FAMILIA[N.FAMILIA[metodo]], width=2),
            marker=dict(size=7), name="|f|"))
        fig2.add_hline(y=tol, line=dict(color=N.GRIS, width=1, dash="dot"),
                       annotation_text="tolerancia", annotation_font_size=10)
        fig2.update_layout(**N.plantilla_plotly(), height=420, yaxis_type="log",
                           xaxis_title="llamadas al motor", yaxis_title="|f(x_k)|",
                           title="Decaimiento del residuo")
        estilo.grafica(fig2)

    with st.expander("Ver la sucesión completa"):
        estilo.tabla(pd.DataFrame([{
            "k": it.k, "x_k (SMLV)": round(it.x / S, 8), "x_k (pesos)": round(it.x, 4),
            "f(x_k)": it.fx, "llamadas al motor": it.evaluaciones_acumuladas,
            "subgradiente": it.derivada, "nota": it.nota,
        } for it in r.historial]))


# =====================================================================
# 6 · La carrera
# =====================================================================

elif seccion == SECCIONES[6]:
    st.markdown("# La carrera")
    estilo.lead("Todos los métodos, el mismo problema, el mismo criterio de parada. "
                "El costo se mide en <b>llamadas efectivas al motor</b> —valor, derivadas y "
                "preparación—, no en iteraciones: en este equipo cada llamada tarda unos "
                f"{dec(N.tiempo_por_llamada_ms(), 1)} ms, y el álgebra del método es "
                "despreciable a su lado.")

    c1, c2 = st.columns([1, 1])
    with c1:
        objetivo_smlv = st.slider("Raíz objetivo (múltiplos del SMLV)", 1.02, 12.0, 2.41, 0.01,
                                  key="carrera_obj")
    with c2:
        seleccion = st.multiselect(
            "Métodos en carrera", N.METODOS_DISPONIBLES,
            default=["Bisección", "Illinois", "Brent", "Secante",
                     "Newton (dif. finitas)", "Halley", "Newton semisuave",
                     "Punto fijo relajado"])

    d = N.poliza()
    clave = N._clave(d, P)
    capital = N.vp_en(d, P, clave, objetivo_smlv * S)
    f, df_ = N.objetivo(d, P, capital)
    crit = CriterioParada(epsilon_f=1.0, epsilon_x=1e-10, max_iteraciones=200, paso_derivada=1.0)

    filas, historiales = [], {}
    with st.spinner(f"Corriendo {len(seleccion)} métodos…"):
        for m in seleccion:
            try:
                r = N.ejecutar(m, f, df_, S, 25 * S, 13 * S, crit)
            except Exception as e:                      # pragma: no cover
                st.error(f"{m}: {e}")
                continue
            historiales[m] = r
            filas.append({
                "Método": m, "Familia": N.FAMILIA[m],
                "Converge": "sí" if r.convergio else "no",
                "Llamadas": r.evaluaciones_funcion,
                "Iteraciones": r.iteraciones,
                "Error (pesos)": abs(r.raiz - objetivo_smlv * S),
                "Orden nominal": N.ORDEN_NOMINAL[m],
            })

    if not filas:
        st.info("Elija al menos un método.")
    else:
        tab = pd.DataFrame(filas).sort_values("Llamadas")
        alto = max(320, 42 * len(tab))
        c1, c2 = st.columns([1.15, 1])
        with c1:
            fig = go.Figure(go.Bar(
                x=tab.Llamadas, y=tab.Método, orientation="h",
                marker_color=[N.COLOR_FAMILIA[f_] for f_ in tab.Familia],
                text=tab.Llamadas, textposition="outside",
                hovertemplate="%{y}<br>%{x} llamadas al motor<extra></extra>"))
            fig.update_layout(**N.plantilla_plotly(), height=alto,
                              xaxis_title="llamadas al motor",
                              yaxis=dict(autorange="reversed"),
                              title="Costo computacional")
            estilo.grafica(fig)
        with c2:
            fig2 = go.Figure()
            for i, (m, r) in enumerate(historiales.items()):
                fig2.add_trace(go.Scatter(
                    x=[it.evaluaciones_acumuladas for it in r.historial],
                    y=[max(abs(it.fx), 1e-13) for it in r.historial],
                    mode="lines+markers", name=m,
                    line=dict(width=1.8, color=N.PALETA[i % len(N.PALETA)]),
                    marker=dict(size=5)))
            fig2.add_hline(y=1.0, line=dict(color=N.GRIS, width=1, dash="dot"))
            plantilla = N.plantilla_plotly()
            plantilla["legend"] = {**plantilla["legend"], "font": dict(size=10)}
            fig2.update_layout(**plantilla, height=alto,
                               yaxis_type="log", xaxis_title="llamadas al motor",
                               yaxis_title="|f(x_k)|", title="Decaimiento del residuo")
            estilo.grafica(fig2)

        estilo.tabla(tab.style.format({"Error (pesos)": lambda v: sci(v, 2),
                                       "Orden nominal": lambda v: f"{v:g}".replace(".", ",")}))

        convergen = tab[tab.Converge == "sí"]
        if len(convergen) >= 2:
            ganador, peor = convergen.iloc[0], convergen.iloc[-1]
            texto = (f"En este escenario, <b>{ganador.Método}</b> resuelve con "
                     f"<b>{int(ganador.Llamadas)}</b> llamadas; <b>{peor.Método}</b> necesita "
                     f"<b>{int(peor.Llamadas)}</b>, un factor de "
                     f"<b>{dec(peor.Llamadas / max(ganador.Llamadas, 1), 1)}</b>. ")
            hal = convergen[convergen.Método == "Halley"]
            uno = convergen[convergen["Orden nominal"] <= 1.0]
            if len(hal) and len(uno) and (uno.Llamadas < hal.Llamadas.iloc[0]).any():
                mejor_uno = uno.sort_values("Llamadas").iloc[0]
                texto += ("El orden nominal no ordena la tabla: Halley, de orden 3, "
                          f"necesita {int(hal.Llamadas.iloc[0])} llamadas y queda por "
                          f"detrás de {mejor_uno.Método}, de orden 1, con "
                          f"{int(mejor_uno.Llamadas)}. El orden nominal alto no garantiza "
                          "menor costo.")
            else:
                texto += ("El orden nominal no es lo que ordena la tabla: lo que cuenta es cuántas "
                          "llamadas al motor exige cada iteración.")
            estilo.bloque("Lectura", texto, "aporte")

    with st.expander("Lo que predice la teoría genérica frente a lo que predice la estructura"):
        estilo.tabla(pd.DataFrame([
            ("Bisección", "lineal, razón 1/2", "sin cambio: la cota no usa suavidad"),
            ("Regula falsi", "lineal",
             "puede conservar un extremo; exacta si la cuerda queda en el tramo de la raíz"),
            ("Secante", "orden φ ≈ 1,618", "exacta con dos puntos en el tramo de la raíz"),
            ("Newton dif. finitas", "orden 2",
             "pendiente exacta si la ventana no cruza un quiebre; costo 3×"),
            ("Newton analítico", "orden 2", "un paso dentro del tramo de la raíz"),
            ("Steffensen", "orden 2", "falla por escala"),
            ("Müller", "orden 1,839", "degenera en secante"),
            ("Halley", "orden 3", "degenera en Newton con triple costo"),
            ("Punto fijo", "lineal", "casi óptimo por f′ constante"),
            ("Newton semisuave", "superlineal",
             "terminación local exacta; alcance según el teorema de terminación"),
        ], columns=["Método", "Teoría genérica", "Predicción estructural"]))

    st.markdown(f"## Resultados consolidados sobre los {C('NEscenarios', '25')} escenarios")
    st.markdown(f"{C('NSinteticos', '9')} escenarios sintéticos, {C('NReales', '9')} cotizaciones "
                f"de renta vitalicia y {C('NRealesRP', '7')} registros adicionales con información "
                "de retiro programado, valorados con la función de renta vitalicia. Tolerancias "
                f"ε<sub>f</sub> = {C('EpsilonProd', '1')} peso de capital y ε<sub>x</sub> = 10⁻⁸ "
                "pesos de mesada; encaje [S₀, 25S₀]; diferencias centradas con h = 1 peso.",
                unsafe_allow_html=True)
    tg = N.tabla_tesis("tabla_global")
    if tg is not None:
        col_exito = next((c for c in tg.columns if c.startswith("Éxito")), None)

        def _resaltar_fallos(fila):
            fallo = col_exito is not None and fila[col_exito].strip().startswith("0")
            return ["color: #D55E00; background-color: #FFF4EC" if fallo else ""] * len(fila)

        # Altura suficiente para ver las 19 filas sin barra de desplazamiento.
        estilo.tabla(tg.style.apply(_resaltar_fallos, axis=1),
                     height=(len(tg) + 1) * 35 + 3)
        st.caption("Tabla de resultados globales de la tesis (tex/tablas/tabla_global.tex), "
                   "ordenada por llamadas al motor. «Éxito»: cumplimiento del criterio "
                   "certificado; «Ev.»: llamadas al motor, incluidos valor, derivadas y "
                   "preparación; error: mediana de las diferencias absolutas de mesada respecto "
                   "de la referencia. El costo de una ejecución fallida no representa el de una "
                   "solución: por eso Steffensen, que encabeza la tabla con 0 % de éxito, va "
                   "resaltado.")
        tr = N.tabla_tesis("tabla_region")
        if tr is not None:
            st.markdown("#### Llamadas medias por región de la raíz (escenarios sintéticos)")
            estilo.tabla(tr, height=(len(tr) + 1) * 35 + 3)
            st.caption("Tabla de costo por región estructural de la tesis "
                       "(tex/tablas/tabla_region.tex).")
    else:
        res = N.tabla_resultados_guardada()
        if res is not None:
            res = res.sort_values("evaluaciones_medias")
            estilo.tabla(res[["metodo", "familia", "tasa_exito", "evaluaciones_medias",
                              "evaluaciones_max", "iteraciones_medias", "error_mediano"]]
                         .rename(columns={"metodo": "Método", "familia": "Familia",
                                          "tasa_exito": "Éxito", "evaluaciones_medias": "Ev. media",
                                          "evaluaciones_max": "Ev. máx.",
                                          "iteraciones_medias": "Iter.",
                                          "error_mediano": "Error mediano"})
                         .style.format({"Éxito": "{:.0%}", "Ev. media": "{:.2f}",
                                        "Iter.": "{:.2f}", "Error mediano": "{:.2e}"}))
            st.caption("No se encontró tex/tablas/tabla_global.tex; tabla leída de "
                       "salidas/resumen_global.csv, producida por correr_benchmark.py.")
        else:
            st.info("No se encontraron las tablas del banco de pruebas.")


# =====================================================================
# 7 · Terminación finita
# =====================================================================

elif seccion == SECCIONES[7]:
    st.markdown("# Terminación finita")
    estilo.lead(
        "Sobre una función afín a trozos, el paso de Newton con la pendiente exacta no se "
        "describe bien como convergencia cuadrática: cuando la clausura del tramo cuya "
        "pendiente se selecciona contiene la raíz, la obtiene <b>en aritmética exacta</b>. "
        "Con el arranque y la raíz dentro del tramo afín comercial, basta un paso.")

    estilo.bloque(
        "Teorema · Terminación en un tramo afín y cota bajo convexidad",
        "Sea <i>f</i> continua, lineal a trozos y estrictamente creciente en "
        "[&alpha;,&nbsp;&beta;], con raíz <i>x</i>*, y sea <i>V<sub>k</sub></i>&nbsp;&gt;&nbsp;0 la "
        "pendiente de un tramo cuya clausura contiene a <i>x<sub>k</sub></i>. "
        "(i) Si la clausura de ese tramo contiene también a <i>x</i>*, entonces "
        "<i>x</i><sub><i>k</i>+1</sub>&nbsp;=&nbsp;<i>x</i>* <b>exactamente</b>. "
        "(ii) Si además <i>f</i> es convexa y <i>x</i><sub>0</sub>&nbsp;&gt;&nbsp;<i>x</i>*, cada paso "
        "que no termina abandona el tramo hacia otro estrictamente a su izquierda, y el método "
        "termina en no más pasos que tramos cuyas clausuras intersectan [<i>x</i>*,&nbsp;<i>x</i><sub>0</sub>]. "
        "La cota de (ii) es una cota superior, no una igualdad.", "aporte")
    estilo.bloque(
        "Corolario · Un paso en el problema de cotización",
        "Si el punto inicial y la solución están ambos en el intervalo abierto "
        f"({dec(ANCHO, 3)}·SMLV,&nbsp;5·SMLV), Newton con la pendiente exacta de ese tramo "
        "alcanza M* en <b>una sola iteración</b> en aritmética exacta. Se requieren dos "
        "evaluaciones de <i>f</i>, para calcular y comprobar el paso; el costo de obtener la "
        "derivada se incluye en la contabilidad del motor (aquí, valor y derivada en una "
        "sola llamada por punto).", "aporte")
    estilo.bloque(
        "Teorema · Convergencia global y terminación finita (Newton salvaguardado)",
        "Sea <i>f</i> continua y estrictamente creciente en [<i>a</i><sub>0</sub>,&nbsp;"
        "<i>b</i><sub>0</sub>] con <i>f</i>(<i>a</i><sub>0</sub>)&nbsp;&lt;&nbsp;0&nbsp;&lt;&nbsp;"
        "<i>f</i>(<i>b</i><sub>0</sub>). El algoritmo con bisección periódica —a lo sumo dos "
        "propuestas de Newton consecutivas antes de imponer un punto medio— conserva el "
        "encaje y converge a la raíz, con "
        "<i>b<sub>k</sub></i>&minus;<i>a<sub>k</sub></i>&nbsp;&le;&nbsp;(<i>b</i><sub>0</sub>&minus;"
        "<i>a</i><sub>0</sub>)&middot;2<sup>&minus;&lfloor;<i>k</i>/3&rfloor;</sup>. Si además "
        "<i>f</i> es afín a trozos con finitos quiebres y el subgradiente es una pendiente "
        "lateral positiva cerca de M*, la iteración ideal alcanza la raíz en finitos pasos. "
        "Esa cota de trabajo no es la cota por iteración de la bisección pura.")

    d = N.poliza()
    clave = N._clave(d, P)
    objetivo_smlv = 2.4142135624
    capital = N.vp_en(d, P, clave, objetivo_smlv * S)
    f, df_ = N.objetivo(d, P, capital)
    crit = CriterioParada(epsilon_f=1e-6, epsilon_x=1e-12, max_iteraciones=100, paso_derivada=1.0)

    st.markdown("### Barrido del punto inicial")
    st.markdown("Se recorre todo el intervalo de búsqueda y se cuenta cuántas iteraciones "
                "necesita Newton semisuave desde cada arranque.")

    with st.spinner("Corriendo Newton semisuave desde 70 puntos iniciales…"):
        barrido = N.barrido_newton_semisuave(objetivo_smlv, 70)
    x0s, its = barrido.x0.to_numpy(), barrido.iteraciones.to_numpy()

    fig = go.Figure()
    for base, et in [(1.0, "racimo I"), (5.0, "racimo II"), (10.0, "racimo III")]:
        fig.add_vrect(x0=base, x1=base * ANCHO, fillcolor=N.NARANJA, opacity=.17, line_width=0,
                      annotation_text=et, annotation_font_size=10)
    fig.add_vline(x=objetivo_smlv, line=dict(color=N.ROJO, width=1.4, dash="dot"),
                  annotation_text="raíz", annotation_font_size=10)
    fig.add_trace(go.Scatter(x=x0s, y=its, mode="lines+markers",
                             line=dict(color=N.VERDE, width=2.2, shape="hv"),
                             marker=dict(size=5), name="iteraciones",
                             hovertemplate="x₀ = %{x:.2f} SMLV<br>"
                                           "%{y} iteraciones<extra></extra>"))
    fig.update_layout(**N.plantilla_plotly(), height=400,
                      xaxis_title="punto inicial x₀  [múltiplos del SMLV]",
                      yaxis_title="iteraciones hasta la raíz exacta",
                      yaxis=dict(dtick=1, range=[0, max(its) + 0.8]),
                      title="Newton semisuave: iteraciones según el punto de arranque")
    estilo.grafica(fig)

    estilo.bloque(
        "Lo que muestra la gráfica",
        "En este escenario, el número de iteraciones es una <b>función escalonada</b> del "
        "punto inicial, con los escalones en los racimos de quiebres. Arrancar en el tramo "
        "de la raíz cuesta <b>una</b> iteración: eso lo <b>garantiza</b> el corolario. Los "
        "arranques que cruzan racimos terminan aquí en <b>dos</b>: es un comportamiento "
        "<b>observado</b>, que no garantiza una o dos iteraciones desde todo arranque ni "
        "identifica los pasos con el número de tramos atravesados.", "aporte")

    st.markdown("### Verificación directa")
    tabla = []
    for x0 in [1.30, 2.00, 3.00, 4.50, 4.90, 6.00, 8.00, 13.00, 20.00, 24.00]:
        r = N.ejecutar("Newton semisuave", f, df_, S, 25 * S, x0 * S, crit)
        tabla.append({"x₀ / SMLV": x0,
                      "Tramo de x₀": ("mismo que M*" if x0 < 5.0 else
                                      "cruza racimo II" if x0 < 10.0 else "cruza racimos II–III"),
                      "Iteraciones": r.iteraciones,
                      "Llamadas al motor": r.evaluaciones_funcion,
                      "Error final (pesos)": abs(r.raiz - objetivo_smlv * S)})
    estilo.tabla(pd.DataFrame(tabla).style.format({"Error final (pesos)": lambda v: sci(v, 2),
                                                   "x₀ / SMLV": lambda v: dec(v, 2)}))
    estilo.nota("Un error residual de 9,3·10⁻¹⁰ pesos es del orden de unas pocas unidades en "
                "el último lugar (ulp) de la representación de doble precisión de un número del "
                "orden de 4·10⁶: la solución alcanza el límite de la aritmética disponible.")


# =====================================================================
# 8 · Laboratorio de sensibilidad
# =====================================================================

elif seccion == SECCIONES[8]:
    st.markdown("# Laboratorio de sensibilidad")
    estilo.lead(
        "Qué hipótesis domina el resultado puede <b>depender de la región estructural</b> en "
        "que caiga la solución: el piso pensional y el auxilio funerario solo intervienen en "
        "la pendiente cerca de sus racimos. Si una hipótesis deja el capital por debajo del "
        "mínimo financiable, no hay variación de mesada que reportar: se registra el estado "
        "de financiación.")

    c1, c2 = st.columns([1, 2.3])
    with c1:
        st.markdown("### Escenario")
        objetivo_smlv = st.slider("Mesada objetivo (múltiplos del SMLV)",
                                  1.01, 11.0, 2.41, 0.01, key="sens_obj")
        if objetivo_smlv < ANCHO:
            st.info("**Racimo I.** La raíz cae en la banda de quiebres del piso legal.")
        elif objetivo_smlv < 5.0:
            st.success("**Tramo afín.** Aquí caen las mesadas de la muestra real examinada.")
        elif objetivo_smlv < 5.0 * ANCHO:
            st.info("**Racimo II.** Banda del auxilio funerario (5 SMLV).")
        elif objetivo_smlv < 10.0:
            st.success("**Tramo afín intermedio.**")
        else:
            st.info("**Racimo III.** Saturación del auxilio funerario (10 SMLV).")

    d = N.poliza()
    clave = N._clave(d, P)
    capital = N.vp_en(d, P, clave, objetivo_smlv * S)

    def resolver(p2, d2):
        """Mesada que agota el capital bajo la hipótesis alterada, o None si el
        capital no alcanza el mínimo financiable con esa hipótesis."""
        f2, df2 = N.objetivo(d2, p2, capital)
        if f2(p2.smlv) > 0:          # KA < VP(SMLV): capital insuficiente
            return None
        r = N.ejecutar("Brent", f2, df2, p2.smlv, p2.smlv * 25, 13 * p2.smlv,
                       CriterioParada(1e-6, 1e-11, 300))
        return r.raiz if r.convergio else None

    base = resolver(P, d)
    variaciones = [
        ("Interés técnico real", "tasa", 0.0420, 0.0050),
        ("IPC primer año", "ipc_primer_anio", P.ipc_primer_anio, 0.0100),
        ("IPC de largo plazo", "ipc_objetivo_largo_plazo", P.ipc_objetivo_largo_plazo, 0.0050),
        ("Deslizamiento", "delta_deslizamiento", P.delta_deslizamiento, 0.0010),
        ("Recargo de gastos", "porcentaje_recargo_gastos_reserva",
         P.porcentaje_recargo_gastos_reserva, 0.0100),
        ("Reserva cambio de grupo", "porcentaje_reserva_cambio_grupo",
         P.porcentaje_reserva_cambio_grupo, 0.0020),
        ("Salario mínimo", "smlv", P.smlv, P.smlv * 0.05),
    ]

    def variacion(v):
        return None if v is None else (v - base) / base * 100

    with st.spinner("Resolviendo la cotización 14 veces (7 hipótesis, al alza y a la baja)…"):
        filas = []
        for et, campo, val, delta in variaciones:
            vals = []
            for signo in (-1, 1):
                if campo == "tasa":
                    vals.append(resolver(P, replace(d, tasa_interes_real=val + signo * delta)))
                else:
                    p2 = N.parametros(**{campo: val + signo * delta})
                    vals.append(resolver(p2, replace(d, smlv=p2.smlv)))
            filas.append((et, variacion(vals[0]), variacion(vals[1])))
        filas.sort(key=lambda r: max(abs(r[1] or 0), abs(r[2] or 0)))
    insuficientes = [(et, lado) for et, lo, hi in filas
                     for lado, v in (("a la baja", lo), ("al alza", hi)) if v is None]

    with c2:
        fig = go.Figure()
        fig.add_trace(go.Bar(y=[f[0] for f in filas], x=[f[1] or 0 for f in filas],
                             orientation="h", marker_color=N.ROJO, name="hipótesis a la baja",
                             hovertemplate="%{y}<br>%{x:+.2f} %<extra></extra>"))
        fig.add_trace(go.Bar(y=[f[0] for f in filas], x=[f[2] or 0 for f in filas],
                             orientation="h", marker_color=N.AZUL, name="hipótesis al alza",
                             hovertemplate="%{y}<br>%{x:+.2f} %<extra></extra>"))
        for et, lado in insuficientes:
            fig.add_annotation(y=et, x=0, text=f"capital insuficiente ({lado})",
                               showarrow=False, xanchor="left" if lado == "al alza" else "right",
                               font=dict(color=N.ROJO, size=11))
        fig.add_vline(x=0, line=dict(color="#444", width=1))
        fig.update_layout(**N.plantilla_plotly(), height=420, barmode="overlay",
                          xaxis_title="variación de la mesada resultante [%]",
                          title=f"Mesada base: {N.pesos(base)}")
        estilo.grafica(fig)

    dom = max(filas, key=lambda r: max(abs(r[1] or 0), abs(r[2] or 0)))
    smlv_efecto = [f for f in filas if f[0] == "Salario mínimo"][0]
    c1, c2 = st.columns(2)
    with c1:
        estilo.bloque("Hipótesis dominante en este escenario",
                      f"<b>{dom[0]}</b>, con {dec(max(abs(dom[1] or 0), abs(dom[2] or 0)))} % de "
                      "variación. Esa sensibilidad es específica del escenario y debe "
                      "distinguirse del error de resolución numérica: la elección de la tasa "
                      "requiere una justificación actuarial propia, independiente de la "
                      "rapidez del solucionador.")
    with c2:
        if insuficientes:
            lista = "; ".join(f"{et} ({lado})" for et, lado in insuficientes)
            estilo.bloque("Capital insuficiente, no una variación de mesada",
                          f"Con esta raíz, las hipótesis <b>{lista}</b> elevan el capital mínimo "
                          "VP(SMLV) por encima del capital disponible. No hay una mesada nueva "
                          "que comparar: se omite el porcentaje y se registra un caso de "
                          "<b>capital insuficiente</b>, la frontera de la sección 3 "
                          "(recomendación R1).", "critica")
        elif max(abs(smlv_efecto[1]), abs(smlv_efecto[2])) < 0.1:
            efecto_smlv = max(abs(smlv_efecto[1]), abs(smlv_efecto[2]))
            estilo.bloque("El salario mínimo pesa poco aquí",
                          "Con la raíz fuera de los racimos, el piso legal está inactivo en "
                          "todos los periodos. El salario mínimo entra solo por el auxilio "
                          "funerario, cuyo monto mínimo es de 5 SMLV y no depende de la mesada: "
                          f"un cambio del 5 % mueve la mesada un {dec(efecto_smlv)} %, pequeño "
                          f"pero no nulo. Baje la mesada objetivo por debajo de {dec(ANCHO)} SMLV "
                          "y véalo cambiar de naturaleza.", "aporte")
        else:
            signo = "+" if smlv_efecto[2] >= 0 else "−"
            estilo.bloque("El salario mínimo se activó",
                          "Con la raíz dentro de un racimo, un aumento del 5 % en el salario "
                          f"mínimo mueve la mesada un <b>{signo}{dec(abs(smlv_efecto[2]))} %</b>. "
                          "La misma variable que pesaba poco en el tramo afín pasa a ser "
                          "determinante.", "aporte")


# =====================================================================
# 9 · RV vs RP
# =====================================================================

elif seccion == SECCIONES[9]:
    st.markdown("# Renta vitalicia frente a retiro programado")
    estilo.lead(
        "En el retiro programado el pensionado conserva su cuenta individual y asume los "
        "riesgos de longevidad y de mercado. Matemáticamente, se pasa de <b>un</b> problema "
        "de raíz a <b>una sucesión acoplada</b> de problemas de raíz, con estado "
        "(<i>C<sub>n</sub></i>,&nbsp;<i>M</i><sub><i>n</i>&minus;1</sub>): el saldo y la mesada "
        "anterior, porque los ajustes dependen de ambos. Cada año se valora con una función "
        "de la misma familia de máximos y recortes —no la misma función: cambian edades, "
        "parámetros y recargos— y la mesada pagada resulta de aplicar los ajustes.")

    c1, c2 = st.columns([1, 1.25])
    with c1:
        st.latex(r"""\begin{cases}
        U_n \approx VP_n^{-1}(C_n)\\[2pt]
        M_n = \Psi_n\bigl(U_n,\,M_{n-1}\bigr)\\[2pt]
        C_{n+1} = \bigl(C_n-\kappa M_n\bigr)(1+g_n)
        \end{cases}""")
        st.caption("Ψₙ aplica el piso de crecimiento (n ≥ 2, cuando se activa la regla), el piso "
                   "del mínimo proyectado S₀⁽ⁿ⁾ = S₀Φᴿᴾₙ₋₁, el techo comercial (opcional, "
                   "desactivado por defecto) y el límite de caída; el año 1 arranca en la mesada "
                   "de renta vitalicia. La simulación se interrumpe si el saldo no es positivo o "
                   "si el solucionador declara que no convergió.")
    with c2:
        estilo.bloque(
            "Teorema · Propagación del error en el estado acoplado",
            "Compárense dos trayectorias con los <b>mismos</b> rendimientos, funciones de "
            "valoración y parámetros, con soluciones admisibles hasta el horizonte. Si las "
            "pendientes de <i>VP<sub>n</sub></i> están acotadas por debajo por "
            "<i>m<sub>n</sub></i>&nbsp;&gt;&nbsp;0, el ajuste es 1-Lipschitz en la mesada bruta y "
            "<i>L<sub>n</sub></i>-Lipschitz en la anterior, y el solucionador comete un error "
            "&epsilon;<sub>n</sub> en la mesada, entonces"
            "<div style='text-align:center;margin:.45rem 0'>|&eta;<sub>n</sub>| &le; "
            "|&delta;<sub>n</sub>|/<i>m<sub>n</sub></i> + <i>L<sub>n</sub></i>|&eta;<sub>n&minus;1</sub>| "
            "+ &epsilon;<sub>n</sub>,&emsp; &delta;<sub>n+1</sub> = (1+<i>g<sub>n</sub></i>)"
            "(&delta;<sub>n</sub> &minus; &kappa;&eta;<sub>n</sub>)</div>"
            "con &delta; el error del saldo y &eta; el de la mesada. Iterada, la cota es "
            "<i>E</i><sub>n+1</sub> &le; <i>A<sub>n</sub>E<sub>n</sub></i> + "
            "&kappa;&epsilon;<sub>n</sub>(<i>G<sub>n</sub></i>,&nbsp;1)<sup>T</sup>, con "
            "<i>A<sub>n</sub></i> de entradas no negativas. La regla condicional de crecimiento "
            "puede introducir un salto al cruzar su umbral: con activaciones distintas en las "
            "dos trayectorias hay que verificar la desigualdad exigida.", "aporte")

    st.markdown("### Tolerancia admisible según el horizonte")
    st.markdown("El corolario da la tolerancia anual que garantiza un error del saldo final "
                "no mayor que Δ: ε ≤ Δ / H_N, con H_N calculado a partir de las matrices "
                "Aₙ. Aquí se calcula con parámetros constantes.")
    c1, c2, c3 = st.columns(3)
    with c1:
        N_anios = st.slider("Horizonte N (años)", 5, 30, 20)
        g = st.slider("Rendimiento de la cuenta g (%)", -5.0, 12.0,
                      P.tasa_crecimiento_cai * 100, 0.5)
    with c2:
        m_pend = st.slider("Cota inferior de la pendiente mₙ", 50.0, 300.0, 245.0, 5.0,
                           help="Pesos de capital por peso de mesada. En la valoración de "
                                "referencia es ≈ 245; disminuye con la edad del grupo.")
        L_dep = st.slider("Dependencia de la mesada anterior Lₙ", 0.0, 1.10,
                          round(1 + P.ipc_objetivo_largo_plazo + P.deslizamiento_rp, 4), 0.0001,
                          format="%.4f",
                          help="Para los ajustes del motor, Lₙ = máx{rₙ, 1 − λ} con n ≥ 2, "
                               "donde rₙ = Φᴿᴾₙ₋₁/Φᴿᴾₙ₋₂ es el factor incremental del mínimo "
                               "proyectado; Lₙ = 1 − λ si la regla de crecimiento está "
                               "inactiva; L₁ = 0 en el arranque constante.")
    with c3:
        Delta = st.select_slider("Error tolerable del saldo final Δ",
                                 options=[0.01, 0.1, 1.0, 10.0, 100.0], value=1.0,
                                 format_func=lambda v: f"{v:g} peso" + ("" if v == 1 else "s"))
        kappa = 13
        st.caption(f"κ = {kappa} mesadas por año.")
    G = abs(1 + g / 100)
    a_n = kappa / m_pend
    A = np.array([[G * (1 + a_n), G * L_dep], [a_n, L_dep]])
    v = kappa * np.array([G, 1.0])
    H_x, Ak = 0.0, np.eye(2)
    for _ in range(N_anios):
        H_x += float((Ak @ v)[0])
        Ak = A @ Ak
    H_f = H_x / m_pend
    eps_x, eps_f = Delta / H_x, Delta / H_f
    estilo.cifras([
        (dec(H_x, 0), "H<sub>N</sub><sup>x</sup>"),
        (sci_html(eps_x, 2), "tolerancia de mesada ε<sub>x</sub><br>(pesos)", "naranja"),
        (sci_html(eps_f, 2), "tolerancia de residuo ε<sub>f</sub><br>(pesos de capital)",
         "verde" if eps_f >= P.epsilon else "rojo"),
    ])
    estilo.bloque(
        "Recomendación R4",
        f"Con estos parámetros, la tolerancia de producción de {dec(P.epsilon, 0)} peso de "
        + ("capital <b>basta</b>" if eps_f >= P.epsilon else "capital <b>no basta</b>")
        + f" para un error del saldo final de {Delta:g} peso{'' if Delta == 1 else 's'} a "
        f"{N_anios} años. No se deduce "
        "un factor universal de endurecimiento a partir del rendimiento medio y del número de "
        "años: la tolerancia depende del horizonte, de las pendientes y de cuánto dependen los "
        "ajustes de la mesada anterior. Por eso R4 consiste en calibrarla y verificarla para "
        "la configuración concreta de la proyección.", "critica")

    st.markdown("### Trayectorias comparadas sobre una póliza "
                + ("real" if N.BASE_ES_REAL else "de la base de ejemplo"))
    base7 = N.base_real()
    if base7 is None:
        st.info("No se encontró la base de pólizas (ni datos_privados/ ni py/cotizador/ejemplos/).")
    else:
        val = N.validacion_real()
        cpol, csem = st.columns([1, 1])
        with cpol:
            idx = st.selectbox("Póliza real" if N.BASE_ES_REAL else "Póliza (base ficticia)",
                               list(range(len(val))), index=0,
                               format_func=lambda i: f"{val.poliza.iloc[i]} · mesada RV "
                                                     f"{dec(val.mesada_smlv.iloc[i])} SMLV")
        with csem:
            semilla = int(st.number_input("Semilla del escenario de mercado", min_value=0,
                                          max_value=2**32 - 1, value=N.SEMILLA_RP, step=1,
                                          help="Fija los rendimientos sorteados de la cuenta. "
                                               "Cambiarla dibuja otra trayectoria de mercado. Sin "
                                               "semilla explícita, el motor deriva una estable "
                                               "de un resumen SHA-256 de las entradas."))
        with st.spinner("Proyectando renta vitalicia y retiro programado año a año…"):
            proy_rv, proy_rp, con_ni = N.trayectorias_rv_rp(int(idx), semilla)

        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.13,
                            specs=[[{}, {"secondary_y": True}]],
                            subplot_titles=("(a) Trayectoria de la mesada",
                                            "(b) Cuenta individual y rendimiento sorteado"))
        fig.add_trace(go.Scatter(x=proy_rv.Anio, y=proy_rv.Mesada_Pensional_proyectada,
                                 mode="lines+markers", line=dict(color=N.AZUL, width=2.2),
                                 marker=dict(size=5), name="Renta vitalicia",
                                 hovertemplate="%{x}<br>%{y:,.0f}<extra>RV</extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=proy_rp.Anio, y=proy_rp.Mesada_Pensional_proyectada,
                                 mode="lines+markers", line=dict(color=N.ROJO, width=2.2),
                                 marker=dict(size=5, symbol="square"), name="Retiro programado",
                                 hovertemplate="%{x}<br>%{y:,.0f}<extra>RP</extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(x=proy_rp.Anio, y=proy_rp.Mesada_sin_piso,
                                 mode="lines", line=dict(color=N.ROJO, width=1.2, dash="dot"),
                                 name="RP bruta (antes de ajustes)",
                                 hovertemplate="%{x}<br>%{y:,.0f}<extra>RP bruta</extra>"),
                      row=1, col=1)
        fig.add_trace(go.Bar(x=proy_rp.Anio, y=proy_rp.Tasa_crecimiento_CAI_este_anio * 100,
                             marker_color=N.NARANJA, opacity=.45, name="rendimiento sorteado [%]",
                             hovertemplate="%{x}<br>%{y:.2f} %<extra></extra>"),
                      row=1, col=2, secondary_y=True)
        fig.add_trace(go.Scatter(x=proy_rp.Anio, y=proy_rp.Saldo_CAI_inicio_anio / 1e6,
                                 mode="lines+markers", line=dict(color=N.VERDE, width=2.2),
                                 fill="tozeroy", fillcolor="rgba(0,158,115,.15)",
                                 marker=dict(size=5), name="saldo de la CAI",
                                 hovertemplate="%{x}<br>%{y:,.1f} millones<extra>CAI</extra>"),
                      row=1, col=2)
        fig.update_layout(**N.plantilla_plotly(), height=420)
        fig.update_layout(legend=dict(orientation="h", y=-0.2, x=0))
        fig.update_yaxes(title_text="mesada [pesos]", row=1, col=1)
        fig.update_yaxes(title_text="saldo [millones de pesos]", row=1, col=2, secondary_y=False)
        fig.update_yaxes(title_text="rendimiento [%]", row=1, col=2, secondary_y=True,
                         showgrid=False, tickmode="auto", nticks=6, tickformat=".0f")
        estilo.grafica(fig)

        n_tot = len(proy_rp)
        n_piso = int(proy_rp.Piso_aplicado.sum())
        n_caida = int(proy_rp.Caida_limitada.sum())
        # En el año 1 la bandera Techo_aplicado marca el arranque forzado en la
        # mesada de RV; el techo comercial propiamente dicho es de los años siguientes.
        n_techo = int(proy_rp.Techo_aplicado.iloc[1:].sum())
        rv_por_anio = dict(zip(proy_rv.Anio.astype(int), proy_rv.Mesada_Pensional_proyectada))
        n_rp_mayor = sum(1 for a, m in zip(proy_rp.Anio.astype(int), proy_rp.Mesada_Pensional_proyectada)
                         if a in rv_por_anio and m > rv_por_anio[a] * (1 + 1e-9))
        texto = (f"Año 1: la mesada de RP arranca, por regla de negocio, exactamente en la de RV. "
                 f"De los {n_tot} años proyectados, el piso de crecimiento se activó en "
                 f"<b>{n_piso}</b> y el límite a la caída en <b>{n_caida}</b>. ")
        if P.aplicar_condicion_rv_mayor:
            texto += f"El techo comercial (RV&nbsp;&gt;&nbsp;RP) se activó en <b>{n_techo}</b>. "
        else:
            texto += ("El techo comercial (RV&nbsp;&gt;&nbsp;RP) está <b>desactivado</b> en la "
                      "parametrización por defecto")
            texto += (f", y por eso RP supera a RV en <b>{n_rp_mayor}</b> de los {n_tot} años. "
                      if n_rp_mayor else ". ")
        if n_tot < len(proy_rv):
            texto += (f"La simulación se interrumpe en {int(proy_rp.Anio.iloc[-1])}; el punto "
                      "donde termina la serie indica la interrupción de la simulación, no la "
                      "extinción del derecho pensional. ")
        if con_ni:
            texto += "En esta póliza se activó además el <b>factor de ajuste NI</b> (sección 10). "
        estilo.bloque("Qué decide la trayectoria", texto +
                      "La línea punteada es la mesada bruta de retiro programado antes de los "
                      "ajustes: la distancia entre ambas es lo que imponen las reglas de la "
                      "implementación. Una trayectoria no establece una comparación general de "
                      "riesgos ni una superioridad económica entre modalidades: para eso harían "
                      "falta conjuntos de trayectorias.", "critica")

        st.markdown("### Experimento de propagación")
        st.markdown("Se perturba el capital inicial en δ pesos y se repite la proyección con los "
                    "**mismos** rendimientos sorteados.")
        with st.spinner("Repitiendo la proyección con cinco capitales perturbados…"):
            tray = N.propagacion_rp(int(idx), semilla)
        ref = tray[0.0]
        fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.1,
                            subplot_titles=("(a) Error en la mesada |M<sub>n</sub><sup>δ</sup> − M<sub>n</sub>|",
                                            "(b) Error en el saldo |C<sub>n</sub><sup>δ</sup> − C<sub>n</sub>|"))
        max_err_mesada = 0.0
        for i, dlt in enumerate([1.0, 1e2, 1e4, 1e6]):
            tr = tray[dlt]
            n = min(len(tr), len(ref))
            e_m = np.abs(tr.Mesada_Pensional_proyectada.to_numpy()[:n]
                         - ref.Mesada_Pensional_proyectada.to_numpy()[:n])
            e_c = np.abs(tr.Saldo_CAI_inicio_anio.to_numpy()[:n]
                         - ref.Saldo_CAI_inicio_anio.to_numpy()[:n])
            max_err_mesada = max(max_err_mesada, float(e_m.max()) if n else 0.0)
            etq = "δ = 10" + "⁰¹²³⁴⁵⁶⁷⁸⁹"[int(round(np.log10(dlt)))] + " pesos"
            fig.add_trace(go.Scatter(x=np.arange(1, n + 1), y=np.maximum(e_m, 1e-9),
                                     mode="lines+markers", name=etq, legendgroup=etq,
                                     line=dict(color=N.PALETA[i], width=1.8), marker=dict(size=5)),
                          row=1, col=1)
            fig.add_trace(go.Scatter(x=np.arange(1, n + 1), y=np.maximum(e_c, 1e-9),
                                     mode="lines+markers", name=etq, legendgroup=etq, showlegend=False,
                                     line=dict(color=N.PALETA[i], width=1.8), marker=dict(size=5)),
                          row=1, col=2)
        kk = np.arange(1, len(ref) + 1)
        fig.add_trace(go.Scatter(x=kk, y=1e4 * (1 + P.tasa_crecimiento_cai) ** kk,
                                 mode="lines", line=dict(color=N.GRIS, width=1.2, dash="dash"),
                                 name="referencia geométrica (1+ḡ)ⁿ·10⁴"), row=1, col=2)
        fig.update_layout(**N.plantilla_plotly(), height=400)
        fig.update_yaxes(type="log")
        fig.update_xaxes(title_text="año n")
        estilo.grafica(fig)

        estilo.nota("La línea discontinua es una referencia geométrica construida con el "
                    "rendimiento medio; no es una cota general cuando los rendimientos varían.")
        if max_err_mesada < 1e-3:
            estilo.bloque(
                "Un escenario de absorción",
                "La mesada no cambia, hasta el redondeo de máquina, con perturbaciones del capital "
                "de hasta un millón de pesos, mientras el saldo sí arrastra la perturbación. Lo "
                "explica el corolario de regímenes locales: el año 1 está fijado a la mesada de "
                "renta vitalicia, una referencia externa (régimen ii, &eta;<sub>1</sub>&nbsp;=&nbsp;0), "
                "y después actúa sobre todo el piso de crecimiento, que depende solo de la mesada "
                "anterior (régimen iii, &eta;<sub>n</sub>&nbsp;=&nbsp;<i>r<sub>n</sub></i>&eta;<sub>n&minus;1</sub>). "
                "La anulación de la derivada respecto de la mesada bruta no elimina por sí sola "
                "la perturbación transmitida por la historia: aquí es nula porque &eta;<sub>1</sub> "
                "lo es. El experimento <b>no acredita</b> que los recortes eliminen el error en "
                "cualquier trayectoria.", "critica")
        else:
            estilo.bloque(
                "La perturbación llega a la mesada",
                f"Con esta póliza y estos rendimientos, una perturbación de hasta un millón de "
                f"pesos en el capital mueve la mesada hasta <b>{N.pesos(max_err_mesada, 2)}</b>. "
                "Cuánto se amortigua o se amplifica depende del régimen activo cada año y de su "
                "dependencia de la mesada anterior.", "aporte")

    st.markdown("### Arranque en caliente")
    estilo.bloque(
        "Una mejora que la estructura sugiere",
        "La mesada del año anterior, en la misma base monetaria, puede usarse como punto "
        "inicial de la valoración siguiente. Si ese arranque y la nueva raíz están en el "
        "interior de un mismo tramo afín, el apartado (i) del teorema de terminación garantiza "
        "que una propuesta de Newton con la pendiente exacta alcanza la raíz; con salvaguarda, "
        "debe verificarse "
        "además que la propuesta se acepte. La proximidad de dos mesadas no demuestra por sí "
        "sola esa condición, porque también cambia la función de valoración: la ganancia "
        "requiere una medición específica y no se le asigna un factor universal.", "aporte")


# =====================================================================
# 10 · Las variables del modelo
# =====================================================================

elif seccion == SECCIONES[10]:
    st.markdown("# Las variables del modelo")
    estilo.lead(
        "Los capítulos anteriores tomaron el modelo actuarial como dado. Aquí se lo somete "
        "a examen. Para cada variable: <b>de dónde viene</b> (imposición normativa, convención "
        "actuarial, estimación o calibración <i>ad hoc</i>), <b>cuánto pesa</b> y si afecta la "
        "<b>estructura</b> de VP o solo su nivel. Tres componentes requieren revisión. La "
        "evaluación no acredita una calibración ni una validación actuarial independiente "
        "del cotizador.")

    efecto = N.efecto_demografico()
    ef = dict(zip(efecto.hipotesis, efecto.efecto_pct))
    sens = None
    if (N.RUTA_SALIDAS / "sensibilidad.csv").exists():
        sens = pd.read_csv(N.RUTA_SALIDAS / "sensibilidad.csv")
    tasa_txt = f"{C('SensTasaAlta')} %" if C("SensTasaAlta", "") else "alto"
    if tasa_txt == "alto" and sens is not None and (sens.variable == "Interés técnico real").any():
        fila_t = sens[sens.variable == "Interés técnico real"].iloc[0]
        tasa_txt = f"±{dec(max(abs(fila_t.baja_pct), abs(fila_t.alta_pct)), 1)} %"
    mejora_txt = (f"{C('EfectoMejora')} %".replace("-", "−") if C("EfectoMejora", "")
                  else f"{dec(ef['Sin factores de mejora de longevidad'], 1)} %".replace("-", "−"))

    veredictos = [
        ("Tablas de mortalidad", "fuentes por conciliar", "alto", "naranja", "trazabilidad pendiente"),
        ("Factores de mejora", "convención implementada", mejora_txt, "naranja",
         "años base por justificar"),
        ("Factor de aplicabilidad", "convención de la compañía", "medio", "naranja", "magnitud sin validar"),
        ("Independencia entre vidas", "hipótesis del modelo", "por cuantificar", "naranja",
         "simplificación demográfica"),
        ("Interés técnico real", "supuesto de valoración", tasa_txt, "naranja",
         "fuente y fecha por documentar"),
        ("IPC en tres tramos", "proyección macro", "medio", "naranja", "supuesto por contrastar"),
        ("Deslizamiento", "política salarial", "bajo", "verde", "determina los racimos"),
        ("SMLV", "Decreto 0159/2026", "alto o nulo", "verde", "monto decretado; transitorio"),
        ("Auxilio funerario", "Ley 100", "bajo", "verde", "exacta"),
        ("Recargos de gastos", "tarifa de la compañía", "medio", "naranja", "base por conciliar"),
        ("Sobrecosto de mortalidad RP", "tabla de la compañía", "medio", "naranja", "sin fuente documentada"),
        ("Beneficiario hipotético", "convención de RP", "alto", "naranja", "calibración pendiente"),
        ("Curva Smith-Wilson", "estándar EIOPA", "alto", "rojo", "configuración sin validar"),
        ("Volatilidad de la CAI", "estimación aproximada", "alto", "rojo", "sin serie histórica de apoyo"),
        ("Factor de ajuste NI", "calibración empírica", "alto", "rojo", "sin validación independiente"),
    ]
    filas_html = "".join(
        f'<tr class="{"debil" if c == "rojo" else ""}"><td>{v}</td><td>{fu}</td><td>{e}</td>'
        f'<td><span class="punto p-{c}"></span>{ve}</td></tr>'
        for v, fu, e, c, ve in veredictos)

    c1, c2 = st.columns([1.25, 1])
    with c1:
        st.markdown("### Veredicto sobre las quince variables")
        st.caption("Las marcadas en rojo requieren revisión y se discuten abajo.")
        st.markdown('<table class="veredicto"><thead><tr><th>Variable</th><th>Fundamento</th>'
                    '<th>Efecto</th><th>Veredicto</th></tr></thead><tbody>'
                    + filas_html + "</tbody></table>", unsafe_allow_html=True)
    with c2:
        st.markdown("### Peso de las hipótesis demográficas")
        fig = go.Figure(go.Bar(
            x=efecto.efecto_pct, y=efecto.hipotesis, orientation="h",
            marker_color=[N.ROJO if v < 0 else N.AZUL for v in efecto.efecto_pct],
            text=[f"{'+' if v >= 0 else '−'}{dec(abs(v), 1)} %" for v in efecto.efecto_pct],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>%{x:+.2f} %<extra></extra>"))
        fig.add_vline(x=0, line=dict(color="#444", width=1))
        fig.update_layout(**N.plantilla_plotly(), height=380,
                          xaxis_title="efecto sobre la reserva matemática [%]",
                          xaxis=dict(range=[efecto.efecto_pct.min() * 1.7,
                                            max(efecto.efecto_pct.max() * 1.8, 2)]))
        fig.update_layout(margin=dict(l=10, r=30, t=20, b=50))
        estilo.grafica(fig)
        estilo.nota(f"Sobre la póliza de referencia, suprimir la cónyuge cambia la reserva un "
                    f"−{dec(abs(ef['Sin cónyuge beneficiaria']), 1)} %, al retirar la cobertura "
                    "de sobrevivencia de esa beneficiaria y pasar de dos vidas a una. El régimen "
                    f"de 14 mesadas suma {dec(ef['Régimen de 14 mesadas'], 1)} %, cerca de 1/13. "
                    "La independencia entre vidas no se cuantifica aquí: si solo cambia CONAB, "
                    "cambian los pesos pero se conservan la forma afín a trozos y los umbrales.")
    estilo.bloque("Mortalidad: trazabilidad antes que verdicto",
                  "La Resolución 1555 de 2010 rige las tablas de rentistas válidos (RV-08) y la "
                  "0585 de 1994 las de inválidos; la denominación de las columnas no basta para "
                  "atribuir cada serie a su tabla. Las mejoras usan años base 2022 y 1985, "
                  "distintos del año que identifica la tabla RV08, cuyo origen debe documentarse. "
                  "Los factores de aplicabilidad (0,70 causante, 0,95 beneficiarios) son "
                  "defendibles en concepto, <b>no verificados en magnitud</b>: hay que comprobar "
                  "que no dupliquen un efecto de selección ya incorporado en la tabla.",
                  "critica")

    st.markdown("### ¿Mueve los quiebres o solo el nivel?")
    st.markdown("El tercer criterio de evaluación pregunta si una variable altera la "
                "**estructura** de VP o solo su nivel. Elija una hipótesis y compare la "
                "pendiente normalizada en el racimo del salario mínimo.")
    opciones = {
        "Interés técnico real: 4,20 % → 3,20 %": ("tasa", 0.032),
        f"Recargo de gastos: {dec(P.porcentaje_recargo_gastos_reserva * 100, 1)} % → 8,0 %":
            ("porcentaje_recargo_gastos_reserva", 0.08),
        f"Reserva por cambio de grupo: {dec(P.porcentaje_reserva_cambio_grupo * 100, 1)} % → 1,5 %":
            ("porcentaje_reserva_cambio_grupo", 0.015),
        f"IPC de largo plazo: {dec(P.ipc_objetivo_largo_plazo * 100)} % → 5,00 %":
            ("ipc_objetivo_largo_plazo", 0.05),
        f"Deslizamiento: {dec(P.delta_deslizamiento * 100)} % → 0,40 %":
            ("delta_deslizamiento", 0.004),
    }
    eleccion = st.radio("Hipótesis alterada", list(opciones), horizontal=True)
    campo, valor = opciones[eleccion]
    p_alt = N.parametros(**{campo: valor}) if campo != "tasa" else P
    ancho_alt = ancho_racimo(p_alt)
    hi = float(min(max(1.40, ancho_alt * 1.06), 2.2))
    with st.spinner("Evaluando la derivada exacta en 480 puntos…"):
        c_base = N.pendiente_normalizada("", 0.0, 0.98 * S, hi * S)
        c_alt = N.pendiente_normalizada(campo, valor, 0.98 * S, hi * S)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=c_base.M / S, y=c_base.pendiente_rel, name="hipótesis base",
                             line=dict(color=N.AZUL, width=2.4, shape="hv")))
    fig.add_trace(go.Scatter(x=c_alt.M / S, y=c_alt.pendiente_rel, name="hipótesis alterada",
                             line=dict(color=N.ROJO, width=1.8, dash="dash", shape="hv")))
    fig.add_vrect(x0=1.0, x1=ANCHO, fillcolor=N.NARANJA, opacity=.14, line_width=0,
                  annotation_text="racimo I (base)", annotation_font_size=10)
    if abs(ancho_alt - ANCHO) > 1e-4:
        fig.add_vrect(x0=1.0, x1=min(ancho_alt, hi), fillcolor="rgba(0,0,0,0)",
                      line=dict(color=N.ROJO, width=1, dash="dot"),
                      annotation_text="racimo I (alterado)", annotation_position="bottom right",
                      annotation_font_size=10)
    fig.update_layout(**N.plantilla_plotly(), height=360,
                      xaxis_title="M  [múltiplos del SMLV]",
                      yaxis_title="VP′₊(M) / VP′₊(3 SMLV)")
    estilo.grafica(fig)
    estilo.nota("Los últimos quiebres de cada racimo corresponden a periodos en que la "
                "probabilidad de que el grupo siga con derecho es casi nula: existen, pero su "
                "salto en la pendiente es imperceptible a esta escala.")
    if campo in ("delta_deslizamiento", "ipc_objetivo_largo_plazo"):
        estilo.bloque("Esta sí mueve la estructura",
                      f"El racimo pasa de terminar en {dec(ANCHO, 3)} a terminar en "
                      f"<b>{dec(ancho_alt, 3)}</b> salarios mínimos: los quiebres están en "
                      "<i>S</i><sub>0</sub>&rho;<sub>n</sub>, y &rho;<sub>n</sub> depende solo de la "
                      "inflación y del deslizamiento. Cambia el ancho del tramo afín y, con él, "
                      "dónde termina Newton en un paso.", "critica")
    else:
        estilo.bloque("Esta solo mueve el nivel",
                      "El racimo empieza y termina exactamente en el mismo sitio. La variable "
                      "entra en <i>VP</i> como peso <i>w<sub>t</sub></i>, <i>c<sub>t</sub></i> o como "
                      "escala global, independiente de <i>M</i>: conserva la representación "
                      "afín a trozos y los umbrales candidatos. La posición de la raíz y el "
                      "desempeño de los métodos sí pueden cambiar.", "aporte")

    st.markdown("### Tres componentes que requieren revisión")
    c1, c2, c3 = st.columns(3)
    with c1:
        estilo.bloque("Curva Smith-Wilson",
                      "Implementada pero <b>desactivada</b> en la configuración de referencia. "
                      "Se usa con <b>un solo punto observado</b> —el interés técnico del año 1—, "
                      f"una UFR del {C('UFR', '3,0')} % muy inferior a él y "
                      f"&alpha;&nbsp;=&nbsp;{C('AlphaSW', '0,10')} sin calibrar. Un único nodo no "
                      "identifica una estructura de mercado entre plazos, y la magnitud de la "
                      "reserva resultante no valida ni refuta por sí sola el método: hace falta "
                      "una calibración documentada y un contraste con curvas alternativas.",
                      "critica")
    with c2:
        estilo.bloque(f"Volatilidad de la CAI · {C('VolCAI', '6,0')} %",
                      "Una <b>estimación</b> con dos observaciones publicadas y la composición del "
                      "portafolio, no con la serie histórica de rentabilidad. Debe apoyarse en "
                      "una serie con frecuencia, ventana y base monetaria explícitas, y evaluar "
                      "la hipótesis normal. Una <i>t</i> escalada explora colas más pesadas, "
                      "pero sigue siendo simétrica; el remuestreo por bloques es otra "
                      "alternativa por contrastar.", "critica")
    with c3:
        estilo.bloque(f"Factor de ajuste NI · {C('FactorNI', '1,19')}",
                      "Cuatro observaciones con un rango del 7 % <b>no acreditan</b> estabilidad "
                      "ni generalización; no hay interpretación actuarial del factor; y hay "
                      "<b>circularidad</b>: se activa con una referencia de la base y la "
                      "calibración por póliza puede imponer la reproducción de esa misma "
                      "referencia, así que la concordancia no acredita desempeño predictivo. "
                      "Su uso como corrección transferible requiere identificar su origen "
                      "actuarial y separar los casos de calibración de los de evaluación.",
                      "critica")

    st.markdown("### Contraste con cotizaciones de referencia")
    lectura_comun = (
        "La causa <b>no está identificada</b> con la información disponible: deben "
        "conciliarse fechas, capitales, tablas, tasas, gastos y convenciones de pago, y la "
        "diferencia no se atribuye a un factor omitido sin evidencia adicional. El contraste "
        "evalúa concordancia de resultados, no valida por separado los parámetros, y su "
        "aceptación requiere fijar una tolerancia de materialidad.")

    def pct_signo(v: float) -> str:
        return f"+{dec(v)} %" if v >= 0 else f"−{dec(-v)} %"

    val = N.validacion_real() if N.BASE_ES_REAL else None
    if val is None:
        # Sin la base real no hay contraste que calcular: la base ficticia del
        # repositorio reproduce el modelo por construcción. Se citan las cifras
        # del documento (sección 6, figura del contraste).
        estilo.cifras([
            (f"+{C('ValidMedia', '1,36')} %", "discrepancia media", "naranja"),
            (f"{C('ValidMin', '0,51')} – {C('ValidMax', '2,88')} %", "rango"),
            (f"{C('MultMin', '1,43')} – {C('MultMax', '2,28')}",
             "mesadas de las muestras<br>reales, en SMLV", "verde"),
        ])
        estilo.bloque(
            "Lectura",
            "En las siete pólizas de referencia las mesadas calculadas son mayores que las "
            "reportadas por la compañía. " + lectura_comun
            + " Todas las mesadas caen dentro del tramo afín.")
        estilo.nota("Cifras del capítulo 6 del documento. Las cotizaciones reales contienen "
                    "datos personales y no se publican; la base ficticia del repositorio "
                    "reproduce el modelo por construcción, así que no sirve para este contraste. "
                    "Con las bases reales en <code>datos_privados/</code>, esta sección lo "
                    "recalcula póliza a póliza.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            lim = [val.aseguradora.min() / 1e6 * .96, val.aseguradora.max() / 1e6 * 1.04]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=lim, y=lim, mode="lines",
                                     line=dict(color=N.GRIS, dash="dash", width=1),
                                     name="igualdad", hoverinfo="skip"))
            orden = val.aseguradora.rank(method="first").astype(int)
            posiciones = ["top left" if k % 2 else "bottom right" for k in orden]
            fig.add_trace(go.Scatter(x=val.aseguradora / 1e6, y=val.modelo / 1e6,
                                     mode="markers+text", text=val.poliza,
                                     textposition=posiciones, marker=dict(color=N.AZUL, size=11),
                                     name="pólizas",
                                     hovertemplate="%{text}<br>compañía %{x:.3f} M<br>"
                                                   "modelo %{y:.3f} M<extra></extra>"))
            fig.update_layout(**N.plantilla_plotly(), height=360, showlegend=False,
                              xaxis_title="mesada reportada por la compañía [millones]",
                              yaxis_title="mesada del modelo [millones]",
                              title="(a) Modelo frente a referencia")
            estilo.grafica(fig)
        with c2:
            fig = go.Figure(go.Bar(
                x=val.poliza, y=val.dif_pct,
                marker_color=[N.VERDE if abs(v) < 3 else N.NARANJA for v in val.dif_pct],
                text=[pct_signo(v) for v in val.dif_pct],
                textposition="outside", cliponaxis=False,
                hovertemplate="%{x}<br>%{y:+.2f} %<extra></extra>"))
            fig.add_hline(y=0, line=dict(color="#444", width=1))
            fig.update_layout(**N.plantilla_plotly(), height=360,
                              yaxis_title="diferencia relativa [%]",
                              yaxis=dict(range=[min(0, val.dif_pct.min() * 1.3),
                                                max(0, val.dif_pct.max() * 1.25)]),
                              title="(b) Discrepancia póliza a póliza")
            estilo.grafica(fig)
        estilo.cifras([
            (pct_signo(val.dif_pct.mean()), "discrepancia media", "naranja"),
            (f"{dec(val.dif_pct.abs().min())} – {dec(val.dif_pct.abs().max())} %",
             "rango (en valor absoluto)"),
            (f"{dec(val.mesada_smlv.min())} – {dec(val.mesada_smlv.max())}",
             "mesadas, en SMLV", "verde"),
        ])
        n_pol = len(val)
        if (val.dif_pct > 0).all():
            signo = "las mesadas calculadas son mayores que las de referencia"
        elif (val.dif_pct < 0).all():
            signo = "las mesadas calculadas son menores que las de referencia"
        else:
            signo = "las diferencias cambian de signo entre pólizas"
        estilo.bloque(
            "Lectura",
            f"En estas {n_pol} pólizas {signo}. " + lectura_comun + " "
            + ("Todas las mesadas caen dentro del tramo afín."
               if val.mesada_smlv.min() > ANCHO and val.mesada_smlv.max() < 5.0 else ""))
        estilo.nota(f"Las pólizas se identifican como P1…P{n_pol}. La base original contiene "
                    "nombres y números de identificación, que la aplicación no muestra.")

    estilo.bloque(
        "Síntesis",
        "La revisión distingue datos normativos, hipótesis de valoración y convenciones del "
        "cotizador. La procedencia de las series de mortalidad, los años base de mejora y los "
        "ajustes de aplicabilidad requieren conciliación documental, y la volatilidad de la "
        "cuenta, la calibración de Smith-Wilson y el factor NI limitan la interpretación "
        "actuarial de las proyecciones. Para el análisis numérico, lo esencial es que las "
        "modificaciones que solo "
        "alteran pesos independientes de <i>M</i> <b>conservan la representación afín a "
        "trozos</b>; la posición de la raíz y el desempeño de los métodos sí pueden cambiar, y "
        "la conservación de la forma funcional <b>no sustituye</b> la validación de las bases "
        "actuariales.", "aporte")


# =====================================================================
# 11 · Del teorema a producción
# =====================================================================

elif seccion == SECCIONES[11]:
    st.markdown("# Del teorema a producción")
    estilo.lead(
        "El análisis detectó cuatro puntos de revisión del motor de valoración, cada uno "
        "apoyado en un resultado del documento. Se distingue la corrección en el banco de "
        "pruebas de su adopción en todos los flujos de producción: la verificación del "
        "catálogo no certifica todos los recorridos de la aplicación.")

    recs = [
        ("R1", "Distinguir insuficiencia de fallo numérico.",
         "KA &lt; VP(S<sub>0</sub>) identifica insuficiencia; el fracaso del método no la "
         "demuestra.", "naranja", "Comprobado en sensibilidad; integración general pendiente."),
        ("R2", "Corregir la derivada en M = S<sub>0</sub>.",
         "La rama altera la fórmula de la derivada aunque conserve el valor: 249,06 frente a "
         "7,23, un factor de 34.", "verde", "<b>Implementado en el motor.</b>"),
        ("R3", "Certificar el error y declarar sus unidades.",
         "|x &minus; M*| &le; |f(x)|/m requiere una cota inferior válida; el ancho del encaje "
         "ofrece otro certificado.", "naranja", "Criterio corregido en el banco."),
        ("R4", "Elegir la tolerancia anual de RP según horizonte.",
         "Corolario de tolerancia: intervienen el estado acoplado, los rendimientos y los "
         "errores locales.", "naranja", "Cota formulada; calibración operativa pendiente."),
        ("—", "Calcular conjuntamente valor y derivada.",
         f"Una llamada por punto; ahorro observado de {C('AhorroDerivada', '59')} % frente a "
         "diferencias finitas.", "verde", "<b>Implementado y contado en el banco.</b>"),
    ]
    st.markdown('<table class="veredicto"><thead><tr><th></th><th>Acción</th><th>Fundamento</th>'
                '<th>Estado</th></tr></thead><tbody>'
                + "".join(f'<tr><td><b>{c}</b></td><td>{h}</td><td>{fu}</td>'
                          f'<td><span class="punto p-{col}"></span>{e}</td></tr>'
                          for c, h, fu, col, e in recs)
                + "</tbody></table>", unsafe_allow_html=True)

    st.markdown("## R1 · El capital insuficiente, antes y después")
    st.markdown("Se corren los algoritmos **de producción** (`core/metodos_numericos.py`, con los "
                "parámetros por defecto del cotizador) sobre la póliza de referencia, con un capital "
                "expresado como fracción del capital mínimo.")
    frac = st.slider("Capital disponible, en múltiplos de KA_mín", 0.80, 1.20, 0.95, 0.01)
    with st.spinner("Corriendo la secante y la bisección de producción…"):
        pr = N.produccion_con_capital(frac)
    c1, c2, c3 = st.columns(3)
    with c1:
        if frac < 1.0:
            estilo.bloque("Prueba a priori · 1 evaluación",
                          f"VP(S<sub>0</sub>) = {N.millones(pr['ka_min'])} &gt; KA = "
                          f"{N.millones(pr['capital'])}.<br><b>«El capital no alcanza para "
                          "financiar la pensión mínima.»</b> Diagnóstico exacto, sin iterar.",
                          "aporte")
        elif abs(frac - 1.0) < 1e-9:
            estilo.bloque("Prueba a priori · 1 evaluación",
                          "KA = VP(S<sub>0</sub>): en el dominio admisible la única solución es "
                          "M = S<sub>0</sub>. La prueba lo reconoce sin iterar.", "aporte")
        else:
            estilo.bloque("Prueba a priori · 1 evaluación",
                          "KA &gt; VP(S<sub>0</sub>): el problema está bien planteado y tiene "
                          "solución única. Se procede a iterar.", "aporte")
    for col, nombre, clave_r in ((c2, "Secante de producción", "secante"),
                                 (c3, "Bisección de producción", "biseccion")):
        r = pr[clave_r]
        with col:
            if r["convergio"]:
                cuerpo = (f"Converge en <b>{r['evaluaciones']}</b> llamadas al motor a "
                          f"M = {dec(r['mesada_smlv'], 4)} SMLV.")
                tipo = "aporte" if frac >= 1.0 else "critica"
                if abs(frac - 1.0) < 1e-9:
                    cuerpo += " Es la solución admisible única."
            else:
                cuerpo = (f"Falla tras <b>{r['evaluaciones']}</b> llamadas al motor, terminando en "
                          f"M = {dec(r['mesada_smlv'], 2)} SMLV, con el mensaje:<br>"
                          f"<i>«{r['mensaje']}»</i>.<br>Nada en él dice que el capital es "
                          "insuficiente"
                          + (", y devolver el salario mínimo no certifica la igualdad actuarial."
                             if abs(r["mesada_smlv"] - 1.0) < 1e-6 else "."))
                tipo = "critica"
            estilo.bloque(nombre, cuerpo, tipo)

    st.markdown("## R3 · Las unidades de la tolerancia")
    d = N.poliza()
    clave = N._clave(d, P)
    with st.spinner("Evaluando la derivada exacta en 260 puntos…"):
        dr = N.curva_vp(d, P, clave, 1.0 * S, 1.6 * S, 260)
    c1, c2 = st.columns([1.6, 1])
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dr.M / S, y=1.0 / dr.dVP_der, line=dict(color=N.ROJO, width=2.2),
                                 name="1 / VP′₊(M)",
                                 hovertemplate="M = %{x:.4f} SMLV<br>%{y:.4f} pesos de mesada<extra></extra>"))
        fig.add_vrect(x0=1.0, x1=ANCHO, fillcolor=N.NARANJA, opacity=.14, line_width=0,
                      annotation_text="racimo I", annotation_font_size=10)
        fig.update_layout(**N.plantilla_plotly(), height=360,
                          xaxis_title="M  [múltiplos del SMLV]",
                          yaxis_title="error de mesada admitido [pesos]",
                          title="Qué significa «|f| < 1 peso» según la región")
        estilo.grafica(fig)
    with c2:
        d_bajo = float(dr.dVP_der.iloc[0])
        d_alto = float(dr.dVP_der.iloc[-1])
        estilo.cifras([(dec(1 / d_bajo, 3), "pesos de mesada<br>junto al SMLV", "rojo"),
                       (dec(1 / d_alto, 4), "pesos de mesada<br>en el tramo afín", "verde"),
                       (f"{dec(d_alto / d_bajo, 0)}×", "diferencia de exigencia", "naranja")])
        estilo.bloque("R3 · Recomendación",
                      "El criterio |<i>f</i>| &lt; 1 peso se mide en pesos de capital, pero la "
                      "incógnita es una mesada. Si las pendientes entre <i>x</i> y M* están "
                      "acotadas por debajo por <i>m</i>, entonces |<i>x</i>&nbsp;&minus;&nbsp;M*| "
                      "&le; |<i>f</i>(<i>x</i>)|/<i>m</i>, y basta exigir |<i>f</i>| &le; <i>m</i>&epsilon; "
                      "para una tolerancia &epsilon; de mesada. En un mismo tramo afín <i>m</i> = <i>VP</i>′; "
                      "si se atraviesan quiebres, la derivada en un punto no sustituye a esa cota: "
                      "hay que certificar la conversión con una cota válida o con el encaje. En "
                      "el banco de pruebas, cada método certifica por residuo o por el semiancho "
                      "del encaje; un paso pequeño solo se usa como diagnóstico de estancamiento.",
                      "critica")

    st.markdown("## R4 · Tolerancia del retiro programado")
    estilo.bloque("Recomendación",
                  "En la recursión de retiro programado el error de cada año se arrastra al saldo y "
                  "a la mesada siguiente. El corolario de tolerancia da la condición suficiente "
                  "&epsilon;&nbsp;&le;&nbsp;&Delta;/<i>H<sub>N</sub></i>, con <i>H<sub>N</sub></i> calculado "
                  "a partir de las pendientes, los rendimientos y la dependencia de los ajustes "
                  "respecto de la mesada anterior. No hay un factor universal de endurecimiento: "
                  "la sección 9 permite calcularlo para una configuración dada.", "critica")

    st.markdown("## Recomendación de método")
    apendice = N.tabla_tesis("tabla_apendice")

    def ev_conjunto(conjunto: str, metodo: str) -> str:
        if apendice is None:
            return "—"
        fila = apendice[(apendice.iloc[:, 0] == conjunto) & (apendice.iloc[:, 1] == metodo)]
        return fila.iloc[0, 3] if len(fila) else "—"

    c1, c2 = st.columns(2)
    with c1:
        estilo.bloque(
            "Para el modelo estudiado, con derivada analítica",
            "<b>Newton semisuave con salvaguarda periódica</b>: combina la reducción "
            "cuantitativa del encaje con la terminación local afín a trozos. En la batería "
            f"completa emplea <b>{C('EvNSG')}</b> llamadas medias, frente a {C('EvBis')} de "
            f"bisección, {C('EvSec')} de secante y {C('EvBre')} de Brent. La comparación con "
            "Brent depende de la región: en las cotizaciones reales, situadas en el tramo afín, "
            f"requiere {ev_conjunto('Pólizas RV', 'Newton salvaguardado')} y "
            f"{ev_conjunto('Registros adicionales', 'Newton salvaguardado')} llamadas en los dos "
            f"conjuntos, frente a {ev_conjunto('Pólizas RV', 'Brent')} de Brent —las dos "
            "llamadas adicionales respecto de Newton semisuave son la evaluación de los "
            "extremos del encaje—; en los sintéticos, que sitúan raíces en los racimos, "
            f"{ev_conjunto('Sintéticos', 'Newton salvaguardado')} frente a "
            f"{ev_conjunto('Sintéticos', 'Brent')}.", "aporte")
    with c2:
        estilo.bloque(
            "Por qué, si no es siempre el más barato",
            "La preferencia no descansa en un menor costo en todos los casos. Se apoya en que "
            "aprovecha la pendiente exacta para obtener la raíz por inversión del tramo que la "
            "contiene, en que su paso tiene lectura actuarial directa —exceso de capital sobre "
            "el costo de un peso de mesada— y en la cota global del teorema del salvaguardado. "
            "Sin derivadas, <b>Brent</b> ofrece una alternativa con encaje y costo similar. La "
            "<b>secante</b>, configurada por defecto en el motor, es competitiva en costo, pero "
            "su versión abierta carece de garantía global. La elección operativa requiere "
            "verificar dominio, bases actuariales y certificados de salida.")


# =====================================================================
# 12 · Conclusiones y trabajo futuro
# =====================================================================

elif seccion == SECCIONES[12]:
    st.markdown("# Conclusiones")

    estilo.bloque(
        "Respuesta a la pregunta de investigación",
        "En el modelo estudiado, la valoración es <b>afín a trozos</b>, con umbrales candidatos "
        "organizados en tres racimos geométricos para la parametrización considerada. La "
        "extensión a <i>M</i>&nbsp;&ge;&nbsp;0 es constante en [0,&nbsp;SMLV], mientras que en el "
        "dominio admisible <i>M</i>&nbsp;&ge;&nbsp;SMLV hay una raíz única si y solo si "
        "KA&nbsp;&ge;&nbsp;VP(SMLV). El auxilio funerario puede destruir la convexidad. Las "
        "mesadas de la muestra de renta vitalicia examinada se sitúan en un intervalo afín; esa "
        "observación no describe la cartera completa de la compañía ni el mercado colombiano.",
        "aporte")
    estilo.bloque(
        "Qué se sigue para los métodos",
        "La derivada lateral exacta permite aprovechar los tramos sin aproximar pendientes por "
        "valoraciones auxiliares. Un paso de Newton obtiene la raíz cuando la clausura del tramo "
        "seleccionado contiene también la solución; eso no garantiza una o dos iteraciones desde "
        "todo arranque ni identifica los pasos con el número de tramos atravesados. Para el "
        "problema interior con un encaje inicial válido, la variante semisuave con "
        "<b>bisección periódica</b> aporta una garantía global explícita, por lo que constituye "
        f"una recomendación fundada para el cotizador estudiado ({C('EvNSG')} llamadas medias "
        f"frente a {C('EvBis')} de la bisección). La recomendación no establece una "
        "superioridad universal.")

    st.markdown("### Verificación de las hipótesis de trabajo")
    hipotesis = [
        ("H1 · Caracterización analítica",
         "La representación afín a trozos y el conjunto de hasta "
         f"{C('NQuiebresMax', '333')} umbrales candidatos se obtienen de las operaciones de máximo "
         "y recorte. Un umbral candidato puede no producir un salto efectivo si su peso es nulo."),
        ("H2 · Terminación bajo condiciones precisas",
         "La inversión exacta de un tramo da la terminación en un paso si este contiene la raíz "
         "en su clausura. La cota por número de tramos requiere las condiciones adicionales del "
         "teorema; no es una igualdad general."),
        ("H3 · Contabilidad de costo",
         "Las iteraciones no representan el mismo trabajo en todos los métodos. La comparación "
         "contabiliza preparación, valoraciones auxiliares y llamadas efectivas al motor, y las "
         "complementa con tiempo de ejecución."),
        ("H4 · Derivada analítica conjunta",
         "Reutilizar los vectores de valoración evita las llamadas auxiliares de las diferencias "
         "finitas. El ahorro efectivo se evalúa con el oráculo conjunto de valor y derivadas; no "
         "se deduce un porcentaje fijo del número nominal de evaluaciones."),
    ]
    cols = st.columns(4)
    for col, (tit, cuerpo) in zip(cols, hipotesis):
        with col:
            estilo.bloque(tit, cuerpo, "aporte")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Aportes teóricos y de modelación")
        st.markdown("""
1. Región plana de la extensión y condición de capital mínimo en el dominio
   admisible.
2. Umbrales candidatos en tres racimos y condiciones de pérdida de convexidad.
3. Expresión del $B$-subdiferencial, interpretación marginal, semisuavidad y
   $BD$-regularidad interior.
4. Condiciones de terminación de Newton y garantía de encaje para la variante
   salvaguardada.
5. Sesgo de las diferencias finitas en quiebres y cota condicional del error en
   el estado de retiro programado.
""")
    with c2:
        st.markdown("### Aportes metodológicos y computacionales")
        st.markdown(f"""
6. Implementación de {C('NMetodos', '19')} métodos con interfaz común, contabilidad de
   llamadas completas al motor y memoria por ejecución.
7. Evaluación conjunta de reserva y derivadas laterales en el motor.
8. Protocolo con raíces de referencia y escenarios que incluyen quiebres,
   regiones afines y capital insuficiente.
9. Hallazgos y recomendaciones sobre la implementación (R1–R4).
10. Esta aplicación interactiva, que no sustituye una nota técnica ni la
    validación de un producto comercial.
""")

    st.markdown("### Limitaciones")
    limitaciones = [
        ("Alcance del modelo",
         "Se analiza una implementación particular, no una representación exhaustiva de las "
         "obligaciones regulatorias ni de la tarificación comercial. Reserva, capital y prima "
         "requieren conciliación sobre fecha, componentes y base de valoración comunes."),
        ("Representatividad",
         "Las muestras proceden de una sola compañía y no permiten inferir propiedades de su "
         "cartera completa o del mercado. Los escenarios sintéticos amplían la cobertura "
         "numérica, sin aportar representatividad estadística."),
        ("Bases actuariales",
         "La procedencia de las series de mortalidad, los años base de mejora y los factores de "
         "aplicabilidad requieren documentación adicional; la dependencia entre vidas no se "
         "cuantifica."),
        ("Calibración y retiro programado",
         "La volatilidad, los recargos de mortalidad y el beneficiario hipotético no cuentan con "
         "calibración acreditada, y el factor NI puede reproducir la referencia con que se "
         "calibró. Las trayectorias son ilustrativas."),
        ("Condiciones de la cota",
         "La propagación supone trayectorias con las mismas funciones de valoración, parámetros "
         "y rendimientos, y soluciones admisibles en un horizonte común. El cierre de una "
         "simulación no determina la extinción jurídica del derecho pensional."),
        ("Garantías y medición",
         "La terminación exacta se formula en aritmética exacta; el programa se detiene con "
         "tolerancias y redondeo. Los tiempos dependen del entorno, y la reproducción exige "
         "conservar versiones, entradas y configuración."),
    ]
    cols = st.columns(3)
    for i, (tit, cuerpo) in enumerate(limitaciones):
        with cols[i % 3]:
            estilo.bloque(tit, cuerpo, "critica")

    st.markdown("### Trabajo futuro")
    futuro = [
        ("Conciliación actuarial",
         "Documentar fuentes, transformaciones, fechas y componentes de valoración; explicar las "
         "discrepancias antes de introducir multiplicadores y separar datos de calibración y de "
         "evaluación."),
        ("Curvas de descuento",
         "Calibrar Smith-Wilson con observaciones y convenciones monetarias coherentes, contrastar "
         "alternativas y examinar su efecto en las reservas. Más nodos no acreditan por sí solos "
         "la idoneidad de la curva."),
        ("Dependencia y experiencia",
         "Estimar conjuntamente las bases de mortalidad y su posible dependencia. Si la "
         "dependencia solo modifica pesos independientes de M, su efecto puede estudiarse sin "
         "perder la representación afín a trozos."),
        ("Proyección y comparación de modalidades",
         "Justificar la dinámica financiera y los ajustes, usar trayectorias comunes para "
         "comparar sensibilidades y definir criterios de riesgo y suficiencia antes de concluir "
         "sobre modalidades pensionales."),
        ("Arranque en caliente",
         "Medir su utilidad y establecer condiciones para que la mesada anterior, en la base "
         "monetaria pertinente, permanezca en un tramo que contenga la nueva raíz. La cercanía "
         "entre años no garantiza esa condición."),
        ("Extensiones del problema",
         "Estudiar la inversión respecto de la tasa y las bases de mortalidad estocásticas. La "
         "forma afín a trozos en la mesada no se traslada automáticamente a otras incógnitas."),
    ]
    cols = st.columns(3)
    for i, (tit, cuerpo) in enumerate(futuro):
        with cols[i % 3]:
            estilo.bloque(tit, cuerpo)

    st.markdown("### Reflexión final")
    estilo.lead(
        "Una función cercana a una recta puede requerir atención en sus quiebres y en el piso. "
        "Reconocer esa estructura permite resolver el caso habitual con pocas operaciones y, a "
        "la vez, identificar los casos donde faltan capital, hipótesis de convergencia o "
        "evidencia actuarial.")
    estilo.bloque(
        "El valor del análisis",
        "Delimitar esas condiciones y documentar la precisión obtenida, sin confundir exactitud "
        "numérica con validez del modelo.")

    st.markdown('<div class="portada" style="border-bottom:none;text-align:center;'
                'padding:2rem 0 1rem 0;margin-top:2rem">'
                '<h1 style="font-size:2.4rem !important">Gracias</h1>'
                '<div class="sub">Preguntas del jurado</div></div>', unsafe_allow_html=True)


# =====================================================================
# Pie de navegación
# =====================================================================

st.markdown(f'<div class="pie-nav">{seccion}</div>', unsafe_allow_html=True)
c_ant, _, c_sig = st.columns([1, 3, 1])
with c_ant:
    if INDICE > 0:
        st.button(f"← {SECCIONES[INDICE - 1]}", on_click=_ir_a, args=(INDICE - 1,),
                  key="nav_anterior")
with c_sig:
    if INDICE < len(SECCIONES) - 1:
        st.button(f"{SECCIONES[INDICE + 1]} →", on_click=_ir_a, args=(INDICE + 1,),
                  key="nav_siguiente")
