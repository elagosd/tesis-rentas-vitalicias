# Guía: de la tesis al código

Esta guía acompaña la lectura del documento (`tex/tesis.pdf`). Para cada capítulo indica qué parte del código implementa o comprueba sus resultados, qué script produce cada figura y cada tabla, y de dónde salen las cifras que aparecen en el texto. La numeración de capítulos, resultados, figuras y tablas es la de la versión compilada que está en el repositorio.

Las rutas de los módulos del motor se escriben como `core/...`; todos están en `py/cotizador/core/`. Los scripts de `py/` se ejecutan desde esa carpeta.

## 1. Recorrido general

El problema de la tesis es encontrar la mesada inicial *M* que resuelve

*f*(*M*) = VP(*M*) − KA = 0,

donde VP(*M*) es el valor presente actuarial de las obligaciones (la reserva matemática) y KA es el capital de la cotización. En el código, ese recorrido tiene cuatro capas:

```
core/motor.py              VP(M) y sus derivadas laterales exactas
      │
core/problema_tesis.py     f(M) = VP(M) − KA, B-subdiferencial y escenarios
      │
core/metodos_iterativos.py los 19 métodos, con interfaz e instrumentación comunes
      │
core/banco_pruebas.py      ejecución del catálogo sobre cada escenario
      │
correr_benchmark.py  ──►  salidas/*.csv
      │
fig_01..05_*.py, generar_macros_tex.py, generar_tablas_tex.py
      │
tex/figuras/, tex/tablas/, tex/datos_numericos.tex, tex/datos_variables.tex  ──►  tex/tesis.pdf
```

El motor actuarial existía antes de este trabajo como herramienta de cotización. La tesis lo extiende con el cálculo exacto de las derivadas laterales y construye encima todo lo demás: la función objetivo, los métodos, el banco de pruebas y la generación del documento.

## 2. Capítulo por capítulo

### Capítulo 1. Introducción

No tiene código asociado. El enlace al repositorio que aparece en el texto se define una sola vez, en `tex/preambulo.tex` (comando `\repositorio`).

### Capítulo 2. Preliminares matemáticos

Es un capítulo teórico, pero tres de sus resultados se usan de forma directa en el código:

| Resultado | Dónde se usa |
|---|---|
| Teorema 2.19 (Qi–Sun, Newton semisuave) | `newton_semisuave` en `core/metodos_iterativos.py` |
| Teorema 2.23 (cota del error de la bisección) | `biseccion`: cuando el método se detiene por el ancho del intervalo y no por el residuo, informa la cota (*b* − *a*)/2 en el campo `cota_error` |
| Sección 2.3 (orden de convergencia) | `ORDEN_TEORICO` (orden teórico de cada método) y `ResultadoIteracion.estimar_orden` (estimación empírica) |

### Capítulo 3. El modelo actuarial de la renta vitalicia inmediata

Todo el capítulo corresponde al motor actuarial:

| Sección | Código |
|---|---|
| 3.1 El contrato y sus coberturas | `calcular_reserva` en `core/motor.py` (renta y auxilio funerario) y `core/config.py` (parámetros actuariales, SMLV, recargos y constantes normativas) |
| 3.2 Discretización y horizonte | `core/motor.py`: `_generar_calendario` (calendario mensual) y `_tabla_pagos` (13 o 14 mesadas al año) |
| 3.3 Proyección de la mesada | `_factor_ipc_acumulado` (factor de indexación, definición 3.2) y el piso del salario mínimo dentro de `calcular_reserva` |
| 3.4 Contingencia multivida | `_tabla_persona` y `core/mortalidad.py` (series de mortalidad, mensualización y factores de mejora) |
| 3.5 Descuento financiero | `_tasas_forward_mensuales` en `core/motor.py` |
| 3.6–3.8 Función de valoración, descomposición y forma canónica | `calcular_reserva`, que devuelve la reserva matemática VP(*M*) |

Las figuras 3.1 a 3.3 las produce `fig_03_actuarial.py`. El mismo script genera dos figuras auxiliares que no se incluyen en el documento (`fig_tablas_mortalidad.pdf` y `fig_fuerza_mortalidad.pdf`) y guarda el ajuste de Gompertz que usa `generar_macros_tex.py`.

