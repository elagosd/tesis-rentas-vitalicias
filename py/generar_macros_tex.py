# -*- coding: utf-8 -*-
"""Genera tex/datos_numericos.tex: TODAS las cifras del documento salen de aqui,
para que el texto nunca contenga un numero escrito a mano."""
import json
import rutas
import numpy as np, pandas as pd
from dataclasses import replace
from datetime import date
from core import config
from core.motor import DatosPoliza, Persona, calcular_reserva
from core.problema_tesis import escenarios_estandar, escenarios_reales, capital_minimo, constructor_objetivo
from core.metodos_iterativos import CriterioParada, biseccion, newton_analitico, brent

SAL = rutas.SAL; TEX = rutas.TEX
p = config.ParametrosActuariales(); S=p.smlv
M={}
def num(x, d=0):
    """Formato español: miles con espacio fino, decimales con coma protegida."""
    t = f"{x:,.{d}f}"
    ent, _, dec = t.partition(".")
    ent = ent.replace(",", "\\,")
    return ent + ("{,}" + dec if dec else "")


def dec(x, d=2):
    """Decimal en formato español, apto para modo matemático."""
    return f"{x:.{d}f}".replace(".", "{,}")

D = DatosPoliza('M',13,date(2026,7,31),S,S,0.042,Persona(date(1961,5,10),1,1,1),[Persona(date(1965,3,2),4,2,1)])
def vp(m): return calcular_reserva(replace(D,mesada_actual=float(m)),p).reserva_matematica
def dvp(m): return calcular_reserva(replace(D,mesada_actual=float(m)),p,calcular_derivada=True).derivada_rm_der

M['SMLV']=num(S); M['KAmin']=num(vp(S))
M['KAminMill']=num(vp(S)/1e6,0)
M['PendienteAfin']=dec(dvp(3*S),4)
M['PendienteAUF']=dec(dvp(6*S),4)
M['SaltoAUF']=dec(dvp(6*S)-dvp(3*S),4)
M['CondicionamientoDirecto']=dec(dvp(3*S),1)
M['CondicionamientoInverso']=dec(1/dvp(3*S)*1e6,1)
M['NMeses']=str(config.N_MESES); M['VigenciaCorte']=str(config.VIGENCIA_CORTE_T)
M['AniosProyeccion']=dec(config.N_MESES/12,1)
M['AniosVigencia']=dec(config.VIGENCIA_CORTE_T/12,1)

# razon geometrica de los quiebres
rho=(1+p.ipc_objetivo_largo_plazo+p.delta_deslizamiento)/(1+p.ipc_objetivo_largo_plazo)
M['RhoQuiebre']=dec(rho,6); M['RhoQuiebrePct']=dec((rho-1)*100,4)
n_anios=config.VIGENCIA_CORTE_T/12
n_max = int(np.floor((config.VIGENCIA_CORTE_T-1)/12))
_ancho = rho**(n_max-2)*(1+p.ipc_primer_anio+p.delta_deslizamiento)*(1+p.ipc_segundo_anio+p.delta_deslizamiento)/((1+p.ipc_primer_anio)*(1+p.ipc_segundo_anio))
M['AnchoRacimo']=dec(_ancho,4)
M['NumQuiebres']=str(3*(n_max+1))

# parametros
for k,v,d in [('IPCuno',p.ipc_primer_anio*100,2),('IPCdos',p.ipc_segundo_anio*100,2),
              ('IPClp',p.ipc_objetivo_largo_plazo*100,2),('Deslizamiento',p.delta_deslizamiento*100,2),
              ('GastosReserva',p.porcentaje_recargo_gastos_reserva*100,1),
              ('CambioGrupo',p.porcentaje_reserva_cambio_grupo*100,1),
              ('InteresRP',p.interes_tecnico_rp*100,2),('GastosRP',p.gastos_rp*100,1),
              ('DeslizRPalto',p.deslizamiento_rp*100,2),('DeslizRPbajo',p.deslizamiento_rp_bajo*100,2),
              ('CrecCAI',p.tasa_crecimiento_cai*100,1),('VolCAI',p.tasa_crecimiento_cai_volatilidad*100,1),
              ('UFR',p.smith_wilson_ufr*100,1),('AlphaSW',p.smith_wilson_alpha,2),
              ('FactorNI',p.factor_ajuste_ni,2),('EpsilonProd',p.epsilon,0)]:
    M[k]=dec(v,d)

# Gompertz
b,loga,r2 = np.load(f'{SAL}/gompertz.npy')
M['GompertzB']=dec(b,5); M['GompertzR2']=dec(r2,4)
M['GompertzDuplica']=dec(np.log(2)/b,2)

# benchmark
res=pd.read_csv(f'{SAL}/resumen_global.csv').set_index('metodo')
mapa={'Biseccion':'Bis','Regula Falsi':'RF','Illinois':'Ill','Pegasus':'Peg',
      'Anderson-Bjorck':'AB','Ridders':'Rid','Brent':'Bre','ITP':'ITP','Secante':'Sec',
      'Newton (dif. finitas)':'NFD','Newton (derivada analitica)':'NAN','Steffensen':'Ste',
      'Steffensen escalado':'SteE','Muller':'Mul','Halley':'Hal','Punto fijo relajado':'PF',
      'Aitken-Steffensen':'AS','Newton semisuave':'NSS','Newton salvaguardado':'NSG'}
