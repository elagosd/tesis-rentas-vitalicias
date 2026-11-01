# -*- coding: utf-8 -*-
"""Figuras de retiro programado, sensibilidad y robustez numerica."""
import copy
import rutas
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from dataclasses import replace
from datetime import date
from estilo_figuras import *
from core import config
from core.motor import calcular_reserva
from core.problema_tesis import escenarios_estandar, escenarios_reales, constructor_objetivo
from core.metodos_iterativos import (CriterioParada, biseccion, secante, newton_diferencias,
                                     newton_analitico, newton_semisuave, brent, illinois)
from core.retiro_programado import resolver_y_proyectar_rp_para_fila, proyectar_rp_dinamico_cai
from core.base_masiva import _fila_a_datos_poliza, proyeccion_mesada_por_anio

aplicar_estilo()
p = config.ParametrosActuariales(); S=p.smlv
SAL = rutas.SAL
crit = CriterioParada(epsilon_f=1.0, epsilon_x=1e-8, max_iteraciones=200, paso_derivada=1.0)

# ================= Fig: Retiro programado vs renta vitalicia =================
base7 = pd.read_excel(rutas.BASE_RP)
fila = base7.iloc[0]
esc7 = escenarios_reales(rutas.BASE_RP, p, limite=1)[0]
mesada_rv = esc7.mesada_teorica

proy_rv = proyeccion_mesada_por_anio(fila, mesada_rv, p, max_anios=20)
proy_rp, _ = resolver_y_proyectar_rp_para_fila(fila, p, max_anios=20, mesada_rv_encontrada=mesada_rv)

fig, ax = plt.subplots(1,2, figsize=(7.0,2.9))
ax[0].plot(proy_rv["Anio"], proy_rv["Mesada_Pensional_proyectada"], color=AZUL,
           marker="o", ms=3, label="Renta vitalicia")
ax[0].plot(proy_rp["Anio"], proy_rp["Mesada_Pensional_proyectada"], color=ROJO,
           marker="s", ms=3, label="Retiro programado")
ax[0].plot(proy_rp["Anio"], proy_rp["Mesada_sin_piso"], color=ROJO, ls=":", lw=1.0,
           label="RP antes de ajustes")
ax[0].set_xlabel("año"); ax[0].set_ylabel("mesada [pesos]"); ax[0].yaxis.set_major_formatter(FMT_M)
ax[0].set_title("(a) Trayectoria de la mesada", fontsize=9); ax[0].legend(fontsize=7)
ax[1].plot(proy_rp["Anio"], proy_rp["Saldo_CAI_inicio_anio"], color=VERDE, marker="o", ms=3)
ax[1].fill_between(proy_rp["Anio"], proy_rp["Saldo_CAI_inicio_anio"], color=VERDE, alpha=.2, lw=0)
ax[1].set_xlabel("año"); ax[1].set_ylabel("saldo de la CAI [pesos]")
ax[1].yaxis.set_major_formatter(FMT_M)
ax[1].set_title("(b) Evolución de la cuenta individual", fontsize=9)
ax2 = ax[1].twinx()
ax2.bar(proy_rp["Anio"], proy_rp["Tasa_crecimiento_CAI_este_anio"], color=NARANJA, alpha=.45, width=.6)
ax2.set_ylabel("rendimiento sorteado", fontsize=8, color=NARANJA)
ax2.tick_params(labelsize=7, colors=NARANJA); ax2.grid(False)
from matplotlib.ticker import MaxNLocator
for a in (ax[0],ax[1]): a.xaxis.set_major_locator(MaxNLocator(integer=True))
ax[0].annotate("fin de la simulación\ndel escenario",
               xy=(proy_rp["Anio"].iloc[-1], proy_rp["Mesada_Pensional_proyectada"].iloc[-1]),
               xytext=(proy_rp["Anio"].iloc[-1]-9, proy_rp["Mesada_Pensional_proyectada"].min()*0.92),
               arrowprops=dict(arrowstyle="->", color=ROJO, lw=.9), fontsize=6.6, color=ROJO)
fig.suptitle("Retiro programado: escenario ilustrativo con ajustes del cotizador",
             fontsize=9.5, y=1.05)
guardar(fig,"fig_rp_vs_rv")

# ================= Fig: propagacion del error en la recursion RP =================
datos_rp = _fila_a_datos_poliza(fila); datos_rp.smlv = p.smlv
capital0 = float(fila["capital_renta"])
mesada_rv_por_anio = {int(r["Anio"]): float(r["Mesada_Pensional_proyectada"])
                      for _,r in proy_rv.iterrows()}
perturbaciones = [0.0, 1.0, 1e2, 1e4, 1e6]
trayectorias = {}
for d in perturbaciones:
    pr = proyectar_rp_dinamico_cai(datos_rp, capital0 + d, p, max_anios=15,
                                   mesada_rv_por_anio=mesada_rv_por_anio, semilla_aleatoria=20260822)
    trayectorias[d] = pr