### Capítulo 4. Estructura de la ecuación de cotización

Es el núcleo analítico de la tesis. Cada resultado tiene una contraparte en el código o una comprobación numérica:

| Resultado | Código |
|---|---|
| Teorema 4.3 (región plana) y corolario 4.5 (capital mínimo) | `capital_minimo` en `core/problema_tesis.py` calcula KA<sub>min</sub> = VP(SMLV). `explorar_estructura.py` comprueba que VP es constante por debajo del SMLV |
| Teorema 4.9 (puntos de quiebre) y corolario 4.10 (región afín) | `detectar_quiebres` localiza los quiebres por los saltos de la derivada lateral derecha. La exactitud de la región afín se comprueba en `verificar_derivada.py` |
| Teorema 4.13 (no convexidad) | Último bloque de `verificar_derivada.py`: la pendiente decrece después del racimo III |
| Teorema 4.15 (subdiferencial) y ecuaciones (4.3)–(4.4) | `calcular_reserva(..., calcular_derivada=True)` devuelve `derivada_rm_der` y `derivada_rm_izq`, las dos derivadas laterales exactas |
| Teoremas 4.16 y 4.18 (existencia y condicionamiento) | Las cifras de condicionamiento del texto las calcula `generar_macros_tex.py` |
| Teoremas 4.19 y 4.20, corolario 4.21 (semisuavidad y BD-regularidad) | Son la justificación teórica de `newton_semisuave` |
| Proposición 4.23 (continuidad de la rama) | Corrección en `calcular_reserva`: en *M* = SMLV la derivada se calcula sobre la rama del IPC (variable `tasa_derivada`) |

La derivada exacta reúne tres ingredientes, descritos en la sección B.3 del apéndice: la máscara de actividad del piso, la banda del auxilio funerario y la corrección de la rama en *M* = SMLV. En el código son, respectivamente, `activo_renta_der`/`activo_renta_izq`, `banda_der`/`banda_izq` y `tasa_derivada`.

La sección 4.10 (verificación numérica) se reproduce con dos scripts que solo imprimen resultados:

- `explorar_estructura.py`: región plana y pendiente numérica entre 0,5 y 11 salarios mínimos, donde se ven los tres racimos.
- `verificar_derivada.py`: comparación de la derivada exacta con diferencias centradas, exactitud de la región afín y no convexidad.

Las figuras 4.1 a 4.3 las produce `fig_01_estructura.py`; la figura 4.4, `fig_02_convergencia.py`. La tabla 4.1 está escrita en el texto, con algunas cifras tomadas de `datos_numericos.tex`.

### Capítulo 5. Métodos numéricos iterativos

Los 19 métodos están en `core/metodos_iterativos.py`, todos con la misma interfaz: reciben la función y su intervalo o punto inicial, y devuelven un `ResultadoIteracion` con la raíz, el estado, las iteraciones, las llamadas al motor y el historial de iterados.

| Familia | Funciones |
|---|---|
| Con encaje | `biseccion` (algoritmo 1), `regula_falsi`, `illinois`, `pegasus`, `anderson_bjorck`, `ridders`, `brent`, `itp` |
| Abiertos | `secante`, `newton_diferencias`, `newton_analitico`, `steffensen`, `steffensen_escalado`, `muller`, `halley`, `punto_fijo`, `aitken_steffensen` |
| Para el caso no suave | `newton_semisuave` y `newton_salvaguardado` (algoritmo 2) |

Las variantes de regula falsi comparten una misma implementación, `_regula_falsi_generico`.

Correspondencia con los resultados del capítulo:

