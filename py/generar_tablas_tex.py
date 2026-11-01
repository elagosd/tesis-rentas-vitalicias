# -*- coding: utf-8 -*-
"""Genera las tablas LaTeX del capitulo de resultados a partir del benchmark."""
import rutas
import pandas as pd
import numpy as np

SAL = rutas.SAL
TAB = rutas.TABLAS

NOMBRE = {
    'Biseccion': 'Bisección', 'Regula Falsi': 'Regula falsi', 'Illinois': 'Illinois',
    'Pegasus': 'Pegasus', 'Anderson-Bjorck': 'Anderson--Björck', 'Ridders': 'Ridders',
    'Brent': 'Brent', 'ITP': 'ITP', 'Secante': 'Secante',
    'Newton (dif. finitas)': 'Newton (dif.\\ finitas)',
    'Newton (derivada analitica)': 'Newton (analítico)', 'Steffensen': 'Steffensen',
    'Steffensen escalado': 'Steffensen escalado', 'Muller': 'Müller', 'Halley': 'Halley',
    'Punto fijo relajado': 'Punto fijo relajado', 'Aitken-Steffensen': 'Aitken--Steffensen',
    'Newton semisuave': 'Newton semisuave', 'Newton salvaguardado': 'Newton salvaguardado',
}
FAM = {'encaje': 'encaje', 'abierto': 'abierto', 'no suave': 'no suave'}


def esp(x, d=2):
    """Decimal con coma protegida, para modo texto y matemático."""
    return f"{x:.{d}f}".replace(".", "{,}")


def sci(v):
    if pd.isna(v):
        return '---'
    if v == 0:
        return '$0$'
    e = int(np.floor(np.log10(abs(v))))
    m = v / 10 ** e
    return f"${esp(m,1)}\\cdot10^{{{e}}}$"


# ---------- Tabla global ----------
g = pd.read_csv(f'{SAL}/resumen_global.csv').sort_values('evaluaciones_medias')
lin = ["\\begin{tabular}{@{}llrrrrr@{}}", "\\toprule",
       "\\textbf{Método} & \\textbf{Familia} & \\textbf{Éxito} & \\textbf{Ev.\\ media} & "
       "\\textbf{Ev.\\ máx.} & \\textbf{Iter.} & \\textbf{Error mediano} \\\\", "\\midrule"]
for _, r in g.iterrows():
    lin.append(f"{NOMBRE.get(r.metodo, r.metodo)} & {FAM[r.familia]} & {r.tasa_exito*100:.0f}\\% & "
               f"{esp(r.evaluaciones_medias)} & {int(r.evaluaciones_max)} & {esp(r.iteraciones_medias)} & "
               f"{sci(r.error_mediano)} \\\\")
lin += ["\\bottomrule", "\\end{tabular}"]
open(f'{TAB}/tabla_global.tex', 'w', encoding='utf-8').write("\n".join(lin))

# ---------- Tabla por region estructural ----------
t = pd.read_csv(f'{SAL}/tabla_larga.csv')
t = t[t.conjunto == 'sinteticos'].copy()
regiones = {
    'banda de quiebres del piso SMLV': 'R2 (racimo I)',
    'tramo afin comercial': 'R3 (afín)',
    'banda de quiebres del auxilio funerario (5 SMLV)': 'R4 (racimo II)',
    'banda de quiebres del auxilio funerario (10 SMLV)': 'R5 (racimo III)',
}
t['reg'] = t.region.map(regiones)
sel = ['Biseccion', 'Brent', 'Illinois', 'Secante', 'Newton (dif. finitas)',
       'Newton (derivada analitica)', 'Newton salvaguardado', 'Punto fijo relajado', 'Halley']
piv = t[t.metodo.isin(sel)].pivot_table(index='metodo', columns='reg',
                                        values='evaluaciones', aggfunc='mean')
cols = [c for c in ['R2 (racimo I)', 'R3 (afín)', 'R4 (racimo II)', 'R5 (racimo III)']
        if c in piv.columns]
piv = piv.reindex(sel)[cols]
lin = ["\\begin{tabular}{@{}l" + "r" * len(cols) + "@{}}", "\\toprule",
       "\\textbf{Método} & " + " & ".join(f"\\textbf{{{c}}}" for c in cols) + " \\\\", "\\midrule"]
for m, row in piv.iterrows():
    lin.append(NOMBRE.get(m, m) + " & " + " & ".join(
        ("---" if pd.isna(v) else esp(v,1)) for v in row) + " \\\\")
lin += ["\\bottomrule", "\\end{tabular}"]
open(f'{TAB}/tabla_region.tex', 'w', encoding='utf-8').write("\n".join(lin))

# ---------- Tabla completa del apendice ----------
lin = ["\\begin{longtable}{@{}llrrrrr@{}}", "\\toprule",
       "\\textbf{Conjunto} & \\textbf{Método} & \\textbf{Éxito} & \\textbf{Ev.} & \\textbf{Iter.} & "
       "\\textbf{ms} & \\textbf{Error mediano} \\\\", "\\midrule", "\\endhead"]
tt = pd.read_csv(f'{SAL}/tabla_larga.csv')
etiq = {'sinteticos': 'Sintéticos', 'polizas_reales': 'Pólizas RV',
        'polizas_rp': 'Registros adicionales', 'sinteticos_tol_fina': 'Sint.\\ tol.\\ fina'}
for conj, sub in tt.groupby('conjunto'):
    r = sub.groupby('metodo').agg(
        exito=('convergio', 'mean'), ev=('evaluaciones', 'mean'),
        it=('iteraciones', 'mean'), ms=('tiempo_ms', 'mean'),
        err=('error_abs', 'median')).sort_values('ev')
    for m, row in r.iterrows():
        lin.append(f"{etiq[conj]} & {NOMBRE.get(m, m)} & {row.exito*100:.0f}\\% & {esp(row.ev)} & "
                   f"{esp(row.it)} & {esp(row.ms,1)} & {sci(row.err)} \\\\")
    lin.append("\\midrule")
lin += ["\\bottomrule", "\\end{longtable}"]
open(f'{TAB}/tabla_apendice.tex', 'w', encoding='utf-8').write("\n".join(lin))

print("tablas generadas")
