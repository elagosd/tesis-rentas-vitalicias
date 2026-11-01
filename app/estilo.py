# -*- coding: utf-8 -*-
"""Hoja de estilo de la presentación y envoltorios de compatibilidad."""

import inspect

import streamlit as st


# ---------------------------------------------------------------------
# Ancho completo para gráficas y tablas, compatible entre versiones.
# Streamlit retiró `use_container_width` en favor de `width="stretch"`;
# las versiones anteriores a ese cambio no aceptan la cadena "stretch".
# Se elige la forma correcta según la firma de la versión instalada.
# ---------------------------------------------------------------------

def _kw_ancho(funcion):
    try:
        par = inspect.signature(funcion).parameters
    except (TypeError, ValueError):          # pragma: no cover
        return {"use_container_width": True}
    if "width" in par and isinstance(par["width"].default, str):
        return {"width": "stretch"}
    return {"use_container_width": True}


_ANCHO_GRAFICA = _kw_ancho(st.plotly_chart)
_ANCHO_TABLA = _kw_ancho(st.dataframe)


def grafica(fig, **kw):
    """Muestra una figura de Plotly a todo el ancho, con convenciones
    numéricas colombianas: coma decimal, punto de miles y sin sufijos
    SI (Plotly escribe «6B» para 6·10⁹, que en español se lee «billones»).
    Los ejes logarítmicos conservan la notación de potencias."""
    fig.update_layout(separators=",.")
    fig.for_each_xaxis(lambda ax: ax.update(
        exponentformat="power" if ax.type == "log" else "none"))
    fig.for_each_yaxis(lambda ax: ax.update(
        exponentformat="power" if ax.type == "log" else "none"))
    st.plotly_chart(fig, **_ANCHO_GRAFICA, **kw)


def tabla(datos, **kw):
    kw.setdefault("hide_index", True)
    st.dataframe(datos, **_ANCHO_TABLA, **kw)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,300;0,400;0,600;0,700;1,400&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --azul:#0072B2; --naranja:#E69F00; --verde:#009E73; --rojo:#D55E00;
  --morado:#CC79A7; --tinta:#161A1D; --gris:#5A6570; --linea:#E3E6E9;
  --papel:#FCFCFD;
}

html, body, [class*="css"] { font-family:'Inter',sans-serif; }
.stApp { background: var(--papel); }
.block-container { padding-top: 2.2rem; max-width: 1180px; }

h1,h2,h3 { font-family:'Crimson Pro',Georgia,serif !important; color:var(--tinta) !important;
           letter-spacing:-.01em; }
h1 { font-weight:700 !important; font-size:2.5rem !important; line-height:1.12; }
h2 { font-weight:600 !important; font-size:1.7rem !important; margin-top:1.6rem !important; }
h3 { font-weight:600 !important; font-size:1.22rem !important; }

/* ---------- Portada ---------- */
.portada {
  border-top:3px solid var(--azul); border-bottom:1px solid var(--linea);
  padding:2.6rem 0 2.2rem 0; margin-bottom:1.6rem;
}
.portada .kicker { font-size:.76rem; letter-spacing:.16em; text-transform:uppercase;
  color:var(--azul); font-weight:600; margin-bottom:1.1rem; }
.portada h1 { font-size:3.1rem !important; margin:0 0 .5rem 0 !important; }
.portada .sub { font-family:'Crimson Pro',serif; font-size:1.35rem; color:var(--gris);
  font-style:italic; margin-bottom:1.6rem; }
.portada .autor { font-size:.95rem; color:var(--tinta); font-weight:500; }

/* ---------- Tarjetas de cifra ---------- */
.rejilla { display:flex; gap:.85rem; flex-wrap:wrap; margin:1.1rem 0; }
.cifra { flex:1 1 165px; background:#fff; border:1px solid var(--linea);
  border-left:3px solid var(--azul); border-radius:3px; padding:.85rem 1rem; }
.cifra .v { font-family:'Crimson Pro',serif; font-size:2.0rem; font-weight:700;
  color:var(--tinta); line-height:1.05; }
.cifra .e { font-size:.73rem; text-transform:uppercase; letter-spacing:.09em;
  color:var(--gris); margin-top:.3rem; }
.cifra.naranja { border-left-color:var(--naranja); }
.cifra.verde   { border-left-color:var(--verde); }
.cifra.rojo    { border-left-color:var(--rojo); }

