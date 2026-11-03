@echo off
setlocal EnableExtensions

rem ===========================================================
rem  TESIS DE MAESTRIA EN MATEMATICAS
rem  Metodos numericos iterativos para la cotizacion
rem  de rentas vitalicias  --  Eduardo Lagos Duran
rem
rem  Lanzador para Windows. Doble clic para abrir el menu.
rem
rem  NOTA: este archivo esta escrito sin tildes a proposito.
rem  La consola de Windows usa por defecto una pagina de
rem  codigos que no es UTF-8, y los acentos se verian como
rem  simbolos raros. El contenido con acentos esta en el
rem  documento y en README.md, no aqui.
rem ===========================================================

cd /d "%~dp0"
title Tesis - Metodos numericos iterativos para rentas vitalicias
color 0F

set "RAIZ=%~dp0"
set "VENV=%RAIZ%venv"
set "PY=%VENV%\Scripts\python.exe"

rem ---------- Localizar Python del sistema ----------
set "PYSIS="
py -3 --version >nul 2>&1 && set "PYSIS=py -3"
if not defined PYSIS (
  python --version >nul 2>&1 && set "PYSIS=python"
)

:MENU
cls
echo.
echo  ============================================================
echo    TESIS DE MAESTRIA EN MATEMATICAS
echo    Metodos numericos iterativos para la cotizacion
echo    de rentas vitalicias
echo.
echo    Eduardo Lagos Duran
echo  ============================================================
echo.
echo    DOCUMENTO
echo      [1]  Abrir la tesis en PDF
echo      [2]  Abrir el README
echo.
echo    APLICACIONES
echo      [3]  Presentacion interactiva de la defensa
echo      [4]  Cotizador (aplicacion de produccion)
echo.
echo    REGENERAR
echo      [5]  Correr el banco de pruebas y rehacer las figuras
echo      [6]  Recompilar el PDF desde LaTeX
echo.
echo    OTROS
echo      [7]  Abrir la carpeta del proyecto
echo      [8]  Instalar / reparar el entorno de Python
echo      [9]  Diagnostico (que falta y que esta bien)
echo      [0]  Salir
echo.
if not exist "%VENV%\.dependencias_ok" (
  echo    [!] El entorno de Python aun no esta listo.
  echo        Las opciones 3 a 5 lo instalaran automaticamente.
  echo.
)
set "OP="
set /p "OP=   Elija una opcion y pulse Enter:  "

if "%OP%"=="1" goto ABRIR_PDF
if "%OP%"=="2" goto ABRIR_README
if "%OP%"=="3" goto PRESENTACION
if "%OP%"=="4" goto COTIZADOR
if "%OP%"=="5" goto REGENERAR
if "%OP%"=="6" goto COMPILAR
if "%OP%"=="7" goto ABRIR_CARPETA
if "%OP%"=="8" goto INSTALAR
if "%OP%"=="9" goto DIAGNOSTICO
if "%OP%"=="0" goto FIN
goto MENU


rem ===========================================================
:ABRIR_PDF
if not exist "tex\tesis.pdf" (
  echo.
  echo  [!] No se encuentra tex\tesis.pdf
  echo      Use la opcion 6 para compilarlo.
  echo.
  pause
  goto MENU
)
start "" "tex\tesis.pdf"
goto MENU


rem ===========================================================
:ABRIR_README
if exist "README.md" (
  start "" notepad "README.md"
) else (
  echo  [!] No se encuentra README.md
  pause
)
goto MENU


rem ===========================================================
:ABRIR_CARPETA
start "" "%RAIZ%"
goto MENU


rem ===========================================================
:PRESENTACION
call :ASEGURAR_ENTORNO
if errorlevel 1 goto MENU
cls
echo.
echo  ------------------------------------------------------------
echo   Iniciando la presentacion interactiva...
echo.
echo   Se abrira en el navegador dentro de unos segundos.
echo   Si no se abre solo, entre a:   http://localhost:8501
echo.
echo   Para cerrarla: cierre la ventana negra que aparecera,
echo   o pulse Ctrl+C dentro de ella.
echo  ------------------------------------------------------------
echo.
start "Presentacion de la tesis" /D "%RAIZ%app" cmd /s /k ""%PY%" -m streamlit run presentacion.py --server.headless true --browser.gatherUsageStats false"
timeout /t 12 /nobreak >nul
start "" "http://localhost:8501"
goto MENU


rem ===========================================================
:COTIZADOR
call :ASEGURAR_ENTORNO
if errorlevel 1 goto MENU
if not exist "py\cotizador\app.py" (
  echo.
  echo  [!] No se encuentra py\cotizador\app.py
  echo.
  pause
  goto MENU
)
cls
echo.
echo  ------------------------------------------------------------
echo   Iniciando el cotizador...
echo   Se abrira en:   http://localhost:8502
echo  ------------------------------------------------------------
echo.
start "Cotizador" /D "%RAIZ%py\cotizador" cmd /s /k ""%PY%" -m streamlit run app.py --server.port 8502 --server.headless true --browser.gatherUsageStats false"
timeout /t 12 /nobreak >nul
start "" "http://localhost:8502"
goto MENU