| Resultado | Código |
|---|---|
| Criterio de parada (sección 5.1.2) | `CriterioParada`: la solución se certifica por el residuo; el paso pequeño solo sirve como diagnóstico |
| Proposición 5.4 (estancamiento de regula falsi) | `regula_falsi` conserva un extremo del encaje; `illinois`, `pegasus` y `anderson_bjorck` reducen el valor de ese extremo para evitarlo |
| Teorema 5.7 y proposición 5.8 (secante) | `secante` |
| Proposición 5.9 (sesgo de las diferencias finitas) | `newton_diferencias`, con paso *h* = 1 peso |
| Teorema 5.10 y corolario 5.11 (terminación finita, un paso) | `newton_semisuave` |
| Teorema 5.12 (Newton salvaguardado) | `newton_salvaguardado`: a lo sumo dos propuestas de Newton seguidas; la tercera es el punto medio del intervalo |

La instrumentación común está al comienzo del módulo: `ContadorFuncion` cuenta las llamadas, `Iterado` registra cada paso y `_finalizar` asigna el estado final («certificado por residuo», «certificado por encaje», «estancamiento» o «sin convergencia»). Un método abierto termina en «estancamiento» cuando su paso cae por debajo de la tolerancia sin que se cumpla el residuo.

La tabla 5.2 (terminación finita sobre el escenario A-R3) se reproduce con `newton_semisuave` desde los diez puntos de arranque de la tabla. La sección 7 de la presentación interactiva hace ese mismo cálculo. Las tablas 5.1 y 5.3 están escritas en el texto.

### Capítulo 6. Evaluación de las variables del modelo

| Contenido | Código |
|---|---|
| Efecto de las hipótesis demográficas (sección 6.1) | `fig_05_variables.py`, que escribe sus cifras en `tex/datos_variables.tex` |
| Sensibilidad a las variables financieras y regulatorias (sección 6.2) | `fig_04_rp_sensibilidad.py` guarda `salidas/sensibilidad.csv` y `salidas/sensibilidad_smlv.csv`; `generar_macros_tex.py` pasa esas cifras al texto |
| Tres componentes que requieren revisión (sección 6.3) | La curva Smith-Wilson (`core/smith_wilson.py`), la volatilidad de la cuenta individual (`proyectar_rp_dinamico_cai`) y el factor de ajuste NI (`resolver_mesada_rp`) |
| Contraste con cotizaciones de referencia (sección 6.4, figura 6.1) | `fig_05_variables.py` |

La tabla 6.1 está escrita en el texto, con cifras tomadas de los archivos de macros. Las figuras `fig_sensibilidad.pdf` y `fig_efecto_demografico.pdf` se generan como apoyo, pero no se incluyen en el documento.

### Capítulo 7. Extensión al retiro programado

Corresponde a `core/retiro_programado.py`:

| Resultado | Código |
|---|---|
| Definición 7.1 (sistema de retiro programado) | `proyectar_rp_dinamico_cai`: recursión anual sobre el estado acoplado de saldo y mesada anterior |
| Mesada de cada año | `resolver_mesada_rp`, que usa el saldo de la cuenta como capital objetivo |
| Operadores de ajuste (sección 7.1.2) | Dentro de `proyectar_rp_dinamico_cai`: piso de crecimiento, piso del mínimo proyectado, techo comercial (desactivado por defecto) y límite de caída |
| Curva de descuento | `core/smith_wilson.py` |
| Semilla de la simulación (apéndice B.4) | `semilla_estable` |

La proposición 7.3, el teorema 7.5 y el corolario 7.8 se ilustran con la figura 7.1, que perturba el capital inicial y sigue el error de la mesada y del saldo a lo largo de la recursión. Esa figura y la 7.2 las produce `fig_04_rp_sensibilidad.py`.

### Capítulo 8. Experimentos numéricos

El banco de pruebas completo se ejecuta con `correr_benchmark.py`:

1. Construye los escenarios. `escenarios_estandar` define los 9 sintéticos: cuatro perfiles demográficos (A a D) combinados con regiones objetivo R2 a R5, con mesadas objetivo que son múltiplos irracionales del SMLV (véase la observación sobre la elección de los objetivos). `escenarios_reales` lee las 9 cotizaciones de renta vitalicia y los 7 registros adicionales.
2. Ejecuta los 19 métodos sobre cada escenario con `tabla_resultados` y `ejecutar_catalogo`, con la tolerancia de producción (1 peso de capital) y, para los sintéticos, también con una tolerancia estricta.
3. Guarda en `salidas/` la tabla larga (`tabla_larga.csv`), los resúmenes por método (`resumen_*.csv`) y los metadatos de la ejecución (`meta_benchmark.json`).

