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

def VP(M):
    return calcular_reserva(replace(base, mesada_actual=float(M)), p).reserva_matematica

S = p.smlv
print(f"SMLV = {S:,.0f}")
print("\n--- ¿Es VP constante por debajo del SMLV? ---")
for frac in [0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99, 0.999, 1.0]:
    M = S*frac
    print(f"  M/SMLV={frac:<7} VP={VP(M):>18,.2f}")

print("\n--- Pendiente numerica (diferencia hacia adelante, h=100) ---")
h=100.0
fracs = [0.5, 0.9, 1.0, 1.0005, 1.002, 1.01, 1.05, 1.10, 1.15, 1.16, 1.17, 1.20, 1.5,
         2.0, 3.0, 4.9, 5.0, 5.1, 5.5, 5.9, 6.0, 7.0, 9.9, 10.0, 10.5, 11.0, 11.7, 12.0, 15.0, 20.0]
prev=None
for fr in fracs:
    M = S*fr
    d = (VP(M+h)-VP(M-h))/(2*h)
    marca = ""
    if prev is not None and abs(d-prev)/max(abs(prev),1e-12) > 1e-6: marca = "  <== CAMBIO DE PENDIENTE"
    print(f"  M/SMLV={fr:<7} VP'={d:>12.6f}{marca}")
    prev=d
