# -*- coding: utf-8 -*-
"""Figuras de convergencia y comparacion de metodos."""
import rutas
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from estilo_figuras import *
from core.problema_tesis import escenarios_estandar, constructor_objetivo
from core.banco_pruebas import ejecutar_catalogo
from core.metodos_iterativos import CriterioParada, ORDEN_TEORICO
from core import config

aplicar_estilo()
p = config.ParametrosActuariales(); S=p.smlv
SAL = rutas.SAL
esc = {e.codigo:e for e in escenarios_estandar(p)}

crit = CriterioParada(epsilon_f=1e-6, epsilon_x=1e-10, max_iteraciones=200, paso_derivada=1.0)

# =============== Fig 4: residuo vs evaluaciones ===============
def panel_residuos(ax, codigo, metodos, titulo):
    e = esc[codigo]
    res = ejecutar_catalogo(e, p, crit)
    for i,m in enumerate(metodos):
        r = res[m]
        ev = [it.evaluaciones_acumuladas for it in r.historial]
        rr = [max(abs(it.fx),1e-12) for it in r.historial]
        ax.semilogy(ev, rr, marker="o", ms=3.2, color=PALETA[i%len(PALETA)], label=nombre(m))
    ax.axhline(1.0, color=GRIS, ls=":", lw=.9)
    ax.set_title(titulo, fontsize=9)
    ax.set_xlabel("llamadas al motor"); ax.set_ylabel(r"$|f(x_k)|$  [pesos]")

METODOS = ["Biseccion","Regula Falsi","Illinois","Brent","Secante",
           "Newton (dif. finitas)","Newton (derivada analitica)","Punto fijo relajado"]
fig, ax = plt.subplots(1,2, figsize=(7.0,3.1))
panel_residuos(ax[0],"A-R3",METODOS,"(a) Raíz en el tramo afín (2.41 SMLV)")
panel_residuos(ax[1],"A-R2",METODOS,"(b) Raíz en el racimo de quiebres (1.04 SMLV)")
ax[1].legend(loc="upper right", ncol=1, fontsize=6.6, bbox_to_anchor=(1.02,1.05))
ax[0].text(2,1.6,"tolerancia de producción, $\\varepsilon_f=1$",fontsize=6.5,color=GRIS)
fig.suptitle("Decaimiento del residuo frente al costo real de cómputo", fontsize=10, y=1.03)
guardar(fig,"fig_convergencia_residuos")

# =============== Fig 5: construccion geometrica en la zona no suave ===============
# Se usa el escenario cuya raiz cae en el racimo de quiebres del SMLV: es la
# UNICA region donde la estructura lineal a trozos es visible a simple
# vista. En el tramo afin comercial las tres construcciones coincidirian
# con la propia grafica de f y la figura no mostraria nada.
e = esc["A-R2"]
f,dfd,_ = constructor_objetivo(e.datos, e.capital, p)
raiz = e.mesada_teorica
LO, HI = 0.97, 1.34
xx = np.linspace(LO*S, HI*S, 420); ff = np.array([f(x) for x in xx])

fig, ax = plt.subplots(1,3, figsize=(7.0,2.8), sharey=True)
def marco(a, tit):
    a.plot(xx/S, ff, color=GRIS, lw=1.6, zorder=4)
    a.axhline(0, color="black", lw=.7, zorder=5)
    a.axvline(raiz/S, color=ROJO, ls=":", lw=1.0, zorder=5)
    a.set_title(tit, fontsize=8.0); a.set_xlabel("$M$ / SMLV", fontsize=8)
    a.tick_params(labelsize=7); a.set_xlim(LO, HI)

a = ax[0]; marco(a, "(a) Bisección\nel encaje se parte a la mitad")
aa, bb = S, 25*S; fa = f(aa)
alt = np.linspace(ff.max()*.92, ff.max()*.18, 8)
for k in range(8):
    m=.5*(aa+bb); fm=f(m)
    a.plot([max(aa,LO*S)/S, min(bb,HI*S)/S],[alt[k]]*2,color=AZUL,lw=2.6,
           solid_capstyle="butt",alpha=.85,zorder=3)
    if fa*fm<0: bb=m
    else: aa,fa=m,fm
a.text(1.15, ff.max()*1.02, "8 encajes sucesivos", fontsize=6.6, color=AZUL, ha="center")

