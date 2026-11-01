# Métodos numéricos iterativos aplicados en la cotización de rentas vitalicias

*Estructura no suave, convergencia finita y eficiencia computacional en la ecuación de equivalencia actuarial*

Tesis de Maestría en Matemáticas — Pontificia Universidad Javeriana, Facultad de Ciencias, Departamento de Matemáticas.

**Autor:** Eduardo Lagos Durán

**Director:** Vladimir Moreno Gutiérrez

## Resumen

La tesis estudia la cotización de una renta vitalicia inmediata en un modelo particular —el cotizador implementado— que incorpora piso pensional, indexación y auxilio funerario. La mesada inicial *M* se obtiene al resolver *f*(*M*) = VP(*M*) − KA = 0, donde VP es el valor presente actuarial de las obligaciones incluidas y KA el capital objetivo, expresados sobre una misma base de valoración. La formulación no es una representación exhaustiva de la regulación ni de la tarificación comercial de las aseguradoras colombianas.

Bajo las hipótesis del modelo:

- **VP es afín a trozos**, con a lo sumo 333 umbrales candidatos agrupados en tres racimos geométricos alrededor de 1, 5 y 10 salarios mínimos, para la parametrización considerada. Un umbral candidato puede no producir un salto efectivo.
- **Capital mínimo.** La extensión de VP a *M* ≥ 0 es constante en [0, SMLV]. En el dominio admisible *M* ≥ SMLV existe una solución única si y solo si KA ≥ VP(SMLV); en la igualdad, la solución es *M* = SMLV.
- **El auxilio funerario puede destruir la convexidad.**

Se obtiene una expresión cerrada de las derivadas laterales y del *B*-subdiferencial de VP, interpretables como factores marginales de renta actuarial. Newton con la pendiente exacta alcanza la raíz en un paso cuando la clausura del tramo seleccionado contiene también la solución; el número de pasos no se identifica con el de tramos atravesados. Una salvaguarda de encaje con bisección periódica proporciona convergencia global bajo las condiciones establecidas.

El retiro programado se formula mediante el estado acoplado de saldo y mesada anterior. Una cota condicional de propagación del error relaciona la tolerancia anual con un límite de error del saldo final.

## Resultados principales

Se comparan 19 métodos en 25 escenarios: 9 sintéticos, 9 cotizaciones de renta vitalicia y 7 registros adicionales con información de retiro programado, valorados con la función de renta vitalicia. El costo se mide en llamadas medias al motor actuarial, incluidas derivadas y preparación:

| Newton semisuave | Secante | Brent | Newton salvaguardado | Newton (dif. finitas) | Halley | Bisección |
|---|---|---|---|---|---|---|
| 3,08 | 5,08 | 5,28 | 5,52 | 7,60 | 10,16 | 33,40 |

- La razón de llamadas entre bisección y Newton analítico es 10,8, y la derivada analítica reduce las llamadas un 59 % frente a las diferencias finitas.
- **Recomendación para el modelo estudiado:** Newton semisuave con salvaguarda periódica cuando se dispone de la derivada analítica. En las cotizaciones reales, situadas en el tramo afín, requiere 4,78 y 4,71 llamadas medias frente a 5,00 de Brent; en los escenarios sintéticos con raíces en los racimos de quiebres requiere 6,89 frente a 5,78. Cuando no se dispone de derivadas, Brent ofrece una alternativa con encaje y costo similar. La secante es competitiva en costo, pero su versión abierta carece de garantía global.
- Las cifras describen los escenarios y el entorno examinados; no constituyen una clasificación universal de los métodos. Las tablas completas por conjunto de datos, que el documento remite a este repositorio, están en `tex/tablas/tabla_apendice.tex`.

## Relación entre la tesis y el código

