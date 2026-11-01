# -*- coding: utf-8 -*-
"""Estilo grafico unificado de las figuras de la tesis."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Paleta segura para daltonismo (Okabe-Ito) mas dos neutros
AZUL      = "#0072B2"
NARANJA   = "#E69F00"
VERDE     = "#009E73"
ROJO      = "#D55E00"
MORADO    = "#CC79A7"
CELESTE   = "#56B4E9"
AMARILLO  = "#F0E442"
GRIS      = "#4D4D4D"
GRIS_CLARO= "#BFBFBF"

PALETA = [AZUL, NARANJA, VERDE, ROJO, MORADO, CELESTE, GRIS, AMARILLO]

# Nombres de los metodos tal como se escriben en el documento. En el codigo
# se conservan sin tildes porque son claves de diccionarios y de los CSV.
NOMBRE_VISIBLE = {
    "Biseccion": "Bisección", "Regula Falsi": "Regula falsi",
    "Anderson-Bjorck": "Anderson–Björck", "Muller": "Müller",
    "Newton (derivada analitica)": "Newton (analítico)",
    "Aitken-Steffensen": "Aitken–Steffensen",
}


def nombre(metodo):
    """Nombre del metodo para rotulos y leyendas."""
    return NOMBRE_VISIBLE.get(metodo, metodo)

def aplicar_estilo():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 9.5,
        "axes.titlesize": 10.5,
        "axes.labelsize": 9.5,
        "legend.fontsize": 8.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#E0E0E0",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "figure.dpi": 130,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "lines.linewidth": 1.6,
        "legend.frameon": False,
        "axes.prop_cycle": plt.cycler(color=PALETA),
    })

def fmt_millones(x, pos=None):
    if abs(x) >= 1e9: return f"{x/1e9:.1f}B"
    if abs(x) >= 1e6: return f"{x/1e6:.1f}M"
    if abs(x) >= 1e3: return f"{x/1e3:.0f}k"
    return f"{x:.0f}"

FMT_M = FuncFormatter(fmt_millones)

def guardar(fig, nombre, carpeta=None):
    from rutas import FIGURAS
    ruta = f"{carpeta or FIGURAS}/{nombre}"
    fig.savefig(ruta + ".pdf")
    plt.close(fig)
    print("  ->", nombre + ".pdf")