a = ax[1]; marco(a, "(b) Secante\nrecta por los dos últimos puntos")
x0,x1 = 25*S, S
for k in range(4):
    f0,f1=f(x0),f(x1)
    if f1==f0: break
    x2 = x1 - f1*(x1-x0)/(f1-f0); pend=(f1-f0)/(x1-x0)
    t=np.array([LO*S,HI*S])
    a.plot(t/S, f1+pend*(t-x1), color=NARANJA, lw=.9, ls="--", zorder=3, alpha=.9)
    if LO*S<=x1<=HI*S:
        a.plot([x1/S],[f1],marker="o",ms=4,color=NARANJA,zorder=6)
        a.annotate(f"$x_{{{k+1}}}$",(x1/S,f1),textcoords="offset points",xytext=(4,5),fontsize=6.6,color=NARANJA)
    x0,x1=x1,x2

a = ax[2]; marco(a, "(c) Newton semisuave\ntangente sobre un subgradiente")
x = 13*S
for k in range(4):
    fx=f(x); d=dfd(x)
    if d==0: break
    xn = x - fx/d
    t=np.array([LO*S,HI*S])
    a.plot(t/S, fx+d*(t-x), color=VERDE, lw=1.0, ls="--", zorder=3, alpha=.9)
    if LO*S<=x<=HI*S:
        a.plot([x/S],[fx],marker="o",ms=4,color=VERDE,zorder=6)
        a.annotate(f"$x_{{{k}}}$",(x/S,fx),textcoords="offset points",xytext=(4,5),fontsize=6.6,color=VERDE)
    x=xn
if LO*S<=x<=HI*S: a.plot([x/S],[f(x)],marker="*",ms=10,color=VERDE,zorder=7)

ax[0].set_ylabel("$f(M)$",fontsize=8.5); ax[0].yaxis.set_major_formatter(FMT_M)
ax[0].set_ylim(ff.min()*1.35, ff.max()*1.14)
fig.suptitle("Construcción geométrica de los métodos en el racimo de quiebres", fontsize=10, y=1.08)
guardar(fig,"fig_trayectorias")

# =============== Fig 5b: la no linealidad, amplificada ===============
# f parece una recta perfecta a escala natural. Restandole la cuerda que une
# sus extremos, la estructura lineal a trozos aparece amplificada ~1e5 veces.
e3 = esc["A-R3"]
f3,_,_ = constructor_objetivo(e3.datos, e3.capital, p)
xg = np.linspace(S, 15*S, 900); fg = np.array([f3(x) for x in xg])
cuerda = fg[0] + (fg[-1]-fg[0])*(xg-xg[0])/(xg[-1]-xg[0])
fig, ax = plt.subplots(1,2, figsize=(7.0,2.8))
ax[0].plot(xg/S, fg, color=AZUL)
ax[0].axhline(0,color=GRIS,lw=.7)
ax[0].set_title("(a) $f$ a escala natural:\nindistinguible de una recta", fontsize=8.5)
ax[0].set_xlabel("$M$ / SMLV",fontsize=8); ax[0].set_ylabel("$f(M)$",fontsize=8.5)
ax[0].yaxis.set_major_formatter(FMT_M); ax[0].tick_params(labelsize=7)
ax[1].plot(xg/S, fg-cuerda, color=ROJO)
ax[1].axhline(0,color=GRIS,lw=.7)
for x0,x1 in [(1.0,1.30),(5.0,5.75),(10.0,11.15)]:
    ax[1].axvspan(x0,x1,color=NARANJA,alpha=.20,lw=0)
ax[1].set_title("(b) $f$ menos su cuerda:\naparece la estructura lineal a trozos", fontsize=8.5)
ax[1].set_xlabel("$M$ / SMLV",fontsize=8)
ax[1].set_ylabel("$f(M)-\\ell(M)$",fontsize=8.5)
ax[1].yaxis.set_major_formatter(FMT_M); ax[1].tick_params(labelsize=7)
amp = np.abs(fg-cuerda).max()/np.abs(fg).max()
ax[1].text(.5,.06, f"amplitud relativa $\\approx {amp:.1e}$",
           transform=ax[1].transAxes, ha="center", fontsize=7, color=GRIS)