fig, ax = plt.subplots(1,2, figsize=(7.0,2.9))
ref = trayectorias[0.0]
for i,d in enumerate(perturbaciones[1:]):
    tr = trayectorias[d]
    n = min(len(tr), len(ref))
    err = np.abs(tr["Mesada_Pensional_proyectada"].to_numpy()[:n] -
                 ref["Mesada_Pensional_proyectada"].to_numpy()[:n])
    ax[0].semilogy(np.arange(1,n+1), np.maximum(err,1e-9), marker="o", ms=3,
                   color=PALETA[i], label=f"$\\delta KA = 10^{{{int(np.log10(d))}}}$")
    errs = np.abs(tr["Saldo_CAI_inicio_anio"].to_numpy()[:n] - ref["Saldo_CAI_inicio_anio"].to_numpy()[:n])
    ax[1].semilogy(np.arange(1,n+1), np.maximum(errs,1e-9), marker="o", ms=3, color=PALETA[i])
g = 1+p.tasa_crecimiento_cai
kk = np.arange(1,13)
ax[1].semilogy(kk, 1e4*g**kk, color=GRIS, ls="--", lw=1.0, label="referencia con rendimiento medio")
ax[0].set_xlabel("año $n$"); ax[0].set_ylabel(r"$\max(|M_n^{\delta}-M_n|,\,10^{-9})$ [pesos]")
ax[0].set_title("(a) Mesada: ceros situados en $10^{-9}$", fontsize=9); ax[0].legend(fontsize=6.8)
ax[1].set_xlabel("año $n$"); ax[1].set_ylabel(r"$|CAI_n^{\delta}-CAI_n|$ [pesos]")
ax[1].set_title("(b) Error en el saldo de la cuenta", fontsize=9); ax[1].legend(fontsize=7)
fig.suptitle("Propagación del error a lo largo de la recursión de retiro programado", fontsize=10, y=1.05)
guardar(fig,"fig_propagacion_error_rp")

# ================= Fig: sensibilidad (tornado) =================
esc = {e.codigo:e for e in escenarios_estandar(p)}
e0 = esc["A-R3"]

def resolver(params, datos, capital):
    """Mesada de equivalencia, o NaN si el capital no financia el minimo.

    La insuficiencia se diagnostica comparando el capital con VP(S0)
    (recomendacion R1), no a partir del fracaso del metodo numerico.
    """
    f, dfd, _ = constructor_objetivo(datos, capital, params)
    if f(params.smlv) > 0:
        return float("nan")
    return brent(f, params.smlv, params.smlv*25, CriterioParada(1e-6,1e-10,300)).raiz

base_val = resolver(p, e0.datos, e0.capital)
variaciones = [
    ("Interés técnico real",     "tasa",  0.0420, 0.0050),
    ("IPC de largo plazo",       "ipc_objetivo_largo_plazo", p.ipc_objetivo_largo_plazo, 0.0050),
    ("IPC primer año",           "ipc_primer_anio", p.ipc_primer_anio, 0.0100),
    ("Deslizamiento",            "delta_deslizamiento", p.delta_deslizamiento, 0.0010),
    ("Recargo de gastos",        "porcentaje_recargo_gastos_reserva", p.porcentaje_recargo_gastos_reserva, 0.0100),
    ("Reserva cambio de grupo",  "porcentaje_reserva_cambio_grupo", p.porcentaje_reserva_cambio_grupo, 0.0020),
    ("Salario mínimo",           "smlv", p.smlv, p.smlv*0.05),
]
filas=[]
for etiqueta, campo, valor, delta in variaciones:
    vals=[]
    for signo in (-1,1):
        if campo=="tasa":
            d2 = replace(e0.datos, tasa_interes_real=valor+signo*delta)
            vals.append(resolver(p, d2, e0.capital))
        else:
            p2 = replace(p, **{campo: valor+signo*delta})
            d2 = replace(e0.datos, smlv=p2.smlv)
            vals.append(resolver(p2, d2, e0.capital))
    filas.append((etiqueta, (vals[0]-base_val)/base_val*100, (vals[1]-base_val)/base_val*100, delta))
filas.sort(key=lambda r: max(abs(r[1]),abs(r[2])))
pd.DataFrame(filas, columns=["variable","baja_pct","alta_pct","delta"]).to_csv(f'{SAL}/sensibilidad.csv',index=False)

# Se repite el mismo analisis con una raiz DENTRO del racimo de quiebres del
# SMLV: el contraste entre ambos paneles es uno de los resultados del
# capitulo -- que hipotesis domina depende de la REGION en que caiga la raiz.
e1 = esc["A-R2"]
base_val1 = resolver(p, e1.datos, e1.capital)
filas1=[]
for etiqueta, campo, valor, delta in variaciones:
    vals=[]
    for signo in (-1,1):
        if campo=="tasa":
            d2 = replace(e1.datos, tasa_interes_real=valor+signo*delta)
            vals.append(resolver(p, d2, e1.capital))
        else:
            p2 = replace(p, **{campo: valor+signo*delta})
            d2 = replace(e1.datos, smlv=p2.smlv)
            vals.append(resolver(p2, d2, e1.capital))
    filas1.append((etiqueta,(vals[0]-base_val1)/base_val1*100,(vals[1]-base_val1)/base_val1*100,delta))