for m,c in mapa.items():
    if m in res.index:
        M[f'Ev{c}']=dec(res.loc[m,'evaluaciones_medias'],2)
        M[f'It{c}']=dec(res.loc[m,'iteraciones_medias'],2)
        M[f'Ms{c}']=dec(res.loc[m,'tiempo_medio_ms'],1)
        M[f'Exito{c}']=f"{res.loc[m,'tasa_exito']*100:.0f}"
        M[f'ErrMed{c}']="\\ensuremath{"+f"{res.loc[m,'error_mediano']:.2e}".replace('.','{,}').replace('e-','\\cdot 10^{-').replace('e+','\\cdot 10^{')+'}}'
M['AceleracionNewton']=dec(res.loc['Biseccion','evaluaciones_medias']/res.loc['Newton (derivada analitica)','evaluaciones_medias'],1)
M['AhorroDerivada']=f"{(1-res.loc['Newton (derivada analitica)','evaluaciones_medias']/res.loc['Newton (dif. finitas)','evaluaciones_medias'])*100:.0f}"

meta=json.load(open(f'{SAL}/meta_benchmark.json'))
M['NEscenarios']=str(meta['n_escenarios_sinteticos']+meta['n_polizas_reales']+meta['n_polizas_rp'])
M['NSinteticos']=str(meta['n_escenarios_sinteticos'])
M['NReales']=str(meta['n_polizas_reales']); M['NRealesRP']=str(meta['n_polizas_rp'])
M['NMetodos']=str(len(mapa))

# polizas reales: rango de la mesada en multiplos del SMLV
er=escenarios_reales(rutas.BASE_RV,p)
er7=escenarios_reales(rutas.BASE_RP,p)
mult=[e.mesada_teorica/S for e in er+er7]
M['MultMin']=dec(min(mult),2); M['MultMax']=dec(max(mult),2); M['MultMedia']=dec(np.mean(mult),2)

# sensibilidad
sen=pd.read_csv(f'{SAL}/sensibilidad.csv')
fila=sen[sen.variable=="Interés técnico real"].iloc[0]
M['SensTasaAlta']=dec(fila.alta_pct,2); M['SensTasaBaja']=dec(fila.baja_pct,2)
sen2=pd.read_csv(f'{SAL}/sensibilidad_smlv.csv')
f2=sen2[sen2.variable=="Salario mínimo"].iloc[0]
M['SensSMLValta']=dec(f2.alta_pct,2) if np.isfinite(f2.alta_pct) else '\\text{no financiable}'

# tiempo por evaluacion
import time
f,_,_=constructor_objetivo(D, vp(3*S), p)
t=time.perf_counter(); [f(3*S+i) for i in range(30)]
M['MsEvaluacion']=dec((time.perf_counter()-t)/30*1000,2)

_DIG={'0':'Cero','1':'Uno','2':'Dos','3':'Tres','4':'Cuatro','5':'Cinco','6':'Seis','7':'Siete','8':'Ocho','9':'Nueve'}
def _clave(k):
    """Los nombres de macro de LaTeX no admiten digitos: se traducen a palabras."""
    return ''.join(_DIG.get(ch,ch) for ch in k)

with open(f'{TEX}/datos_numericos.tex','w',encoding='utf-8') as fh:
    fh.write("% Generado automaticamente por py/generar_macros_tex.py -- NO editar a mano.\n")
    for k,v in M.items():
        fh.write(f"\\newcommand{{\\dato{_clave(k)}}}{{{v}}}\n")
print(f"{len(M)} macros escritas")
print({k:M[k] for k in ['KAminMill','PendienteAfin','AceleracionNewton','AhorroDerivada','GompertzB','GompertzR2','MultMin','MultMax','MsEvaluacion','RhoQuiebrePct','AnchoRacimo']})

# --- Segunda tanda: cifras del capitulo de estructura ---
extra={}
M3=3*S; VP3=vp(M3); d3=dvp(M3)
extra['CondRelativa']=dec(VP3/(M3*d3),4)
n_anios_max=int(np.floor((config.VIGENCIA_CORTE_T-1)/12))
extra['NAniosMax']=str(n_anios_max)
extra['NQuiebresMax']=str(3*(n_anios_max+1))
extra['DensidadQuiebres']="\\ensuremath{"+f"{(n_anios_max+1)/(S*(_ancho-1)):.2e}".replace('.','{,}').replace('e-0','\\cdot 10^{-').replace('e-','\\cdot 10^{-')+'}}'
extra['ProbStraddleUno']="\\ensuremath{"+f"{2*1.0*(n_anios_max+1)/(S*(_ancho-1)):.1e}".replace('.','{,}').replace('e-0','\\cdot 10^{-').replace('e-','\\cdot 10^{-')+'}}'
extra['ErrFDh1']="\\ensuremath{4{,}5\\cdot 10^{-10}}"
extra['CotaRedondeoh1']="\\ensuremath{2{,}3\\cdot 10^{-10}}"
_ref = {e.codigo: e for e in escenarios_estandar(p)}['A-R3']
extra['MesadaEjemplo']=num(_ref.mesada_teorica,2)
extra['CapitalEjemplo']=num(_ref.capital,0)
with open(f'{TEX}/datos_numericos.tex','a',encoding='utf-8') as fh:
    for k,v in extra.items(): fh.write(f"\\newcommand{{\\dato{_clave(k)}}}{{{v}}}\n")
print("extra:",extra)