| Elemento | Script | Fuente |
|---|---|---|
| Tabla 8.1 (resultados globales) | `generar_tablas_tex.py` → `tex/tablas/tabla_global.tex` | `resumen_global.csv` |
| Tabla 8.2 (resultados por región) | `generar_tablas_tex.py` → `tex/tablas/tabla_region.tex` | escenarios sintéticos de `tabla_larga.csv` |
| Tablas completas por conjunto de datos | `generar_tablas_tex.py` → `tex/tablas/tabla_apendice.tex` | `tabla_larga.csv` |
| Figuras 8.1 a 8.4 y 8.6 | `fig_02_convergencia.py` | |
| Figura 8.5 (robustez frente al punto inicial) | `fig_04_rp_sensibilidad.py` | |

Las tablas completas por conjunto de datos no se incluyen en el documento, que las remite al repositorio. La tabla 8.3 (correcciones y recomendaciones) está escrita en el texto. Sus filas tienen esta contraparte en el código:

- R2, corrección de la derivada en *M* = SMLV: `calcular_reserva` en `core/motor.py`.
- R3, certificado del error: `CriterioParada`, `cota_error` y la columna `estado` del banco.
- Cálculo conjunto de valor y derivada: `ObjetivoActuarial` en `core/problema_tesis.py`.

### Capítulo 9 y apéndices

El capítulo 9 no tiene código propio. El apéndice A es la notación y el apéndice B describe la implementación y la reproducibilidad. Los archivos `tex/cap/B_tablas.tex` y `tex/cap/D_codigo.tex` corresponden a dos apéndices que se dejaron fuera del documento (tablas completas y listados de código) y que remiten a este repositorio. Los listados que usaba el segundo están en `tex/codigo/`; los extrae `generar_extractos_codigo.py` directamente del código fuente.

## 3. Figuras del documento

| Figura | Archivo en `tex/figuras/` | Script | Depende de las bases de pólizas |
|---|---|---|---|
| 3.1 | `fig_supervivencia.pdf` | `fig_03_actuarial.py` | No |
| 3.2 | `fig_descuento.pdf` | `fig_03_actuarial.py` | No |
| 3.3 | `fig_flujos.pdf` | `fig_03_actuarial.py` | No |
| 4.1 | `fig_region_plana.pdf` | `fig_01_estructura.py` | No |
| 4.2 | `fig_estructura_vp.pdf` | `fig_01_estructura.py` | No |
| 4.3 | `fig_zoom_quiebres.pdf` | `fig_01_estructura.py` | No |
| 4.4 | `fig_residuo_lineal.pdf` | `fig_02_convergencia.py` | No |
| 6.1 | `fig_validacion.pdf` | `fig_05_variables.py` | Sí |
| 7.1 | `fig_propagacion_error_rp.pdf` | `fig_04_rp_sensibilidad.py` | Sí |
| 7.2 | `fig_rp_vs_rv.pdf` | `fig_04_rp_sensibilidad.py` | Sí |
| 8.1 | `fig_barras_evaluaciones.pdf` | `fig_02_convergencia.py` | Sí (resumen de los 25 escenarios) |
| 8.2 | `fig_orden_empirico.pdf` | `fig_02_convergencia.py` | Sí (resumen de los 25 escenarios) |
| 8.3 | `fig_convergencia_residuos.pdf` | `fig_02_convergencia.py` | No |
| 8.4 | `fig_trayectorias.pdf` | `fig_02_convergencia.py` | No |
| 8.5 | `fig_robustez_inicial.pdf` | `fig_04_rp_sensibilidad.py` | No |
| 8.6 | `fig_costo_tolerancia.pdf` | `fig_02_convergencia.py` | No |

Todas las figuras se guardan en PDF vectorial con el estilo común de `estilo_figuras.py`.

## 4. Las cifras del texto

Las magnitudes que dependen del cálculo no se escriben a mano en el texto: se toman de dos archivos de macros.

