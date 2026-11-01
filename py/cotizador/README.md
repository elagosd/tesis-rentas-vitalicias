# Cotizador

Aplicación en Streamlit para cotizar rentas vitalicias y retiro programado. Es la herramienta sobre la que se construyó el motor actuarial de la tesis: el módulo `core/motor.py` que usa el banco de pruebas es el mismo que usa esta aplicación.

Dado el capital de una póliza, el cotizador encuentra la mesada inicial que lo agota (ecuación de equivalencia actuarial). También calcula la tasa equivalente a partir de una curva de tasas y proyecta año a año la mesada de renta vitalicia y la de retiro programado.

## Ejecución

Desde la raíz del repositorio, con el entorno instalado (véase el README principal):

```bash
cd py/cotizador
streamlit run app.py
```

En Windows, la opción correspondiente del menú de `INICIAR.bat` hace lo mismo.

## Páginas

| Página | Contenido |
|---|---|
| Parametrización actuarial | Supuestos del cálculo: vector de IPC, inflación esperada, SMLV, deslizamiento, recargos, curva de tasas y método de iteración. Incluye pestañas para cotizar una sola póliza (mesada, tasa equivalente y retiro programado). Pide una clave |
| Masivo: Encontrar mesada | Carga una base de pólizas en Excel y encuentra la mesada de cada una, con gráficos por póliza y estadísticas de la base |
| Masivo: Encontrar tasa equivalente | Versión masiva del cálculo de la tasa equivalente |
| Historial | Consulta y exporta en CSV las parametrizaciones guardadas, los cálculos realizados y las proyecciones por año |

Para probar las páginas masivas pueden usarse las bases ficticias de `ejemplos/`: `base_polizas_ejemplo.xlsx` y `base_cotizacion_ejemplo.xlsx`. Sus datos son inventados.

## Clave de la parametrización

La página de parametrización pide una clave para evitar cambios accidentales en los supuestos. Es un control sencillo, una clave compartida sin usuarios individuales, y no un mecanismo de seguridad.

La clave se define en `.streamlit/secrets.toml`, a partir de la plantilla `.streamlit/secrets.toml.ejemplo`:

```toml
actuario_password = "la-clave-elegida"
```

Si ese archivo no existe, se usa la clave por defecto de `core/auth.py` y la aplicación muestra una advertencia. El archivo `secrets.toml` está excluido del control de versiones.

## Persistencia

Las parametrizaciones, los cálculos y las proyecciones se guardan en `data/historial.db` (SQLite), que se crea la primera vez que se guarda algo. Cada parametrización guardada se agrega como una versión nueva y la aplicación carga la última al iniciar. Ese archivo tampoco se publica: contiene los datos de las pólizas que se hayan cargado.

## Módulos de `core/`

| Módulo | Contenido |
|---|---|
| `config.py` | Constantes y parámetros actuariales (`ParametrosActuariales`) |
| `motor.py` | Reserva matemática, flujos, duración de Macaulay y derivadas laterales exactas |
| `mortalidad.py` | Tablas de mortalidad, mensualización y factores de mejora |
| `smith_wilson.py` | Curva de descuento de Smith-Wilson, usada en retiro programado |
| `retiro_programado.py` | Mesada de retiro programado y proyección anual del saldo de la cuenta individual |
| `tasa_equivalente.py` | Tasa equivalente y mesada a partir de una curva de tasas |
| `encontrar_mesada_individual.py` | Búsqueda de la mesada de una póliza |
| `metodos_numericos.py` | Bisección, Newton y secante acotados que usa la aplicación |
| `base_masiva.py`, `mapeo_base.py` | Lectura de bases de pólizas y traducción de sus códigos |
| `paralelo.py` | Ejecución de las corridas masivas en varios procesos |
| `proyecciones_masivo.py` | Proyecciones de renta vitalicia y retiro programado para toda una base |
| `persistencia.py` | Historial en SQLite |
| `estado.py`, `formularios.py`, `auth.py` | Parámetros de la sesión, formularios reutilizables y clave de acceso |
| `comparador_escenarios_rp.py` | Comparación de variantes de retiro programado |
| `metodos_iterativos.py`, `problema_tesis.py`, `banco_pruebas.py` | Módulos de la tesis: los 19 métodos, la función objetivo con su *B*-subdiferencial y el banco de pruebas |

La carpeta `data/` contiene las tablas de mortalidad, el sobrecosto de mortalidad de retiro programado y las tablas del beneficiario hipotético, en CSV.

## Relación con la tesis

El capítulo 3 de la tesis describe el modelo que implementa `motor.py`; el capítulo 4 estudia la estructura de la función de valoración y el capítulo 5 compara los métodos para resolver la ecuación de cotización. Las recomendaciones de la tabla 8.3 se refieren a esta implementación. La correspondencia detallada está en `docs/guia_tesis_codigo.md`, en la raíz del repositorio.
