# -*- coding: utf-8 -*-
"""Corre el banco de pruebas completo y guarda las tablas de la tesis."""
import time, json
import rutas
import pandas as pd
from core.problema_tesis import escenarios_estandar, escenarios_reales, capital_minimo
from core.banco_pruebas import tabla_resultados, resumen_por_metodo
from core.metodos_iterativos import CriterioParada
from core import config

SAL = rutas.SAL
p = config.ParametrosActuariales()

est = escenarios_estandar(p)
reales = escenarios_reales(rutas.BASE_RV, p)
reales7 = escenarios_reales(rutas.BASE_RP, p)

t0=time.perf_counter()
# Tolerancia de produccion (1 peso) y tolerancia estricta (1e-6 pesos)
crit_prod = CriterioParada(epsilon_f=1.0, epsilon_x=1e-8, max_iteraciones=200, paso_derivada=1.0)
crit_fino = CriterioParada(epsilon_f=1e-6, epsilon_x=1e-10, max_iteraciones=300, paso_derivada=1.0)

tab_sint = tabla_resultados(est, p, crit_prod);      tab_sint['conjunto']='sinteticos'
tab_real = tabla_resultados(reales, p, crit_prod);   tab_real['conjunto']='polizas_reales'
tab_r7   = tabla_resultados(reales7, p, crit_prod);  tab_r7['conjunto']='polizas_rp'
tab_fino = tabla_resultados(est, p, crit_fino);      tab_fino['conjunto']='sinteticos_tol_fina'

tab = pd.concat([tab_sint,tab_real,tab_r7,tab_fino], ignore_index=True)
tab.to_csv(f'{SAL}/tabla_larga.csv', index=False)

for nombre, sub in [('sinteticos',tab_sint),('polizas_reales',tab_real),('polizas_rp',tab_r7),('tol_fina',tab_fino)]:
    resumen_por_metodo(sub).to_csv(f'{SAL}/resumen_{nombre}.csv', index=False)

resumen_por_metodo(pd.concat([tab_sint,tab_real,tab_r7],ignore_index=True)).to_csv(f'{SAL}/resumen_global.csv', index=False)

meta = {
  'n_escenarios_sinteticos': len(est),
  'n_polizas_reales': len(reales),
  'n_polizas_rp': len(reales7),
  'smlv': p.smlv,
  'capital_minimo_A': capital_minimo(est[0].datos, p),
  'segundos': round(time.perf_counter()-t0,2),
}
json.dump(meta, open(f'{SAL}/meta_benchmark.json','w'), indent=2)
print(json.dumps(meta, indent=2))
print(resumen_por_metodo(pd.concat([tab_sint,tab_real,tab_r7],ignore_index=True)).to_string(index=False, float_format=lambda v: f'{v:,.4g}'))