La guía [`docs/guia_tesis_codigo.md`](docs/guia_tesis_codigo.md) recorre el documento capítulo por capítulo e indica qué función implementa o comprueba cada resultado, qué script produce cada figura y cada tabla, y de dónde salen las cifras del texto. También explica cómo se cuenta el costo de los métodos y qué resultados cambian cuando se usan las bases ficticias.

## Estructura del repositorio

```
tesis-rentas-vitalicias/
├── tex/                     Documento en LaTeX: tesis.tex, capítulos, figuras y tablas
│   ├── tesis.pdf            Documento compilado
│   └── datos_numericos.tex  Cifras del documento, generadas por código
├── py/
│   ├── cotizador/           Motor actuarial y cotizador en Streamlit
│   │   ├── core/            Motor y aporte de la tesis (ver la tabla de módulos)
│   │   └── ejemplos/        Bases de pólizas ficticias, con la estructura de las reales
│   ├── rutas.py             Rutas del proyecto y elección de la base de pólizas
│   ├── correr_benchmark.py  Banco de pruebas completo
│   ├── fig_01..05_*.py      Figuras del documento
│   └── generar_*.py         Cifras, tablas y listados del documento
├── app/                     Presentación interactiva de la defensa (Streamlit)
├── docs/
│   └── guia_tesis_codigo.md Correspondencia entre la tesis y el código
├── INICIAR.bat              Menú para Windows: instalar, regenerar, compilar y abrir las aplicaciones
├── requirements.txt         Dependencias de Python
└── README.md
```

La carpeta `salidas/` (resultados del banco de pruebas en CSV) se crea al ejecutar los scripts.

### Módulos

| Módulo | Contenido |
|---|---|
| **Motor actuarial** (preexistente, extendido en este trabajo) | |
| `core/config.py` | Parámetros actuariales y constantes normativas |
| `core/mortalidad.py` | Series de mortalidad, mensualización y factores de mejora; fuentes por conciliar |
| `core/motor.py` | Función de valoración VP; **derivadas laterales exactas** (aporte de este trabajo) |
| `core/smith_wilson.py` | Extrapolación de la curva de descuento |
| `core/retiro_programado.py` | Recursión de retiro programado y operadores de ajuste |
| `core/base_masiva.py` | Carga y procesamiento de bases de pólizas |
| **Aporte de esta tesis** | |
| `core/metodos_iterativos.py` | Los 19 métodos con interfaz común e instrumentación |
| `core/problema_tesis.py` | Construcción de *f*, de su *B*-subdiferencial (valor y derivada en una misma llamada al motor) y de los escenarios |
| `core/banco_pruebas.py` | Ejecución del catálogo, con un objetivo y una memoria independientes por método |
| **Generación del documento** | |
| `correr_benchmark.py` | Ejecuta el banco de pruebas completo |
| `fig_01..05_*.py` | Generan las figuras en PDF vectorial |
| `generar_macros_tex.py` | Genera `datos_numericos.tex` |
| `generar_tablas_tex.py` | Genera las tablas de resultados en LaTeX |
| `generar_extractos_codigo.py` | Extrae los listados del código fuente |
| `insertar_notas.py` | Comprueba las notas al pie y sus anclas; solo modifica el texto con la opción `--escribir` |
| `explorar_estructura.py`, `verificar_derivada.py` | Comprobaciones numéricas del capítulo 4: región plana, quiebres, derivadas laterales y no convexidad |
| **Aplicaciones** | |
| `app/` | Presentación de la defensa en Streamlit |
| `py/cotizador/app.py` | Cotizador: renta vitalicia, retiro programado y procesos masivos |

## Cómo reproducir

Se probó con Python 3.13. Dependencias principales: numpy, pandas, scipy, matplotlib, openpyxl, streamlit, altair y plotly.

En Windows, el archivo `INICIAR.bat` instala el entorno y ofrece un menú con todos los pasos. Desde una consola:

