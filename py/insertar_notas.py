# -*- coding: utf-8 -*-
"""
Inserta las notas al pie del documento.

Se hace con un script y no a mano por dos razones: para poder verificar que
cada ancla exista realmente en el texto (un `\\footnote` colocado sobre una
frase que ya cambió es un error silencioso), y para dejar constancia de qué
nota corresponde a qué afirmación.

Las notas se insertaron sobre una versión anterior del texto y después se
revisaron a mano: algunas se reescribieron y otras se retiraron. La
referencia es el texto vigente de `tex/cap/`.

Por defecto el script solo comprueba: informa cuántas notas están en el
texto, cuáles se insertarían y qué anclas ya no aparecen, sin modificar
ningún archivo. Para escribir los cambios hay que ejecutarlo con la opción
`--escribir`. Una nota que ya está en el texto nunca se duplica.
"""

import sys
from pathlib import Path

CAP = Path(__file__).resolve().parent.parent / "tex" / "cap"

# (archivo, ancla exacta, texto de la nota)
NOTAS = [

    # =================================================================
    # Capítulo 1 — Introducción
    # =================================================================
    ("01_introduccion.tex",
     "convenciones bien establecidas",
     None),  # marcador de comprobación; se ignora si es None

    ("01_introduccion.tex",
     "el capital acumulado durante su vida laboral a cambio del derecho a\nrecibir un pago periódico mientras él o sus beneficiarios conserven ese derecho",
     "El capital acumulado se compone del saldo de la cuenta de ahorro individual, "
     "del bono pensional cuando sea aplicable y de los aportes adicionales necesarios "
     "para garantizar el monto mínimo de pensión. En la terminología del contrato de "
     "seguro constituye la prima única."),

    ("01_introduccion.tex",
     "un horizonte de\n\\datoNMeses{} periodos mensuales",
     "El horizonte no es arbitrario: corresponde a la edad límite de las tablas de "
     "mortalidad vigentes. Su carácter finito es lo que hace que todas las sumas del "
     "modelo converjan trivialmente y que el conjunto de puntos de quiebre de la "
     "\\cref{cap:estructura} sea finito y contable."),

    ("01_introduccion.tex",
     "cuesta aproximadamente\n\\datoMsEvaluacion{} milisegundos",
     "Medido sobre la implementación en Python descrita en el \\cref{ap:software}, "
     "con la proyección vectorizada mediante \\texttt{numpy}. La cifra es el promedio "
     "de treinta evaluaciones consecutivas sobre la póliza de referencia. Una "
     "implementación en lenguaje compilado sería más rápida en términos absolutos, "
     "pero la conclusión relativa --- que el costo de la evaluación domina por completo "
     "al del método --- no cambiaría."),

    ("01_introduccion.tex",
     "la mesada inicial \\emph{y} equivocada en la cifra que\nefectivamente se paga al pensionado durante décadas",
     "Con una duración media del contrato del orden de veinte años y trece mesadas "
     "anuales, un error de un peso en la mesada inicial se traduce en varios cientos "
     "de pesos de valor presente. La magnitud es despreciable en términos "
     "financieros; lo que no es despreciable es que el error no sea \\emph{acotable} "
     "a partir del criterio de parada empleado."),

    ("01_introduccion.tex",
     "invocando el teorema del valor intermedio y la monotonía estricta",
     "Véanse, por ejemplo, \\citet[cap.~4--5]{bowers1997} y \\citet[cap.~4]{dickson2020}. "
     "El argumento es correcto para el modelo clásico sin garantías mínimas, donde la "
     "función de valoración es lineal en el beneficio; deja de serlo en cuanto la "
     "regulación introduce un piso legal."),

    ("01_introduccion.tex",
     "algunos desde el siglo\nXVII",
     "El método de Newton aparece en su forma moderna en el \\emph{Analysis per "
     "aequationes numero terminorum infinitas} (1669, publicado en 1711) y en la "
     "\\emph{Analysis aequationum universalis} de Joseph Raphson (1690); la forma "
     "iterativa que hoy se enseña se debe a Thomas Simpson (1740). El método de Halley "
     "data de 1694."),

    ("01_introduccion.tex",
     "la teoría de convergencia de métodos\niterativos, teoría de la medida para el intercambio esperanza-suma",
     "El intercambio entre la esperanza matemática y la suma de flujos, que la "
     "literatura actuarial suele dar por descontado, requiere el teorema de Tonelli "
     "o el de Fubini según el caso; se enuncia y demuestra como \\cref{thm:tonelli}."),

    # =================================================================
    # Capítulo 2 — Preliminares
    # =================================================================
    ("02_preliminares.tex",
     "la propiedad de falta de memoria\ncondicional que define el modelo de tabla de mortalidad",
     "Esta propiedad --- que la distribución del tiempo residual de vida de un individuo "
     "de edad $x$ que ha sobrevivido $t$ años coincide con la de un individuo de edad "
     "$x+t$ --- es constitutiva del modelo de tabla de mortalidad, no una hipótesis "
     "adicional: es lo que permite tabular la mortalidad por edad alcanzada y no por "
     "cohorte. Los modelos de cohorte, que sí distinguen ambas cosas, requieren "
     "abandonarla; véase \\citet{pitacco2009}."),

    ("02_preliminares.tex",
     "sobre una malla mensual",
     "La mensualización de una tabla anual exige una hipótesis sobre la distribución de "
     "los fallecimientos dentro del año. El modelo implementado adopta la de "
     "\\emph{fallecimientos uniformemente distribuidos}, que conduce a la expresión "
     "$q^{(t)}_{x}=(q_x/12)/(1-s\\,q_x)$ con $s$ la fracción de año transcurrida. Es la "
     "convención estándar; véase \\citet[cap.~3]{dickson2020}."),

    ("02_preliminares.tex",
     "lo que se hace en la\n\\cref{sec:var-demograficas}",
     "El contraste no es un ejercicio ocioso. Una tabla regulatoria es un acto "
     "administrativo, y verificar que además se comporta como un objeto estadístico "
     "razonable --- que su fuerza de mortalidad es monótona y sigue una ley conocida --- "
     "es parte de la evaluación crítica que exige el \\cref{cap:variables}."),

    ("02_preliminares.tex",
     "el llamado \\emph{efecto de duelo}",
     "El fenómeno está documentado desde los trabajos demográficos de los años setenta y "
     "se ha incorporado a la valoración actuarial mediante cópulas; la referencia "
     "clásica en el ámbito de las anualidades es \\citet{frees1996}, que estima que "
     "ignorar la dependencia sobrevalora las anualidades conjuntas en torno al cinco por "
     "ciento."),

    ("02_preliminares.tex",
     "el teorema de Tonelli aplicado a la medida producto",
     "Véase \\citet[cap.~18]{billingsley1995}. La versión de Tonelli no exige "
     "integrabilidad, solo no negatividad, que es la hipótesis natural aquí: ni las "
     "mesadas ni el auxilio funerario pueden ser negativos."),

    ("02_preliminares.tex",
     "el teorema de Rademacher",
     "Toda función localmente Lipschitz sobre $\\R^n$ es diferenciable en casi todo "
     "punto respecto de la medida de Lebesgue. Es el resultado que permite definir el "
     "$B$-subdiferencial como conjunto de límites de gradientes: sin él, el conjunto "
     "podría ser vacío."),

    ("02_preliminares.tex",
     "puede no\ncorresponder a ninguna dirección de la gráfica",
     "En dimensión uno la distinción es sutil pero real: si $f$ tiene pendientes $s^-$ y "
     "$s^+$ a los lados de un quiebre, $\\dB f=\\{s^-,s^+\\}$ mientras que $\\dC f$ es "
     "todo el segmento entre ambas. Un método que use el punto medio de ese segmento "
     "--- que es exactamente lo que devuelve una diferencia centrada, según la "
     "\\cref{prop:sesgo-diferencias} --- está usando una pendiente que la función no "
     "realiza en ninguna dirección."),

    ("02_preliminares.tex",
     "El estimador clásico\n$\\hat p_k=\\ln(e_{k+1}/e_k)\\big/\\ln(e_k/e_{k-1})$",
     "Aparece con esta forma en \\citet[cap.~2]{burden2016} y en la mayoría de los "
     "textos introductorios. Su fragilidad es conocida pero rara vez señalada: presupone "
     "que la sucesión de errores es monótona y que se dispone de suficientes términos "
     "por encima del ruido de redondeo, dos condiciones que este problema viola "
     "sistemáticamente."),

    ("02_preliminares.tex",
     "por encima del ruido de redondeo",
     None),

    # =================================================================
    # Capítulo 3 — El modelo
    # =================================================================
    ("03_modelo.tex",
     "se obliga a pagar una renta periódica al pensionado y, tras su fallecimiento, a los\nbeneficiarios con derecho reconocido, mientras subsista ese derecho",
     "Definición conforme al artículo 80 de la Ley 100 de 1993, que caracteriza la renta "
     "vitalicia inmediata como la modalidad en que el afiliado contrata directamente con "
     "la aseguradora el pago de una renta mensual hasta su fallecimiento y el pago de "
     "pensiones de sobrevivientes en favor de sus beneficiarios por el tiempo a que ellos "
     "tengan derecho."),

    ("03_modelo.tex",
     "\\textbf{Auxilio funerario.} Un pago único al fallecimiento del causante",
     "Artículo 51 de la Ley 100 de 1993. La persona que compruebe haber sufragado los "
     "gastos de entierro de un afiliado o pensionado tiene derecho a un auxilio "
     "equivalente al último salario base de cotización o a la última mesada pensional, "
     "sin que pueda ser inferior a cinco ni superior a diez salarios mínimos legales "
     "mensuales vigentes."),

    ("03_modelo.tex",
     "La \\emph{vigencia general} de la póliza se define por",
     "El corte responde a que la edad alcanzada excede el límite de la tabla de "
     "mortalidad, no a una decisión de modelación: a partir de ese punto la probabilidad "
     "de supervivencia es nula por construcción de la tabla y los términos "
     "correspondientes no aportan nada a la suma."),

    ("03_modelo.tex",
     "el primer año se toma la inflación observada o proyectada de corto plazo, el segundo la de\nla encuesta de expectativas, y a partir del tercero la meta de largo plazo del\nbanco central",
     "La meta de inflación de largo plazo del Banco de la República de Colombia es del "
     "tres por ciento anual, con un rango de tolerancia de un punto porcentual. Las "
     "expectativas de corto y mediano plazo se toman de la encuesta mensual de "
     "expectativas de analistas económicos que publica el propio banco."),

    ("03_modelo.tex",
     "responde a la política de aumentos reales del\nsalario mínimo",
     "En Colombia el reajuste anual del salario mínimo se negocia en la Comisión "
     "Permanente de Concertación de Políticas Salariales y Laborales y, a falta de "
     "acuerdo, lo fija el Gobierno por decreto. Históricamente ha superado a la "
     "inflación, de modo que el deslizamiento es positivo. Su magnitud concreta es, "
     "como se verá en el \\cref{thm:quiebres}, el parámetro que determina la anchura de "
     "los racimos de puntos de quiebre."),

    ("03_modelo.tex",
     "La normativa garantiza que ninguna mesada sea inferior al salario mínimo",
     "Artículo 35 de la Ley 100 de 1993: el monto mensual de la pensión mínima de vejez "
     "o jubilación no podrá ser inferior al valor del salario mínimo legal mensual "
     "vigente. La indexación anual de las mesadas por la variación del índice de precios "
     "al consumidor está establecida en el artículo 14 de la misma ley."),

    ("03_modelo.tex",
     "Los sistemas pensionales colombianos pagan $13$ o $14$ mesadas anuales según el\nrégimen",
     "La mesada catorce fue suprimida para las pensiones causadas a partir del 31 de "
     "julio de 2011 por el Acto Legislativo 01 de 2005, con excepción de quienes se "
     "pensionaran antes de esa fecha con una mesada inferior a tres salarios mínimos. "
     "Ambos regímenes coexisten, por lo que el modelo debe soportar los dos."),

    ("03_modelo.tex",
     "que recoge el efecto de selección adversa del colectivo asegurado frente a la\n        población general",
     "El fenómeno se conoce en la literatura como \\emph{annuity puzzle} o "
     "autoselección del rentista: quien contrata una renta vitalicia tiende a tener "
     "mejor expectativa de vida que el promedio poblacional, porque quien se sabe "
     "enfermo prefiere modalidades con devolución de saldos. La magnitud concreta de los "
     "factores empleados se discute críticamente en la \\cref{sec:var-demograficas}."),

    ("03_modelo.tex",
     "vitalicia para hijos inválidos, y hasta $20$ años para cónyuges\n        temporales",
     "Artículo 74 de la Ley 100 de 1993 y sus modificaciones. El cónyuge o compañero "
     "permanente menor de treinta años sin hijos con el causante recibe la pensión de "
     "sobrevivientes de forma temporal, por veinte años; los hijos conservan el derecho "
     "hasta los dieciocho años, o hasta los veinticinco si acreditan escolaridad, o de "
     "forma vitalicia si son inválidos."),

    ("03_modelo.tex",
     "la tasa \\emph{forward} anual real obtenida de la curva\n\\emph{spot}",
     "La relación telescópica entre tasas \\emph{spot} y \\emph{forward} es una "
     "identidad de no arbitraje, no una hipótesis de modelación: expresa que invertir a "
     "$t$ años debe rendir lo mismo que invertir a $t-1$ años y reinvertir un año más al "
     "tipo pactado hoy para ese periodo."),

    ("03_modelo.tex",
     "La forma $B/(1-g)$ --- y no $B(1+g)$ ---",
     "La diferencia no es cosmética. Con un recargo del cinco por ciento, "
     "$1/(1-0{,}05)=1{,}0526$ frente a $1{,}05$: medio punto porcentual de reserva. "
     "Sobre una cartera de miles de pólizas la distinción es material, y es una fuente "
     "habitual de discrepancia entre implementaciones."),

    # =================================================================
    # Capítulo 4 — Estructura
    # =================================================================
    ("04_estructura.tex",
     "donde el borrador original de este trabajo introducía hipótesis innecesarias",
     "El borrador enunciaba un lema de convergencia absoluta de la serie que define el "
     "valor presente, con hipótesis de sumabilidad sobre los factores de descuento. "
     "Sobre una suma finita esas hipótesis son vacuas. Se conservan aquí, en cambio, las "
     "consecuencias: continuidad y carácter Lipschitz, que sí se usan."),

    ("04_estructura.tex",
     "el costo del contrato deja de depender de la mesada nominal\ncontratada",
     "Dicho de otro modo: por debajo del salario mínimo, la mesada contratada es una "
     "ficción contable. Lo que la aseguradora se obliga a pagar es el salario mínimo, y "
     "eso es lo que cuesta. La consecuencia matemática --- pérdida de inyectividad --- es "
     "el reflejo exacto de una consecuencia económica evidente una vez enunciada."),

    ("04_estructura.tex",
     "y una sola evaluación lo determina",
     "El costo de la comprobación es una evaluación de $\\VP$, frente a las "
     "$\\datoEvBis$ que consume, en promedio, un intento fallido de bisección sobre el "
     "intervalo completo. La ganancia no es solo de tiempo: la comprobación previa "
     "convierte un fallo del algoritmo en un diagnóstico interpretable."),

    ("04_estructura.tex",
     "el único cuyo quiebre está\nexactamente en $S_0$",
     "Esto ocurre porque el primer periodo pertenece al año calendario de la valoración, "
     "para el cual $n=0$ y por tanto $\\tau=\\phi=1$: la mesada y el salario mínimo aún "
     "no se han reajustado, y el piso coincide con el nominal. Todos los periodos "
     "posteriores han sufrido al menos un reajuste, y en ellos el deslizamiento ya ha "
     "separado ambas trayectorias."),

    ("04_estructura.tex",
     "porque los factores de indexación de \\cref{eq:factor-ipc} se actualizan una vez al año",
     "Es el punto técnico decisivo de la demostración. Si la indexación fuese continua "
     "--- si la mesada creciera mes a mes en lugar de dar un salto anual --- habría un "
     "quiebre distinto por cada uno de los $\\datoNMeses$ periodos, y los racimos serían "
     "conjuntos densos en lugar de conjuntos finitos. La estructura discreta del "
     "reajuste es lo que hace el problema tratable."),

    ("04_estructura.tex",
     "la benignidad numérica del problema colombiano es, en\neste sentido, una consecuencia contingente de su política salarial",
     "El experimento mental es verificable con la aplicación interactiva que acompaña "
     "este trabajo: fijando el deslizamiento por encima del dos por ciento anual, los "
     "racimos se ensanchan hasta solaparse y la región afín comercial desaparece."),

    ("04_estructura.tex",
     "Una función convexa tiene\nderivada lateral derecha no decreciente",
     "El resultado es estándar en análisis convexo; véase \\citet[Teorema~24.1]"
     "{rockafellar1970} o \\citet[§3.1]{boyd2004}. Su contrarrecíproco es lo que se usa "
     "aquí: exhibir dos puntos donde la derivada lateral derecha decrece basta para "
     "refutar la convexidad, sin necesidad de examinar la función en el resto del "
     "dominio."),

    ("04_estructura.tex",
     "basta\npara invalidar todo argumento que invoque convexidad",
     "Conviene resistir la tentación de considerar despreciable una violación de dos "
     "milésimas. La convexidad es una propiedad cualitativa: o se tiene o no se tiene. "
     "Un argumento que la invoque es válido o inválido, y su conclusión no se vuelve "
     "\\emph{casi} válida porque la violación sea pequeña. Lo que sí es legítimo decir "
     "--- y se dice en la \\cref{sec:robustez-empirica} --- es que la consecuencia "
     "práctica observada es benigna."),

    ("04_estructura.tex",
     "un teorema del valor medio para funciones Lipschitz",
     "Véase \\citet[Teorema~2.3.7]{clarke1983}. El enunciado sustituye la derivada del "
     "teorema del valor medio clásico por un elemento del subdiferencial de Clarke, y es "
     "precisamente la herramienta que permite hacer análisis de estabilidad sobre "
     "funciones no diferenciables."),

    ("04_estructura.tex",
     "y de que la discusión sobre cuál usar sea una\ndiscusión sobre \\emph{costo}, no sobre estabilidad",
     "Es una observación que conviene tener presente al leer el \\cref{cap:resultados}: "
     "las diferencias de exactitud entre métodos que allí se reportan --- entre "
     "$10^{-10}$ y $10^{-6}$ pesos --- carecen por completo de significado práctico. Lo "
     "que tiene significado es el número de evaluaciones."),

    ("04_estructura.tex",
     "un factor de $34$",
     "El valor correcto de la derivada lateral derecha en $M=S_0$ es $7{,}23$, y "
     "corresponde a los pocos periodos del año calendario de la valoración en los que "
     "el piso aún no se ha separado del nominal. La fórmula evaluada sobre la rama "
     "equivocada devuelve $249{,}06$, que es la pendiente que tendría la función si "
     "todos los periodos estuviesen activos."),

    # =================================================================
    # Capítulo 5 — Métodos
    # =================================================================
    ("05_metodos.tex",
     "es inferior en más de seis órdenes de\nmagnitud",
     "Una iteración de cualquiera de los métodos del catálogo consume, a lo sumo, unas "
     "decenas de operaciones de punto flotante; una evaluación de $\\VP$ consume del "
     "orden de $10^5$. La proporción justifica ignorar por completo el costo aritmético "
     "del método en la comparación."),

    ("05_metodos.tex",
     "un método\nque reevalúe un punto no sea penalizado dos veces",
     "La memoización favorece particularmente a la familia de la regula falsi, que "
     "conserva un extremo del intervalo durante muchas iteraciones. Sin ella, esos "
     "métodos aparecerían artificialmente caros y la comparación estaría sesgada en "
     "contra suya."),

    ("05_metodos.tex",
     "el método de referencia para un problema como este",
     None),

    ("05_metodos.tex",
     "el número observado es $\\datoEvBis$ evaluaciones en\npromedio",
     "La discrepancia entre la cota teórica de unas cincuenta y dos iteraciones y las "
     "treinta y tres observadas se explica porque el criterio de parada efectivo es el "
     "del residuo y no el del paso: con una pendiente de "
     "$\\datoPendienteAfin$, un residuo menor que un peso corresponde a un error en la "
     "mesada del orden de $4\\cdot10^{-3}$ pesos, muy por encima de la tolerancia "
     "$\\varepsilon_x=10^{-8}$ que da lugar a la cota."),

    ("05_metodos.tex",
     "El efecto sobre la conclusión es grande: el costo medio\nde la bisección pasa de $21{,}6$ a $\\datoEvBis$ evaluaciones",
     "Se documenta este episodio porque ilustra un riesgo metodológico general en la "
     "comparación de algoritmos: los conjuntos de prueba construidos con valores "
     "«redondos» pueden favorecer sistemáticamente a los métodos cuya aritmética "
     "coincide con esa forma de redondeo. La bisección, que divide en potencias de dos, "
     "es especialmente vulnerable a ello."),

    ("05_metodos.tex",
     "es la que garantiza que ITP nunca gaste más de $n_0$ iteraciones\nadicionales sobre la cota de la bisección",
     "El resultado de \\citet{oliveira2021} es notable porque durante décadas se "
     "consideró que la optimalidad en el peor caso y la convergencia superlineal eran "
     "objetivos incompatibles: los métodos rápidos degradaban en el peor caso y los "
     "robustos no aceleraban en el caso bueno. ITP alcanza ambas."),

    ("05_metodos.tex",
     "de modo que su índice de eficiencia $\\varphi^1\\approx1{,}618$ supera al de Newton",
     "La observación se remonta a \\citet{ostrowski1966} y es bien conocida en análisis "
     "numérico, pero se ignora con frecuencia en la práctica, donde la comparación "
     "suele hacerse por orden nominal. Este trabajo la confirma empíricamente: la "
     "secante requiere $\\datoEvSec$ evaluaciones frente a las $\\datoEvNFD$ de Newton "
     "con diferencias finitas."),

    ("05_metodos.tex",
     "es una elección \\emph{correcta}, y\nconviene dejarlo dicho, porque el resto de este trabajo señala sobre todo defectos",
     "El análisis no permite determinar si la elección de $h=1$ peso fue deliberada o "
     "afortunada. En cualquier caso es la correcta, y el rango admisible que aquí se "
     "deriva ofrece por primera vez un criterio explícito para justificarla o para "
     "revisarla si cambian las magnitudes del problema."),

    ("05_metodos.tex",
     "la raíz real de $t^3=t^2+t+1$",
     "El valor es $p\\approx1{,}83929$, la llamada constante \\emph{tribonacci}, que "
     "generaliza la razón áurea de la secante del mismo modo que Müller generaliza la "
     "interpolación lineal a la cuadrática. La sucesión de órdenes de la familia de "
     "métodos de interpolación de grado creciente tiende a $2$ por abajo."),

    ("05_metodos.tex",
     "el orden $3$ presupone $f\\in C^3$ y explota la\ninformación de $f''$",
     "Halley publicó el método en 1694 como una mejora del de Newton, y su deducción "
     "original --- por aproximación mediante una hipérbola en lugar de una recta --- "
     "presupone explícitamente curvatura no nula. Sobre una función afín a trozos la "
     "hipérbola degenera en la recta, y con ella toda la ventaja del método."),

    ("05_metodos.tex",
     "el punto fijo relajado puede leerse como un\nNewton con derivada CONGELADA",
     None),

    # =================================================================
    # Capítulo 6 — Variables
    # =================================================================
    ("06_variables.tex",
     "adoptadas por la Resolución 1555 de\n2010 de la Superintendencia Financiera de Colombia",
     "La resolución actualizó las tablas de mortalidad de rentistas vigentes desde 2005 "
     "y adoptó las denominadas RV-08 y RI-08, construidas sobre la experiencia del "
     "período 2005--2008 del sistema pensional colombiano. Incluye asimismo los "
     "factores anuales de mejora de longevidad y fija su año base."),

    ("06_variables.tex",
     "es\nobligatorio para el cálculo de reservas de rentas vitalicias en Colombia",
     "La obligatoriedad alcanza al cálculo de reservas matemáticas y a la constitución "
     "de las provisiones técnicas de las compañías de seguros de vida que operan el "
     "ramo de rentas vitalicias del sistema general de pensiones."),

    ("06_variables.tex",
     "valor\nconsistente con el rango de $7$ a $9$ años reportado en la literatura\ninternacional",
     "El llamado tiempo de duplicación de Gompertz es notablemente estable entre "
     "poblaciones y épocas, hecho que se conoce como ley de compensación de la "
     "mortalidad. Su estabilidad es uno de los argumentos empíricos más sólidos a favor "
     "del modelo de Gompertz frente a alternativas con más parámetros."),

    ("06_variables.tex",
     "El tope de $30$ años en el exponente merece comentario",
     "El tope aparece en la propia resolución y no es una decisión del modelador. Su "
     "efecto es acotar la extrapolación de una tendencia estimada sobre una ventana "
     "histórica limitada, lo cual es prudente en sentido estadístico; pero al mismo "
     "tiempo reduce la reserva exigida, lo cual es imprudente en sentido financiero. "
     "Las dos prudencias apuntan en direcciones opuestas."),

    ("06_variables.tex",
     "el \\emph{origen} de los valores $0{,}70$ y $0{,}95$",
     "Se revisó la documentación disponible del motor de valoración, la nota técnica de "
     "la que procede y la resolución regulatoria. Ninguna de las tres los justifica. "
     "Esto no significa que carezcan de fundamento --- pueden provenir de un estudio de "
     "experiencia interno --- sino que ese fundamento no es verificable con la "
     "información disponible para este trabajo."),

    ("06_variables.tex",
     "Todos los teoremas\nsobreviven; solo cambian los números",
     "Esta robustez estructural es una propiedad valiosa y poco frecuente. Significa que "
     "la conclusión metodológica del trabajo --- qué método iterativo emplear --- no "
     "depende de una discusión actuarial que sigue abierta."),

    ("06_variables.tex",
     "un error de un punto básico en la tasa produce un error de\n$\\sim12\\,000$ pesos en la mesada",
     "La cifra se obtiene del análisis de sensibilidad: cincuenta puntos básicos mueven "
     "la mesada un $\\datoSensTasaAlta$ por ciento sobre una mesada base del orden de "
     "cuatro millones de pesos, de donde un punto básico equivale aproximadamente a "
     "diez mil o doce mil pesos según el escenario."),

    ("06_variables.tex",
     "El modelo está formulado, en el fondo,\nen términos reales",
     "La cancelación es exacta solo si la indexación de la mesada y la del descuento "
     "usan la misma trayectoria de inflación, lo cual el modelo cumple por construcción. "
     "Lo que sobrevive es la asimetría introducida por el salario mínimo, que crece con "
     "inflación \\emph{más} deslizamiento."),

    ("06_variables.tex",
     "fijado por el Decreto 0159 de 2026",
     "Decreto 0159 del 19 de febrero de 2026, del Ministerio del Trabajo, que fija el "
     "salario mínimo legal mensual vigente para el año 2026 en \\$\\,\\datoSMLV. El dato "
     "es exacto y de verificación inmediata, a diferencia de las hipótesis financieras y "
     "demográficas del modelo, que son proyecciones."),

    ("06_variables.tex",
     "entre el $3{,}8\\%$ y el $18\\%$, tomado de una tabla interna",
     "El recargo crece con la edad del causante y es mayor para hombres que para "
     "mujeres, lo cual es coherente con la dirección esperada del riesgo de longevidad "
     "no transferido. Su calibración, sin embargo, no está documentada en las fuentes "
     "disponibles."),

    ("06_variables.tex",
     "convergiendo hacia una tasa forward última (UFR)",
     "El método fue propuesto por \\citet{smith2001} y adoptado por la autoridad europea "
     "de seguros y pensiones para la construcción de las curvas libres de riesgo bajo "
     "Solvencia~II; la documentación técnica es \\citet{eiopa2019}. Su virtud es "
     "reproducir exactamente los puntos líquidos observados y extrapolar de forma suave "
     "más allá del último de ellos."),

    ("06_variables.tex",
     "Con un único nodo,\nSmith-Wilson no interpola nada",
     "El método resuelve un sistema lineal cuya dimensión es el número de puntos "
     "observados. Con un solo punto, ese sistema es escalar y la curva resultante queda "
     "determinada por completo por la elección de $\\alpha$ y de la tasa última, "
     "ninguna de las cuales se ha calibrado contra datos de mercado."),

    ("06_variables.tex",
     "una distribución\n$t$ de Student escalada, o un remuestreo histórico por bloques",
     "El remuestreo por bloques tiene la ventaja adicional de preservar la "
     "autocorrelación de los rendimientos, que la simulación de variables normales "
     "independientes destruye. En un horizonte de veinte años, la persistencia de los "
     "regímenes de mercado no es un detalle menor."),

    ("06_variables.tex",
     "se tomó el promedio redondeado",
     "El procedimiento está descrito con transparencia en la documentación del propio "
     "código, lo cual es de agradecer y hace posible esta crítica. La objeción no es a "
     "la honestidad del registro, que es ejemplar, sino a la validez del procedimiento."),

    ("06_variables.tex",
     "las causas más probables son diferencias en el salario mínimo de referencia",
     "El motor emplea el salario mínimo de 2026, mientras que las cotizaciones de "
     "referencia pueden haberse calculado con el vigente en la fecha de emisión. Sobre "
     "pólizas con mesada cercana al racimo I, esa diferencia basta para explicar buena "
     "parte de la discrepancia; sobre las demás, no."),

    # =================================================================
    # Capítulo 7 — Retiro programado
    # =================================================================
    ("07_retiro.tex",
     "el riesgo de longevidad y el riesgo de mercado permanecen en cabeza del\npensionado",
     "Artículo 81 de la Ley 100 de 1993. La modalidad se define allí como aquella en que "
     "el afiliado o los beneficiarios obtienen su pensión de la sociedad administradora "
     "con cargo a su cuenta individual y al bono pensional, calculándose cada año una "
     "anualidad en unidades de valor constante igual al resultado de dividir el saldo de "
     "la cuenta por el capital necesario para financiar una unidad de renta vitalicia "
     "para el afiliado y sus beneficiarios."),

    ("07_retiro.tex",
     "tabla de mortalidad sin factores de mejora,\n        sobrecosto de mortalidad y recargo de gastos de retiro programado",
     "La supresión de los factores de mejora y la adición de un sobrecosto son "
     "decisiones de modelación de la administradora, no imposiciones normativas. Se "
     "evalúan críticamente en la \\cref{cap:variables}."),

    ("07_retiro.tex",
     "Impone la condición comercial de que la renta vitalicia supere siempre al retiro\n        programado",
     "Es un requisito de negocio explícito y no un resultado actuarial. En la "
     "configuración por defecto del motor está desactivado, de modo que la brecha entre "
     "ambos productos surge de la propia dinámica del fondo; puede activarse desde la "
     "parametrización."),

    ("07_retiro.tex",
     "está reportando\nel valor del recorte",
     "La objeción no invalida el uso de los recortes, que responden a exigencias legales "
     "y comerciales legítimas. Lo que exige es que la presentación del resultado "
     "distinga entre lo que el fondo sostiene y lo que las restricciones imponen. El "
     "motor ya registra esa distinción en su salida, mediante las columnas que indican "
     "qué ajuste se activó cada año; lo que falta es que llegue al usuario final."),

    ("07_retiro.tex",
     "Con Newton semisuave ($\\datoEvNAN$ evaluaciones) el costo baja a unas $62$\nevaluaciones por cédula",
     "La estimación supone arranque frío en cada año, es decir, sin aprovechar la "
     "solución del año anterior. La mejora que se describe a continuación reduce esa "
     "cifra a unas cuarenta evaluaciones."),

    # =================================================================
    # Capítulo 8 — Resultados
    # =================================================================
    ("08_resultados.tex",
     "elegido precisamente por no ser ninguno de los métodos que\ncompiten en primer plano",
     "Usar como referencia uno de los métodos comparados introduciría un sesgo evidente "
     "en su favor: su error medido sería, por construcción, nulo. Brent es además el "
     "algoritmo por defecto de las bibliotecas científicas, de modo que la referencia es "
     "reproducible con cualquier implementación estándar."),

    ("08_resultados.tex",
     "la diferencia sobre una cartera de\n      cien mil cotizaciones es de unos $15$ minutos de cómputo frente a menos de\n      dos",
     "El cálculo supone ejecución secuencial. En la práctica el proceso masivo se "
     "paraleliza, lo que reduce ambos tiempos en la misma proporción y deja intacto el "
     "factor de mejora."),

    ("08_resultados.tex",
     "significa convergencia \\emph{demasiado\n        rápida para ser medida asintóticamente}",
     "Es una situación análoga a la de intentar estimar la pendiente de una recta a "
     "partir de un solo punto. El estimador no es defectuoso: el objeto que pretende "
     "medir --- un comportamiento asintótico --- simplemente no existe cuando la "
     "convergencia es finita."),

    ("08_resultados.tex",
     "todo método basado en pendientes da pasos exagerados",
     "El efecto es el esperable: si la función es casi horizontal, el cociente "
     "$f(x)/f'(x)$ es grande y el paso de Newton sobrepasa ampliamente la raíz. Lo "
     "salva, en este caso, el acotamiento al intervalo admisible."),

    ("08_resultados.tex",
     "la garantía formal solo la ofrece el\nmétodo salvaguardado del \\cref{alg:newton-salvaguardado}",
     "La distinción entre lo observado y lo demostrado importa especialmente en un "
     "contexto regulado. Una compañía que deba justificar su metodología de valoración "
     "ante un supervisor está en mejor posición exhibiendo una garantía demostrable que "
     "una regularidad empírica sobre su cartera actual."),

    ("08_resultados.tex",
     "es el precio de una razón de convergencia de $1/2$",
     "Cada iteración de la bisección gana exactamente un bit de precisión, y un dígito "
     "decimal equivale a $\\log_2 10\\approx3{,}32$ bits. De ahí las tres iteraciones y "
     "media por dígito que muestra la pendiente de la recta."),

    ("08_resultados.tex",
     "sino una división, y basta un método de segundo orden con derivada\nexacta para reconocerlo y aprovecharlo",
     "La afirmación no debe leerse como una invitación a resolver el problema "
     "analíticamente: la posición del tramo afín depende de la póliza y no se conoce de "
     "antemano. Lo que el método de segundo orden hace es \\emph{descubrir} en tiempo de "
     "ejecución que se encuentra en un tramo afín, y terminar."),
]


