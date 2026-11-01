# -*- coding: utf-8 -*-
"""Figuras del capitulo de bases tecnicas: mortalidad, supervivencia, descuento, flujos."""
import rutas
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from dataclasses import replace
from datetime import date
from estilo_figuras import *
from core.mortalidad import cargar_tabla_mortalidad, generar_tabla_mortalidad_mensualizada, datos_auxiliar
from core.motor import DatosPoliza, Persona, calcular_reserva, _generar_calendario, _tasas_forward_mensuales
from core.smith_wilson import curva_smith_wilson
from core import config

aplicar_estilo()
p = config.ParametrosActuariales(); S = p.smlv
T = cargar_tabla_mortalidad()
edades = T["Edad"].to_numpy()

# ---------- Fig: tabla de mortalidad real ----------
fig, ax = plt.subplots(1,2, figsize=(7.0,2.9))
for col,et,c in [("RV_Masculino","RV-08 hombres válidos",AZUL),
                 ("RV_Femenino","RV-08 mujeres válidas",NARANJA),
                 ("RI_Masculino","Serie de inválidos: hombres",VERDE),
                 ("RI_Femenino","Serie de inválidos: mujeres",ROJO)]:
    q = T[col].to_numpy(); m = q>0
    ax[0].semilogy(edades[m], q[m], color=c, label=et)
ax[0].set_xlabel("edad $x$ [años]"); ax[0].set_ylabel("$q_x$ (escala logarítmica)")
ax[0].set_title("(a) Tasas anuales de mortalidad", fontsize=9)
ax[0].legend(fontsize=6.6, loc="lower right"); ax[0].set_xlim(15,110)

# Ley de Gompertz: log q_x lineal en x.  Se ajusta en 40-95 anios.
q = T["RV_Masculino"].to_numpy(); msk = (edades>=40)&(edades<=95)&(q>0)
b,loga = np.polyfit(edades[msk], np.log(q[msk]), 1)
ax[1].semilogy(edades[msk], q[msk], color=AZUL, lw=1.8, label="RV-08 hombres")
ax[1].semilogy(edades[msk], np.exp(loga+b*edades[msk]), color=ROJO, ls="--",
               label=f"Gompertz ajustada, $b={b:.4f}$")
ax[1].set_xlabel("edad $x$ [años]"); ax[1].set_ylabel("$q_x$")
ax[1].set_title("(b) Contraste con la ley de Gompertz", fontsize=9)
ax[1].legend(fontsize=7)
resid = np.log(q[msk]) - (loga+b*edades[msk])
ax[1].text(.04,.90, f"$R^2={1-resid.var()/np.log(q[msk]).var():.4f}$",
           transform=ax[1].transAxes, fontsize=7.5, color=GRIS)
fig.suptitle("Series de mortalidad utilizadas en el archivo del cotizador", fontsize=10, y=1.05)
guardar(fig,"fig_tablas_mortalidad")
np.save(rutas.SAL / 'gompertz.npy', np.array([b,loga,1-resid.var()/np.log(q[msk]).var()]))

# ---------- Fig: supervivencia individual y conjunta REAL ----------
fv = pd.Timestamp("2026-07-31")
fechas = _generar_calendario(fv, config.N_MESES)
def npx_de(persona, es_causante):
    aux = datos_auxiliar(persona.sexo, persona.estado, persona.tipo_beneficiario, fv, persona.fecha_nacimiento)
    fap = (0.7 if persona.estado<2 else 1.0) if es_causante else (0.95 if persona.estado<2 else 1.0)
    dura = aux.dura_y if es_causante else aux.dura_y+1
    t = generar_tabla_mortalidad_mensualizada(fv, aux.edad_mensual, dura, persona.estado,
        aux.auxiliar, aux.auxiliar_2, aux.anio_factores_mejora, fap, fechas)
    return t["nPx"].to_numpy()

caus = Persona(date(1961,5,10),1,1,1)          # hombre 65
conyuge = Persona(date(1965,3,2),4,2,1)        # mujer 61
hijo = Persona(date(2010,4,12),2,1,1)          # hijo 16
n1, n2, n3 = npx_de(caus,True), npx_de(conyuge,False), npx_de(hijo,False)
conab2 = 1-(1-n1)*(1-n2)
conab3 = 1-(1-n1)*(1-n2)*(1-n3)
anios = np.arange(config.N_MESES)/12

fig, ax = plt.subplots(1,2, figsize=(7.0,2.9))
ax[0].plot(anios,n1,color=AZUL,label="causante (hombre, 65)")
ax[0].plot(anios,n2,color=NARANJA,label="cónyuge (mujer, 61)")
ax[0].plot(anios,conab2,color=VERDE,lw=2.0,label=r"conjunta $CONAB(t)$")
ax[0].fill_between(anios,np.maximum(n1,n2),conab2,color=VERDE,alpha=.18,lw=0)
ax[0].set_xlim(0,55); ax[0].set_xlabel("$t$ [años]"); ax[0].set_ylabel("probabilidad")
ax[0].set_title("(a) Grupo de dos vidas", fontsize=9); ax[0].legend(fontsize=7)
ax[0].text(31,.70,"ganancia de\ndiversificación",fontsize=6.8,color=VERDE,ha="center")