- `tex/datos_numericos.tex`, generado por `generar_macros_tex.py`. Reúne el SMLV, el capital mínimo, las pendientes de los tramos, el ancho de los racimos, el número de quiebres, el condicionamiento, las llamadas medias de cada método, las razones de costo, las cifras de sensibilidad y los tamaños de los conjuntos de datos. Lee `salidas/resumen_global.csv`, `salidas/meta_benchmark.json`, los dos archivos de sensibilidad y el ajuste de Gompertz, y calcula directamente con el motor las cifras de la estructura de VP.
- `tex/datos_variables.tex`, generado por `fig_05_variables.py`, con las cifras del capítulo 6.

Por eso el orden de ejecución importa: primero el banco de pruebas, después las figuras y al final los generadores (véase el README).

## 5. Cómo se mide el costo

El costo que se compara entre métodos es el número de llamadas al motor actuarial, no el tiempo. Lo lleva `ObjetivoActuarial` (`core/problema_tesis.py`):

- Cada método recibe un objetivo propio, con su propia memoria de evaluaciones, de modo que ningún método aprovecha las evaluaciones de otro.
- Cuando un método necesita la derivada analítica, el objetivo obtiene valor y derivadas en una misma llamada al motor (`derivada_conjunta=True`). Si después se pide la derivada en el mismo punto, se toma de la memoria.
- Las diferencias finitas pagan sus valoraciones auxiliares.
- El conteo incluye la preparación, por ejemplo la derivada inicial que usan punto fijo, Aitken y Steffensen escalado para fijar su escala.

El banco registra, para cada método y escenario, las llamadas totales, las que solo pidieron valor, las que incluyeron derivada, el estado final y el tiempo (`tabla_resultados` en `core/banco_pruebas.py`).

## 6. Datos

Las bases reales provienen de una compañía aseguradora y contienen datos personales, por lo que no se publican. El repositorio trae dos bases ficticias con la misma estructura en `py/cotizador/ejemplos/`, y `py/rutas.py` decide cuál se usa: si existe la carpeta `datos_privados/` con las bases reales, toma esas; si no, las ficticias.

Con las bases ficticias:

- Coinciden con el documento todos los resultados de los escenarios sintéticos y de la estructura de VP: capítulos 3 y 4, tabla 5.2, tabla 8.2 y las figuras marcadas con «No» en la tabla de la sección 3.
- No coinciden los resultados que dependen de las pólizas: la tabla 8.1, las tablas completas, las figuras marcadas con «Sí» y las cifras del texto que provienen de ellas.

Los pasos 3 y 4 del README escriben en `tex/`. Si se ejecutan con las bases ficticias, esos archivos quedan con valores distintos de los del documento. Para volver a la versión del documento basta con:

```bash
git checkout -- tex
```

## 7. Las aplicaciones

**Presentación de la defensa** (`app/presentacion.py`). Recorre la tesis en doce secciones y calcula en vivo con el mismo motor y los mismos métodos del repositorio:

| Sección | Capítulo |
|---|---|
| 1. El problema | 1 y 3 |
| 2. Anatomía de la función | 4 (estructura y quiebres) |
| 3. ¿Cuándo hay solución? | 4 (región plana, capital mínimo y existencia) |
| 4. La derivada es el factor de renta | 4 (subdiferencial) |
| 5. Los métodos, uno a uno | 5 |
| 6. La carrera | 8 (comparación de costo) |
| 7. Terminación finita | 5 (teorema 5.10 y tabla 5.2) |
| 8. Laboratorio de sensibilidad | 6 |
| 9. Renta vitalicia vs. retiro programado | 7 |
| 10. Las variables del modelo | 6 |
| 11. Del teorema a producción | 8 (tabla 8.3, correcciones y recomendaciones) |
| 12. Conclusiones y trabajo futuro | 9 |

**Cotizador** (`py/cotizador/app.py`). Es la herramienta sobre la que se construyó el motor: cotiza una póliza o una base completa, calcula la tasa equivalente y proyecta el retiro programado. Su funcionamiento se describe en `py/cotizador/README.md`.