orden = [f[0] for f in filas]
filas1.sort(key=lambda r: orden.index(r[0]))
pd.DataFrame(filas1, columns=["variable","baja_pct","alta_pct","delta"]).to_csv(f'{SAL}/sensibilidad_smlv.csv',index=False)

fig, axs = plt.subplots(1,2, figsize=(7.2,3.2), sharey=True)
for a,(datos_f,tit) in zip(axs,[(filas,"(a) Raíz en el tramo afín (2.41 SMLV)"),
                                (filas1,"(b) Raíz en el racimo del SMLV (1.04 SMLV)")]):
    for i,(et,lo,hi,_) in enumerate(datos_f):
        sin_fin = []
        if np.isfinite(lo): a.barh(i, lo, color=ROJO, height=.62, alpha=.85)
        else: sin_fin.append("baja")
        if np.isfinite(hi): a.barh(i, hi, color=AZUL, height=.62, alpha=.85)
        else: sin_fin.append("alza")
        # Sin barra cuando el capital no financia el minimo (recomendacion R1):
        # el rotulo se escribe del lado en que habria quedado la barra.
        if "baja" in sin_fin:
            a.text(-0.15, i, "baja: sin financiación", ha="right", va="center", fontsize=6.6, color=GRIS)
        if "alza" in sin_fin:
            a.text(0.15, i, "alza: sin financiación", ha="left", va="center", fontsize=6.6, color=GRIS)
    a.axvline(0,color=GRIS,lw=.9); a.grid(axis="y",alpha=0)
    a.set_xlabel("variación de la mesada [%]", fontsize=8.5)
    a.set_title(tit, fontsize=8.8); a.tick_params(labelsize=7.5)
axs[1].set_xlim(-5.5, 7.0)
axs[0].set_yticks(np.arange(len(filas))); axs[0].set_yticklabels([f[0] for f in filas], fontsize=8)
axs[0].barh([np.nan],[np.nan],color=AZUL,label="hipótesis al alza")
axs[0].barh([np.nan],[np.nan],color=ROJO,label="hipótesis a la baja")
axs[0].legend(fontsize=7.2, loc="lower left")
fig.suptitle("Sensibilidad de la mesada: qué hipótesis domina depende de la región", fontsize=10, y=1.04)
guardar(fig,"fig_sensibilidad")

# ================= Fig: robustez frente al punto inicial =================
f, dfd, _ = constructor_objetivo(e0.datos, e0.capital, p)
# Newton semisuave obtiene valor y derivada en una misma llamada al motor.
f_conj, dfd_conj, _ = constructor_objetivo(e0.datos, e0.capital, p, derivada_conjunta=True)
x0s = np.linspace(1.02*S, 24.5*S, 90)
series = {"Secante":[], "Newton (dif. finitas)":[], "Newton semisuave":[]}
for x0 in x0s:
    series["Secante"].append(secante(f, x0, min(x0*1.5, 25*S), crit, lo=S, hi=25*S))
    series["Newton (dif. finitas)"].append(newton_diferencias(f, x0, crit, lo=S, hi=25*S))
    series["Newton semisuave"].append(newton_semisuave(f_conj, dfd_conj, x0, crit, lo=S, hi=25*S))

fig, ax = plt.subplots(1,2, figsize=(7.0,2.8))
for i,(m,rs) in enumerate(series.items()):
    ax[0].plot(x0s/S, [r.evaluaciones_funcion for r in rs], color=PALETA[i], label=m, lw=1.3)
    err = [abs(r.raiz-e0.mesada_teorica) for r in rs]
    ax[1].semilogy(x0s/S, np.maximum(err,1e-12), color=PALETA[i], lw=1.3)
ax[0].axhline(np.mean([r.evaluaciones_funcion for r in
                       [biseccion(f,S,25*S,crit)]]), color=GRIS, ls="--", lw=1.0,
              label="Bisección (independiente de $x_0$)")
ax[0].axvline(e0.mesada_teorica/S, color=ROJO, ls=":", lw=.9)
ax[1].axvline(e0.mesada_teorica/S, color=ROJO, ls=":", lw=.9)
ax[0].set_xlabel("punto inicial $x_0$ / SMLV"); ax[0].set_ylabel("llamadas al motor")
ax[0].set_title("(a) Costo según el punto de arranque", fontsize=9); ax[0].legend(fontsize=6.6)
ax[1].set_xlabel("punto inicial $x_0$ / SMLV"); ax[1].set_ylabel("error final [pesos]")
ax[1].set_title("(b) Exactitud alcanzada", fontsize=9)
fig.suptitle("Robustez de los métodos abiertos frente al punto inicial", fontsize=10, y=1.05)
guardar(fig,"fig_robustez_inicial")
print("base_val", base_val)
