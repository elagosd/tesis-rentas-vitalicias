# -*- coding: utf-8 -*-
"""Figuras 1-3: estructura funcional de VP."""
import rutas
import numpy as np, matplotlib.pyplot as plt
from dataclasses import replace
from datetime import date
from estilo_figuras import *
from core.motor import DatosPoliza, Persona, calcular_reserva
from core import config

aplicar_estilo()
p = config.ParametrosActuariales(); S = p.smlv
D = DatosPoliza('F',13,date(2026,7,31),S,S,0.042,
    Persona(date(1961,5,10),1,1,1),[Persona(date(1965,3,2),4,2,1)])

def vp(M):  return calcular_reserva(replace(D,mesada_actual=float(M)),p).reserva_matematica
def dvp(M):
    r=calcular_reserva(replace(D,mesada_actual=float(M)),p,calcular_derivada=True)
    return r.derivada_rm_der

# ---------- Figura 1: VP y su derivada ----------
xs = np.concatenate([np.linspace(0.05,1.0,40), np.linspace(1.0,1.30,120),
                     np.linspace(1.30,4.9,60), np.linspace(4.9,5.8,120),
                     np.linspace(5.8,9.8,60), np.linspace(9.8,11.3,140),
                     np.linspace(11.3,15,40)])
xs = np.unique(xs)
V  = np.array([vp(S*x) for x in xs])
Dv = np.array([dvp(S*x) for x in xs])

fig, ax = plt.subplots(2,1, figsize=(6.5,5.6), sharex=True,
                       gridspec_kw={"height_ratios":[1.2,1]})
bandas = [(1.0,1.30),(5.0,5.75),(10.0,11.15)]
for a in ax:
    a.axvspan(0.0,1.0, color=GRIS_CLARO, alpha=.40, lw=0)
    for x0,x1 in bandas:
        a.axvspan(x0,x1, color=NARANJA, alpha=.20, lw=0)

ax[0].plot(xs, V, color=AZUL)
ax[0].set_ylabel(r"$VP(M)$   [pesos]"); ax[0].yaxis.set_major_formatter(FMT_M)
ax[0].set_title("Estructura de la función de valoración actuarial")
ax[0].set_ylim(0, V.max()*1.16)
ax[0].annotate("región plana:  $VP$ constante,  $VP'\\equiv 0$",
               xy=(0.55, V[0]), xytext=(2.3, V.max()*0.30),
               arrowprops=dict(arrowstyle="->", color=GRIS, lw=.9,
                               connectionstyle="arc3,rad=-0.2"),
               fontsize=8.2, color=GRIS)
ax[0].annotate(f"$KA_{{\\min}}=VP(\\mathrm{{SMLV}})\\approx{V[0]/1e6:,.0f}$ millones",
               xy=(1.0, V[0]), xytext=(5.4, V.max()*0.10),
               arrowprops=dict(arrowstyle="->", color=GRIS, lw=.9),
               fontsize=8.2, color=GRIS)

ax[1].plot(xs, Dv, color=ROJO)
ax[1].set_ylabel(r"$VP'_+(M)$")
ax[1].set_xlabel(r"mesada inicial $M$   [múltiplos del SMLV]")
ax[1].set_ylim(-14, 300)
ax[1].set_yticks([0,50,100,150,200,250])
for x0,x1,et in [(1.0,1.30,"I"),(5.0,5.75,"II"),(10.0,11.15,"III")]:
    ax[1].text(0.5*(x0+x1), 268, et, ha="center", fontsize=8, color=ROJO, weight="bold")
ax[1].text(0.5, 120, "$VP'=0$", ha="center", fontsize=8, color=GRIS)

# Recuadro interior: la variacion fina de la pendiente, invisible a escala
# completa, es la que revela la PERDIDA DE CONVEXIDAD en el racimo III.
inset = ax[1].inset_axes([0.30, 0.14, 0.66, 0.44])
mask = xs > 1.35
inset.plot(xs[mask], Dv[mask], color=ROJO, lw=1.2)
for x0,x1 in bandas[1:]:
    inset.axvspan(x0,x1,color=NARANJA,alpha=.20,lw=0)
inset.set_ylim(245.05, 245.62); inset.set_xlim(1.35, 15)
inset.tick_params(labelsize=6.5); inset.grid(alpha=.5)
inset.set_title("detalle: la pendiente BAJA en III (no hay convexidad)",
                fontsize=6.6, pad=2)
guardar(fig,"fig_estructura_vp")

# ---------- Figura 2: zoom a los tres racimos ----------
fig, ax = plt.subplots(1,3, figsize=(6.9,2.5)); fig.subplots_adjust(wspace=.42)
rangos = [(0.98,1.32,"I. Piso del salario mínimo"),
          (4.96,5.85,"II. Auxilio funerario (5 SMLV)"),
          (9.95,11.25,"III. Auxilio funerario (10 SMLV)")]
for a,(x0,x1,tit) in zip(ax,rangos):
    xx=np.linspace(x0,x1,360); dd=np.array([dvp(S*x) for x in xx])
    a.plot(xx,dd,color=ROJO,lw=1.3)
    a.set_title(tit,fontsize=8.0,pad=4); a.set_xlabel("$M$ / SMLV",fontsize=8)
    a.tick_params(labelsize=7)
ax[0].set_ylabel(r"$VP'_+(M)$",fontsize=8.5)
ax[2].text(10.62,245.34,"la pendiente\ndecrece",ha="center",fontsize=6.8,color=GRIS)
fig.suptitle("Los tres racimos de puntos de quiebre de $VP$", fontsize=10, y=1.10)
guardar(fig,"fig_zoom_quiebres")

# ---------- Figura 3: buen planteamiento del problema ----------
KAmin = vp(S)
fig, ax = plt.subplots(figsize=(6.2,3.3))
xx = np.linspace(0.3, 3.2, 320); Vx = np.array([vp(S*x) for x in xx])
for KA, col, et, ls in [(KAmin*0.85, ROJO, r"$KA<KA_{\min}$: sin solución", "--"),
                        (KAmin,       NARANJA, r"$KA=KA_{\min}$: única admisible, $M=S_0$", "-."),
                        (KAmin*1.55,  VERDE, r"$KA>KA_{\min}$: solución única", "-")]:
    ax.plot(xx, Vx-KA, color=col, ls=ls, label=et)
ax.axhline(0,color=GRIS,lw=.8)
ax.axvspan(0.3,1.0,color=GRIS_CLARO,alpha=.35,lw=0)
ax.text(0.63,(Vx[0]-KAmin*1.55)*0.55,"región plana",ha="center",fontsize=7.5,color=GRIS)
ax.set_xlabel(r"mesada inicial $M$  [múltiplos del SMLV]")
ax.set_ylabel(r"$f(M)=VP(M)-KA$")
ax.yaxis.set_major_formatter(FMT_M)
ax.set_title("Buen planteamiento del problema según el capital disponible")
ax.legend(loc="upper left")
guardar(fig,"fig_region_plana")