```bash
# 1. Entorno de Python
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# 2. Banco de pruebas completo (menos de un minuto)
cd py
python correr_benchmark.py

# 3. Figuras
python fig_01_estructura.py
python fig_02_convergencia.py
python fig_03_actuarial.py
python fig_04_rp_sensibilidad.py
python fig_05_variables.py

# 4. Cifras, tablas y listados del documento
python generar_macros_tex.py
python generar_tablas_tex.py
python generar_extractos_codigo.py

# 5. Documento
cd ../tex
latexmk -pdf tesis.tex

# 6. Presentación interactiva de la defensa
cd ../app
streamlit run presentacion.py

# 7. Cotizador
cd ../py/cotizador
streamlit run app.py
```

Los scripts usan rutas relativas a su propia ubicación, de modo que también pueden ejecutarse desde otra carpeta. El paso 3 debe preceder al 4, porque `generar_macros_tex.py` lee resultados que producen `fig_03_actuarial.py`, `fig_04_rp_sensibilidad.py` y `fig_05_variables.py`.

### Trazabilidad y reproducibilidad

- Las cifras del documento provienen de `tex/datos_numericos.tex` y de las tablas de `tex/tablas/`, generadas a partir de los resultados del banco de pruebas. Si cambian las entradas o el código, deben volver a ejecutarse el banco y los generadores; las figuras y las afirmaciones del texto deben contrastarse también con esas salidas.
- Reproducir una ejecución requiere conservar la revisión del código, los datos, la configuración y las versiones de las dependencias. El enlace al repositorio por sí solo no identifica esa revisión: conviene registrar el *commit* o las sumas de comprobación de los archivos utilizados.
- La simulación del rendimiento de la cuenta individual en retiro programado admite una semilla explícita. Sin ella, la semilla se deriva de un resumen SHA-256 de las entradas serializadas en JSON, estable entre procesos. Para comparar variantes de una misma póliza debe fijarse la misma semilla.
- Los tiempos de ejecución dependen del entorno; el costo comparable entre métodos es el número de llamadas al motor.

## Datos

Las cotizaciones reales usadas en el trabajo provienen de una compañía aseguradora y contienen datos personales, por lo que no se publican. El repositorio incluye, en `py/cotizador/ejemplos/`, dos bases ficticias con la misma estructura: `base_polizas_ejemplo.xlsx` (9 pólizas) y `base_cotizacion_ejemplo.xlsx` (7 registros con información de retiro programado). Sus fechas, identificaciones, nombres y capitales son inventados.

Con las bases ficticias todo el código se ejecuta. Los resultados de los escenarios sintéticos y el análisis de la estructura de la función coinciden con los del documento. Los que dependen de las pólizas no: la tabla de resultados globales, las tablas completas, las figuras 6.1, 7.1, 7.2, 8.1 y 8.2, y las cifras del texto que provienen de ellas. La guía detalla cada caso.

Los pasos 3 y 4 de la sección anterior escriben en `tex/`. Si se ejecutan con las bases ficticias, esos archivos quedan con valores distintos de los del documento; `git checkout -- tex` recupera la versión del documento.

Quien disponga de las bases reales puede copiarlas en una carpeta `datos_privados/` en la raíz del proyecto, con sus nombres originales (`base_polizas_10_polizas.xlsx` y `base_cotizacion_prueba_7_casos.xlsx`). Los scripts y las aplicaciones las usan automáticamente en lugar de las ficticias. Esa carpeta está excluida del control de versiones.

## Notación

| Símbolo | Significado |
|---|---|
| *M* | Mesada pensional inicial |
| KA | Capital objetivo de la cotización |
| VP(*M*) | Valor presente actuarial de las obligaciones para la mesada *M* (reserva matemática) |
| *f*(*M*) | VP(*M*) − KA |
| SMLV, *S*₀ | Salario mínimo legal mensual vigente |

## Licencia

© 2026 Eduardo Lagos Durán. Todos los derechos reservados.