ax[1].plot(anios,n1,color=AZUL,label="causante")
ax[1].plot(anios,n2,color=NARANJA,label="cónyuge")
ax[1].plot(anios,n3,color=MORADO,label="hijo (16 años, derecho hasta los 25)")
ax[1].plot(anios,conab3,color=VERDE,lw=2.0,label=r"$CONAB(t)$, tres vidas")
ax[1].set_xlim(0,55); ax[1].set_xlabel("$t$ [años]")
ax[1].set_title("(b) Grupo de tres vidas con derecho temporal", fontsize=9)
ax[1].legend(fontsize=6.4, loc="lower left")
ax[1].annotate("caducidad del\nderecho del hijo", xy=(9.2,0.35), xytext=(17,.30),
               arrowprops=dict(arrowstyle="->",color=MORADO,lw=.9), fontsize=6.8, color=MORADO)
fig.suptitle("Factor de contingencia del amparo básico, calculado con las tablas reales", fontsize=10, y=1.05)
guardar(fig,"fig_supervivencia")

# ---------- Fig: fuerza de mortalidad implicita ----------
fig, ax = plt.subplots(figsize=(5.4,3.0))
for nn,et,c in [(n1,"causante (hombre, 65)",AZUL),(n2,"cónyuge (mujer, 61)",NARANJA)]:
    m = nn>1e-10
    mu = -np.gradient(np.log(np.where(m,nn,np.nan)), 1/12)
    ax.semilogy(anios[m], mu[m], color=c, label=et)
ax.set_xlim(0,50); ax.set_ylim(1e-3,1)
ax.set_xlabel("$t$ [años desde la valoración]"); ax.set_ylabel(r"$\mu_{x+t}$ [escala log]")
ax.set_title(r"Fuerza de mortalidad implícita, $\mu_{x+t}=-\frac{d}{dt}\ln{}_tp_x$")
ax.legend(fontsize=7.5)
guardar(fig,"fig_fuerza_mortalidad")

# ---------- Fig: descuento, tasas forward, Smith-Wilson ----------
D = DatosPoliza('G',13,date(2026,7,31),S,3*S,0.042,caus,[conyuge])
fw = _tasas_forward_mensuales(0.042, fechas, fv, p)
desc = np.ones(config.N_MESES)
for i in range(1,config.N_MESES): desc[i]=desc[i-1]/(1+fw[i-1])
sw = curva_smith_wilson({1.0:p.interes_tecnico_rp}, p.smith_wilson_ufr, p.smith_wilson_alpha, 120)

fig, ax = plt.subplots(1,2, figsize=(7.0,2.9))
ax[0].plot(anios, (1+fw)**12-1, color=AZUL, label="tasa nominal anualizada (real + IPC)")
ax[0].axhline(0.042, color=ROJO, ls="--", lw=1.0, label="interés técnico real, 4.20 %")
ax[0].set_xlim(0,40); ax[0].set_xlabel("$t$ [años]"); ax[0].set_ylabel("tasa efectiva anual")
ax[0].set_title("(a) Estructura temporal empleada", fontsize=9); ax[0].legend(fontsize=6.8)
ax[1].plot(np.arange(1,121), sw, color=VERDE, label=f"Smith-Wilson ($\\alpha={p.smith_wilson_alpha}$)")
ax[1].axhline(p.interes_tecnico_rp, color=AZUL, ls=":", lw=1.0, label="punto observado (año 1)")
ax[1].axhline(p.smith_wilson_ufr, color=ROJO, ls="--", lw=1.0, label=f"UFR = {p.smith_wilson_ufr:.0%}")
ax[1].set_xlim(0,120); ax[1].set_xlabel("plazo [años]"); ax[1].set_ylabel("tasa cupón cero")
ax[1].set_title("(b) Extrapolación Smith-Wilson (retiro programado)", fontsize=9)
ax[1].legend(fontsize=6.8)
fig.suptitle("Hipótesis financiera: descuento y extrapolación de la curva", fontsize=10, y=1.05)
guardar(fig,"fig_descuento")

# ---------- Fig: descomposicion de los flujos ----------
r = calcular_reserva(replace(D, mesada_actual=3*S), p, generar_flujos=True)
fl = r.construir_flujos()
fig, ax = plt.subplots(1,3, figsize=(7.2,2.5))
ax[0].plot(anios, fl["Mesada_Pensional_proyectada"], color=AZUL, label="mesada proyectada")
smlv_proj = S*np.array([1.0]*len(anios))
ax[0].set_xlim(0,60); ax[0].set_title("(a) Mesada proyectada", fontsize=8.5)
ax[0].yaxis.set_major_formatter(FMT_M)
ax[1].plot(anios, fl["Flujos_Renta_Supervivencia"], color=NARANJA)
ax[1].set_xlim(0,60); ax[1].set_title("(b) Flujo esperado\n(mesada $\\times\\ CONAB$)", fontsize=8.5)
ax[1].yaxis.set_major_formatter(FMT_M)
ax[2].plot(anios, fl["Flujos_Renta_Supervivencia_descontados"], color=VERDE)
ax[2].fill_between(anios, fl["Flujos_Renta_Supervivencia_descontados"], color=VERDE, alpha=.2, lw=0)
ax[2].set_xlim(0,60); ax[2].set_title("(c) Flujo descontado\n(el área es $VP$)", fontsize=8.5)
ax[2].yaxis.set_major_formatter(FMT_M)
for a in ax: a.set_xlabel("$t$ [años]", fontsize=8); a.tick_params(labelsize=7)
fig.suptitle("Descomposición del valor presente actuarial en sus tres factores", fontsize=10, y=1.06)
guardar(fig,"fig_flujos")
print("gompertz b=",b,"R2=",1-resid.var()/np.log(q[msk]).var())