rem ===========================================================
:REGENERAR
call :ASEGURAR_ENTORNO
if errorlevel 1 goto MENU
cls
echo.
echo  ------------------------------------------------------------
echo   Regenerando todos los resultados del documento.
echo   Esto tarda unos 3 minutos. No cierre esta ventana.
echo  ------------------------------------------------------------
echo.
pushd "%RAIZ%py"

echo  [1/8] Banco de pruebas (19 metodos x 25 escenarios)...
"%PY%" correr_benchmark.py || goto REGEN_ERROR

echo  [2/8] Figuras: estructura de la funcion de valoracion...
"%PY%" fig_01_estructura.py || goto REGEN_ERROR

echo  [3/8] Figuras: convergencia y comparacion de metodos...
"%PY%" fig_02_convergencia.py || goto REGEN_ERROR

echo  [4/8] Figuras: mortalidad, supervivencia y descuento...
"%PY%" fig_03_actuarial.py || goto REGEN_ERROR

echo  [5/8] Figuras: retiro programado y sensibilidad...
"%PY%" fig_04_rp_sensibilidad.py || goto REGEN_ERROR

echo  [6/8] Figuras: evaluacion de variables...
"%PY%" fig_05_variables.py || goto REGEN_ERROR

echo  [7/8] Cifras y tablas del documento...
"%PY%" generar_macros_tex.py || goto REGEN_ERROR
"%PY%" generar_tablas_tex.py || goto REGEN_ERROR

echo  [8/8] Listados de codigo del apendice D...
"%PY%" generar_extractos_codigo.py || goto REGEN_ERROR

popd
echo.
echo  ------------------------------------------------------------
echo   Listo. Todo regenerado.
echo   Use la opcion 6 para recompilar el PDF con los datos nuevos.
echo  ------------------------------------------------------------
echo.
pause
goto MENU

:REGEN_ERROR
popd
echo.
echo  [!] Fallo uno de los pasos. Revise el mensaje de arriba.
echo.
pause
goto MENU


rem ===========================================================
:COMPILAR
where latexmk >nul 2>&1
if errorlevel 1 (
  where pdflatex >nul 2>&1
  if errorlevel 1 (
    echo.
    echo  ------------------------------------------------------------
    echo   [!] No hay una distribucion de LaTeX instalada.
    echo.
    echo   Para compilar el documento necesita MiKTeX o TeX Live:
    echo       MiKTeX    https://miktex.org/download
    echo       TeX Live  https://tug.org/texlive/
    echo.
    echo   El PDF ya compilado esta en tex\tesis.pdf, de modo que
    echo   solo necesita LaTeX si va a modificar el documento.
    echo  ------------------------------------------------------------
    echo.
    pause
    goto MENU
  )
)
cls
echo.
echo  ------------------------------------------------------------
echo   Compilando el documento. Tarda entre 1 y 3 minutos.
echo   La primera vez puede tardar mas si MiKTeX descarga paquetes.
echo  ------------------------------------------------------------
echo.
pushd "%RAIZ%tex"
where latexmk >nul 2>&1
if errorlevel 1 (
  pdflatex -interaction=nonstopmode tesis.tex
  bibtex tesis
  pdflatex -interaction=nonstopmode tesis.tex
  pdflatex -interaction=nonstopmode tesis.tex
) else (
  latexmk -pdf -interaction=nonstopmode tesis.tex
)
popd
echo.
if exist "tex\tesis.pdf" (
  echo   Compilacion terminada. Abriendo el PDF...
  timeout /t 2 /nobreak >nul
  start "" "tex\tesis.pdf"
) else (
  echo  [!] No se genero el PDF. Revise tex\tesis.log
)
echo.
pause
goto MENU


rem ===========================================================
:INSTALAR
cls
echo.
echo  ------------------------------------------------------------
echo   Instalando el entorno de Python desde cero.
echo  ------------------------------------------------------------
echo.
if exist "%VENV%" (
  echo   Borrando el entorno anterior...
  rmdir /s /q "%VENV%"
)
if exist "%VENV%\.dependencias_ok" del /q "%VENV%\.dependencias_ok" >nul 2>&1
call :ASEGURAR_ENTORNO
echo.
pause
goto MENU


rem ===========================================================
rem  Subrutina: asegura que el entorno virtual exista Y tenga las
rem  dependencias instaladas. Devuelve errorlevel 1 si no lo consigue.
rem
rem  IMPORTANTE: no basta con comprobar que exista python.exe. Si el
rem  venv se crea pero la instalacion de paquetes falla a medias (sin
rem  internet, con proxy corporativo, o si se cierra la ventana), queda
rem  un entorno vacio y todas las opciones fallarian con el mensaje
rem  "No module named streamlit" sin explicar por que. Por eso se usa
rem  un archivo centinela que solo se escribe cuando la instalacion
rem  termino y se verifico.
rem ===========================================================
:ASEGURAR_ENTORNO
set "CENTINELA=%VENV%\.dependencias_ok"
if exist "%PY%" if exist "%CENTINELA%" exit /b 0