/* ---------- Bloques de resultado ---------- */
.teorema {
  background:#fff; border:1px solid var(--linea); border-left:3px solid var(--azul);
  border-radius:3px; padding:1.05rem 1.25rem; margin:1.1rem 0;
  font-family:'Crimson Pro',Georgia,serif; font-size:1.06rem; line-height:1.55;
}
.teorema .tit { font-family:'Inter',sans-serif; font-size:.72rem; font-weight:600;
  letter-spacing:.13em; text-transform:uppercase; color:var(--azul);
  margin-bottom:.5rem; display:block; }
.teorema.critica { border-left-color:var(--rojo); background:#FEFAF8; }
.teorema.critica .tit { color:var(--rojo); }
.teorema.aporte { border-left-color:var(--verde); background:#F7FCFA; }
.teorema.aporte .tit { color:var(--verde); }

.lead { font-family:'Crimson Pro',Georgia,serif; font-size:1.22rem; line-height:1.6;
  color:#2A3238; margin-bottom:1.1rem; }

.nota { font-size:.86rem; color:var(--gris); font-style:italic;
  border-left:2px solid var(--linea); padding-left:.8rem; margin:.8rem 0; }

/* ---------- Navegación lateral ---------- */
section[data-testid="stSidebar"] { background:#F4F6F8; border-right:1px solid var(--linea); }
section[data-testid="stSidebar"] h2 { font-size:1.0rem !important; margin-top:.6rem !important; }
.marca { font-family:'Crimson Pro',serif; font-size:1.02rem; font-weight:700;
  color:var(--tinta); line-height:1.25; padding:.3rem 0 .7rem 0;
  border-bottom:1px solid var(--linea); margin-bottom:.7rem; }
.marca span { display:block; font-family:'Inter',sans-serif; font-size:.68rem;
  font-weight:500; letter-spacing:.11em; text-transform:uppercase;
  color:var(--azul); margin-bottom:.25rem; }

/* ---------- Varios ---------- */
code, .mono { font-family:'JetBrains Mono',monospace !important; font-size:.86em; }
.stDataFrame { border:1px solid var(--linea); border-radius:3px; }
hr { border-color:var(--linea); }
.stTabs [data-baseweb="tab"] { font-family:'Inter',sans-serif; font-size:.92rem; }
div[data-testid="stMetricValue"] { font-family:'Crimson Pro',serif; font-weight:700; }
.stButton>button { border-radius:3px; font-weight:500; }

/* ---------- Pie de navegación ---------- */
.pie-nav { border-top:1px solid var(--linea); margin-top:2.2rem; padding-top:.4rem;
  font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; color:var(--gris);
  text-align:center; }

/* ---------- Tabla de veredictos ---------- */
.veredicto { width:100%; border-collapse:collapse; font-size:.9rem; margin:.6rem 0 1rem 0; }
.veredicto th { text-align:left; font-size:.7rem; letter-spacing:.1em; text-transform:uppercase;
  color:var(--gris); border-bottom:1px solid var(--tinta); padding:.4rem .5rem; }
.veredicto td { border-bottom:1px solid var(--linea); padding:.42rem .5rem; vertical-align:top; }
.veredicto .punto { display:inline-block; width:.62rem; height:.62rem; border-radius:50%;
  margin-right:.45rem; vertical-align:baseline; }
.veredicto .p-verde { background:var(--verde); }
.veredicto .p-naranja { background:var(--naranja); }
.veredicto .p-rojo { background:var(--rojo); }
.veredicto tr.debil td { background:#FEFAF8; }
.veredicto td:last-child { white-space:nowrap; }
</style>
"""


def aplicar():
    st.markdown(CSS, unsafe_allow_html=True)


def cifras(items):
    """items: lista de (valor, etiqueta, clase)."""
    html = '<div class="rejilla">'
    for v, e, *c in items:
        cls = c[0] if c else ""
        html += f'<div class="cifra {cls}"><div class="v">{v}</div><div class="e">{e}</div></div>'
    return st.markdown(html + "</div>", unsafe_allow_html=True)


def bloque(titulo, cuerpo, tipo=""):
    st.markdown(
        f'<div class="teorema {tipo}"><span class="tit">{titulo}</span>{cuerpo}</div>',
        unsafe_allow_html=True)


def lead(texto):
    st.markdown(f'<div class="lead">{texto}</div>', unsafe_allow_html=True)


def nota(texto):
    st.markdown(f'<div class="nota">{texto}</div>', unsafe_allow_html=True)
