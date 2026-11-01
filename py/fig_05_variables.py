# -*- coding: utf-8 -*-
"""Figuras y tablas del capitulo de evaluacion de variables."""
import rutas
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from dataclasses import replace
from datetime import date
from estilo_figuras import *
from core import config
from core.motor import DatosPoliza, Persona, calcular_reserva
from core.problema_tesis import escenarios_reales, constructor_objetivo
from core.metodos_iterativos import CriterioParada, brent
aplicar_estilo()
p=config.ParametrosActuariales(); S=p.smlv; SAL = rutas.SAL
caus=Persona(date(1961,5,10),1,1,1); cony=Persona(date(1965,3,2),4,2,1)
D=DatosPoliza('V',13,date(2026,7,31),S,3*S,0.042,caus,[cony])

# ---- Efecto de las hipotesis demograficas sobre VP ----
casos=[]
base=calcular_reserva(D,p).reserva_matematica
sinmej=calcular_reserva(replace(D,sin_factores_mejora=True),p).reserva_matematica
casos.append(("Sin factores de mejora de longevidad",(sinmej-base)/base*100))
# sin factor de aplicabilidad: se emula subiendo qx (aproximacion: estado invalido no; se
# recalcula con un motor parcheado no disponible) -> se mide con el causante sin conyuge
solo=calcular_reserva(replace(D,beneficiarios=[]),p).reserva_matematica
casos.append(("Sin cónyuge beneficiaria",(solo-base)/base*100))
hijo=calcular_reserva(replace(D,beneficiarios=[cony,Persona(date(2012,1,1),2,1,1)]),p).reserva_matematica
casos.append(("Con un hijo menor adicional",(hijo-base)/base*100))
mes14=calcular_reserva(replace(D,n_mesadas=14),p).reserva_matematica
casos.append(("Régimen de 14 mesadas",(mes14-base)/base*100))
inval=calcular_reserva(replace(D,causante=Persona(date(1961,5,10),1,1,2)),p).reserva_matematica
casos.append(("Causante inválido (serie del archivo)",(inval-base)/base*100))
mujer=calcular_reserva(replace(D,causante=Persona(date(1961,5,10),1,2,1),beneficiarios=[Persona(date(1965,3,2),4,1,1)]),p).reserva_matematica
casos.append(("Causante mujer (tabla RV-08 F)",(mujer-base)/base*100))
casos.sort(key=lambda c: c[1])
pd.DataFrame(casos,columns=["hipotesis","efecto_pct"]).to_csv(f'{SAL}/efecto_demografico.csv',index=False)

fig,ax=plt.subplots(figsize=(6.0,2.9))
y=np.arange(len(casos))
ax.barh(y,[c[1] for c in casos],color=[ROJO if c[1]<0 else AZUL for c in casos],height=.62)
ax.axvline(0,color=GRIS,lw=.9); ax.set_yticks(y); ax.set_yticklabels([c[0] for c in casos],fontsize=8)
ax.set_xlabel("efecto sobre la reserva matemática [%]"); ax.grid(axis="y",alpha=0)
ax.set_title("Peso relativo de las hipótesis demográficas y contractuales")
for i,c in enumerate(casos):
    ax.text(c[1]+(0.5 if c[1]>=0 else -0.5), i, f"{c[1]:+.1f}\\%".replace("\\",""), va="center",
            ha="left" if c[1]>=0 else "right", fontsize=7, color=GRIS)
guardar(fig,"fig_efecto_demografico")

# ---- Validacion contra la mesada real de la aseguradora ----
b7=pd.read_excel(rutas.BASE_RP)
esc=escenarios_reales(rutas.BASE_RP,p)
comp=[]
# Las polizas se rotulan P1, P2, ... para no publicar identificadores.
for i,(e,(_,fila)) in enumerate(zip(esc,b7.iterrows()), start=1):
    comp.append({"poliza":f"P{i}","modelo":e.mesada_teorica,
                 "aseguradora":float(fila["Mesada_RV"]),
                 "dif_pct":(e.mesada_teorica-float(fila["Mesada_RV"]))/float(fila["Mesada_RV"])*100})
cmp=pd.DataFrame(comp); cmp.to_csv(f'{SAL}/validacion_mesada.csv',index=False)

fig,ax=plt.subplots(1,2,figsize=(7.0,2.8))
ax[0].scatter(cmp.aseguradora/1e6, cmp.modelo/1e6, color=AZUL, s=34, zorder=3)
lims=[cmp.aseguradora.min()/1e6*.96, cmp.aseguradora.max()/1e6*1.04]
ax[0].plot(lims,lims,color=GRIS,ls="--",lw=1.0)
ax[0].set_xlabel("mesada reportada por la aseguradora [M\\$]".replace("\\",""))
ax[0].set_ylabel("mesada del modelo [M\\$]".replace("\\",""))
ax[0].set_title("(a) Modelo frente a referencia", fontsize=9)
ax[1].bar(range(len(cmp)), cmp.dif_pct, color=[VERDE if abs(v)<3 else NARANJA for v in cmp.dif_pct])
ax[1].axhline(0,color=GRIS,lw=.8)
ax[1].set_xticks(range(len(cmp))); ax[1].set_xticklabels(cmp.poliza,fontsize=7)
ax[1].set_ylabel("diferencia relativa [%]")
ax[1].set_title(f"(b) Discrepancia (media {cmp.dif_pct.mean():+.2f} %)", fontsize=9)
fig.suptitle("Contraste del modelo con siete cotizaciones de referencia", fontsize=10, y=1.05)
guardar(fig,"fig_validacion")
print(cmp.to_string(index=False))
print("\nefecto demografico:"); [print(f"  {c[0]:<40}{c[1]:+7.2f}%") for c in casos]

# macros
def _esp(x,d=2): return f"{x:.{d}f}".replace('.','{,}')
with open(rutas.TEX / 'datos_variables.tex','w',encoding='utf-8') as fh:
    fh.write("% Generado por py/fig_05_variables.py -- NO editar a mano.\n")
    fh.write("\\newcommand{\\datoValidMedia}{"+_esp(cmp.dif_pct.mean())+"}\n")
    fh.write("\\newcommand{\\datoValidMax}{"+_esp(cmp.dif_pct.abs().max())+"}\n")
    fh.write("\\newcommand{\\datoValidMin}{"+_esp(cmp.dif_pct.abs().min())+"}\n")
    fh.write("\\newcommand{\\datoEfectoMejora}{"+_esp(dict(casos)['Sin factores de mejora de longevidad'])+"}\n")
    fh.write("\\newcommand{\\datoEfectoConyuge}{"+_esp(dict(casos)['Sin cónyuge beneficiaria'])+"}\n")
    fh.write("\\newcommand{\\datoEfectoCatorce}{"+_esp(dict(casos)['Régimen de 14 mesadas'])+"}\n")
    fh.write("\\newcommand{\\datoEfectoInvalido}{"+_esp(dict(casos)['Causante inválido (serie del archivo)'])+"}\n")
    fh.write("\\newcommand{\\datoEfectoMujer}{"+_esp(dict(casos)['Causante mujer (tabla RV-08 F)'])+"}\n")
