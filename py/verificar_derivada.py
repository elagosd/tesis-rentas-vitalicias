import rutas
import numpy as np
from datetime import date
from dataclasses import replace
from core.motor import DatosPoliza, Persona, calcular_reserva
from core import config

p = config.ParametrosActuariales()
base = DatosPoliza(id_pol='E', n_mesadas=13, fecha_valoracion=date(2026,7,31), smlv=p.smlv,
    mesada_actual=1.0, tasa_interes_real=0.0420,
    causante=Persona(date(1961,5,10),1,1,1),
    beneficiarios=[Persona(date(1965,3,2),4,2,1)])
def R(M, der=False): return calcular_reserva(replace(base, mesada_actual=float(M)), p, calcular_derivada=der)
S=p.smlv
print(f"{'M/SMLV':>9} {'VP':>18} {'D_izq':>12} {'D_der':>12} {'FD central':>12} {'act_renta':>9} {'act_auf':>8}")
for fr in [0.5,0.99,1.0,1.02,1.08,1.2,2.0,4.99,5.0,5.2,5.6,8.0,9.99,10.0,10.4,11.0,15.0]:
    M=S*fr; r=R(M,True)
    h=1e-3*M
    fd=(R(M+h).reserva_matematica - R(M-h).reserva_matematica)/(2*h)
    print(f"{fr:>9.4f} {r.reserva_matematica:>18,.2f} {r.derivada_rm_izq:>12.6f} {r.derivada_rm_der:>12.6f} {fd:>12.6f} {r.terminos_activos_renta:>9} {r.terminos_activos_auf:>8}")

print("\n--- Test de exactitud: VP(M+d) - VP(M) == D_der*d en tramo afin? ---")
for M0 in [3_000_000.0, 6_000_000.0, 30_000_000.0]:
    r=R(M0,True); d=50_000.0
    pred = r.reserva_matematica + r.derivada_rm_der*d
    real = R(M0+d).reserva_matematica
    print(f"  M0={M0:>12,.0f}  pred={pred:>18,.4f}  real={real:>18,.4f}  err_rel={abs(pred-real)/real:.3e}")

print("\n--- Convexidad: la pendiente debe ser no decreciente si VP fuera convexa ---")
pend=[(fr, R(S*fr,True).derivada_rm_der) for fr in [2.0,5.3,6.0,10.2,12.0]]
for i in range(1,len(pend)):
    signo = "OK (crece)" if pend[i][1]>=pend[i-1][1]-1e-12 else "VIOLACION DE CONVEXIDAD"
    print(f"  {pend[i-1][0]:>5} -> {pend[i][0]:>5}: {pend[i-1][1]:.6f} -> {pend[i][1]:.6f}   {signo}")