fig.suptitle("Por qué el problema es benigno: la no linealidad existe, pero es diminuta",
             fontsize=10, y=1.06)
guardar(fig,"fig_residuo_lineal")

# =============== Fig 6-8: desde las tablas del benchmark ===============
res_g = pd.read_csv(f'{SAL}/resumen_global.csv')
res_g = res_g[res_g.tasa_exito>0].sort_values("evaluaciones_medias")
colores = {"encaje":AZUL,"abierto":NARANJA,"no suave":VERDE}

fig, ax = plt.subplots(figsize=(6.4,3.7))
y=np.arange(len(res_g))
ax.barh(y, res_g.evaluaciones_medias, color=[colores[f] for f in res_g.familia], height=.68)
ax.errorbar(res_g.evaluaciones_medias, y,
            xerr=[np.zeros(len(res_g)), res_g.evaluaciones_max-res_g.evaluaciones_medias],
            fmt="none", ecolor=GRIS, elinewidth=.8, capsize=2)
ax.set_yticks(y); ax.set_yticklabels([nombre(m) for m in res_g.metodo], fontsize=7.6); ax.invert_yaxis()
ax.set_xlabel("llamadas al motor (media y máximo observado)")
ax.set_title("Costo computacional por método, 25 escenarios de valoración")
for fam,c in colores.items():
    ax.barh([np.nan],[np.nan],color=c,label=f"familia: {fam}")
ax.legend(loc="center right", fontsize=7.5)
ax.grid(axis="y", alpha=0)
guardar(fig,"fig_barras_evaluaciones")

# Solo los metodos con orden nominal fijo y con suficientes errores utiles
# para la regresion. La pendiente describe la trayectoria observada; no
# certifica un orden asintotico, sobre todo cuando hay terminacion en pocos pasos.
sub = res_g.dropna(subset=["orden_empirico", "orden_teorico"])
sub = sub.sort_values(["orden_teorico", "orden_empirico"])
fig, ax = plt.subplots(figsize=(5.6,3.8))
y = np.arange(len(sub))
ax.hlines(y, np.minimum(sub.orden_teorico, sub.orden_empirico),
          np.maximum(sub.orden_teorico, sub.orden_empirico), color=GRIS_CLARO, lw=1.2)
ax.scatter(sub.orden_teorico, y, marker="|", s=90, color=GRIS, zorder=3, label="orden nominal")
ax.scatter(sub.orden_empirico, y, c=[colores[f] for f in sub.familia], s=26, zorder=4,
           label="regresión de los errores")
ax.set_yticks(y); ax.set_yticklabels([nombre(m) for m in sub.metodo], fontsize=7.4)
ax.set_xlim(0, 3.2)
ax.set_xlabel("exponente nominal / pendiente de regresión")
ax.set_title("Orden nominal y descripción de las trayectorias\n"
             "la regresión no certifica un orden asintótico", fontsize=9)
ax.grid(axis="y", alpha=0)
ax.legend(fontsize=7.2, loc="lower right")
guardar(fig,"fig_orden_empirico")

# Fig 8: costo frente a la tolerancia exigida
from core.banco_pruebas import ejecutar_catalogo as EC
tols = [1e2,1e1,1e0,1e-1,1e-2,1e-3,1e-4,1e-5,1e-6]
sel = ["Biseccion","Brent","Secante","Newton (dif. finitas)","Newton (derivada analitica)",
       "Newton salvaguardado","Illinois"]
curvas = {m:[] for m in sel}
for t in tols:
    c = CriterioParada(epsilon_f=t, epsilon_x=1e-12, max_iteraciones=300, paso_derivada=1.0)
    r = EC(esc["A-R3"], p, c)
    for m in sel: curvas[m].append(r[m].evaluaciones_funcion)
fig, ax = plt.subplots(figsize=(5.6,3.2))
for i,m in enumerate(sel):
    ax.plot(-np.log10(tols), curvas[m], marker="o", ms=3.5, color=PALETA[i], label=nombre(m))
ax.set_xlabel(r"dígitos de precisión exigidos, $-\log_{10}\varepsilon_f$")
ax.set_ylabel("llamadas al motor")
ax.set_title("Costo frente a la precisión exigida")
ax.legend(fontsize=7.2, ncol=2)
guardar(fig,"fig_costo_tolerancia")