if not defined PYSIS (
  echo.
  echo  ------------------------------------------------------------
  echo   [!] No se encontro Python en este equipo.
  echo.
  echo   Instalelo desde   https://www.python.org/downloads/
  echo   y marque la casilla "Add Python to PATH" durante la
  echo   instalacion. Luego vuelva a ejecutar este archivo.
  echo  ------------------------------------------------------------
  echo.
  pause
  exit /b 1
)

cls
echo.
echo  ------------------------------------------------------------
echo   Preparando el entorno de Python.
echo   Solo ocurre la primera vez. Tarda unos minutos.
echo   NO cierre esta ventana hasta que termine.
echo  ------------------------------------------------------------
echo.
echo   Python del sistema:
%PYSIS% --version
echo.

if not exist "%PY%" (
  echo   [1/3] Creando el entorno virtual...
  %PYSIS% -m venv "%VENV%"
) else (
  echo   [1/3] El entorno virtual ya existe, se reutiliza.
)
if not exist "%PY%" (
  echo.
  echo   [!] No se pudo crear el entorno virtual.
  echo       Compruebe que tiene permisos de escritura en esta carpeta.
  echo.
  pause
  exit /b 1
)

echo   [2/3] Instalando dependencias...
echo.
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r "%RAIZ%requirements.txt"

echo.
echo   [3/3] Verificando la instalacion...
"%PY%" -c "import streamlit, plotly, numpy, pandas, matplotlib, openpyxl, scipy" 2>nul
if errorlevel 1 (
  echo.
  echo  ------------------------------------------------------------
  echo   [!] Las dependencias NO quedaron instaladas.
  echo.
  echo   Detalle del fallo:
  "%PY%" -c "import streamlit, plotly, numpy, pandas, matplotlib, openpyxl, scipy"
  echo.
  echo   Causas mas frecuentes:
  echo.
  echo    - Sin conexion a internet.
  echo.
  echo    - Proxy o inspeccion SSL corporativa. Es lo mas probable si
  echo      esta en un equipo de empresa. Pruebe a instalar asi, desde
  echo      una consola abierta en esta misma carpeta:
  echo.
  echo        venv\Scripts\python.exe -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
  echo.
  echo    - Antivirus bloqueando la escritura en la carpeta venv.
  echo.
  echo   Cuando lo resuelva, vuelva a ejecutar la opcion 8.
  echo  ------------------------------------------------------------
  echo.
  pause
  exit /b 1
)

rem Centinela: marca que la instalacion se completo Y se verifico.
> "%CENTINELA%" echo instalacion verificada

echo.
echo   Entorno listo. Todas las dependencias verificadas.
timeout /t 3 /nobreak >nul
exit /b 0


rem ===========================================================
:DIAGNOSTICO
cls
echo.
echo  ------------------------------------------------------------
echo   DIAGNOSTICO DEL ENTORNO
echo  ------------------------------------------------------------
echo.
echo   Carpeta del proyecto:
echo     %RAIZ%
echo.
echo   Python del sistema:
if defined PYSIS (%PYSIS% --version) else (echo     [!] NO ENCONTRADO)
echo.
echo   Entorno virtual:
if exist "%PY%" (echo     OK    "%PY%") else (echo     [!] NO EXISTE)
if exist "%VENV%\.dependencias_ok" (echo     OK    dependencias verificadas) else (echo     [!] dependencias SIN verificar)
echo.
echo   Paquetes:
if exist "%PY%" (
  for %%P in (streamlit plotly numpy pandas matplotlib openpyxl scipy) do (
    "%PY%" -c "import %%P" >nul 2>&1 && (echo     OK    %%P) || (echo     FALTA %%P)
  )
) else (
  echo     [!] sin entorno virtual, no se puede comprobar
)
echo.
echo   LaTeX:
where latexmk >nul 2>&1 && (echo     OK    latexmk) || (echo     --    latexmk no encontrado)
where pdflatex >nul 2>&1 && (echo     OK    pdflatex) || (echo     --    pdflatex no encontrado)
echo.
echo   Archivos clave:
if exist "tex\tesis.pdf" (echo     OK    tex\tesis.pdf) else (echo     FALTA tex\tesis.pdf)
if exist "app\presentacion.py" (echo     OK    app\presentacion.py) else (echo     FALTA app\presentacion.py)
if exist "py\cotizador\app.py" (echo     OK    py\cotizador\app.py) else (echo     FALTA py\cotizador\app.py)
if exist "requirements.txt" (echo     OK    requirements.txt) else (echo     FALTA requirements.txt)
echo.
echo  ------------------------------------------------------------
echo   Si falta algun paquete, use la opcion 8 para reinstalar.
echo  ------------------------------------------------------------
echo.
pause
goto MENU


rem ===========================================================
:FIN
endlocal
exit /b 0