def main(escribir: bool = False):
    total, presentes, faltantes = 0, 0, []
    por_archivo = {}
    for archivo, ancla, nota in NOTAS:
        if nota is None:
            continue
        por_archivo.setdefault(archivo, []).append((ancla, nota))

    accion = "insertadas" if escribir else "por insertar"
    for archivo, pares in por_archivo.items():
        ruta = CAP / archivo
        texto = ruta.read_text(encoding="utf-8")
        n = 0
        for ancla, nota in pares:
            if ancla + "\\footnote{" in texto:
                presentes += 1
                continue  # la nota ya esta en el texto: no se duplica
            if ancla not in texto:
                faltantes.append((archivo, ancla[:70].replace("\n", " ")))
                continue
            if texto.count(ancla) > 1:
                faltantes.append((archivo, "AMBIGUA: " + ancla[:60].replace("\n", " ")))
                continue
            texto = texto.replace(ancla, ancla + "\\footnote{" + nota + "}", 1)
            n += 1
        if escribir and n:
            ruta.write_text(texto, encoding="utf-8")
        print(f"  {archivo:<26} {n:>3} notas {accion}")
        total += n

    print(f"\nNotas ya presentes en el texto: {presentes}")
    print(f"Total {accion}: {total}")
    if not escribir and total:
        print("No se modifico ningun archivo (use --escribir para aplicar los cambios).")
    if faltantes:
        print(f"\nAnclas NO encontradas ({len(faltantes)}):")
        for a, t in faltantes:
            print(f"  [{a}] {t}")


if __name__ == "__main__":
    main(escribir="--escribir" in sys.argv[1:])
