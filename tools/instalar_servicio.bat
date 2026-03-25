@echo off
:: CLF Gestion Web — Instalar como servicio de Windows
:: Usa el Programador de Tareas para arrancar automaticamente al iniciar el sistema.
::
:: REQUIERE: ejecutar como Administrador
:: Para desinstalar: schtasks /delete /tn "CLF-Gestion-Web" /f

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Ejecuta este script como Administrador.
    pause
    exit /b 1
)

set PROJECT_DIR=%~dp0..
set PYTHON_EXE=python
set TASK_NAME=CLF-Gestion-Web
set LOG_FILE=%PROJECT_DIR%\logs\web_app.log

:: Crear carpeta de logs
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

:: Generar certificado si no existe
if not exist "%PROJECT_DIR%\ssl\server.crt" (
    echo Generando certificado SSL...
    cd /d "%PROJECT_DIR%"
    python tools\generar_cert.py
)

:: Eliminar tarea anterior si existe
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Crear XML de la tarea
set XML_FILE=%TEMP%\clf_web_task.xml

(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>CLF Gestion Web - Servidor FastAPI con HTTPS^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<BootTrigger^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<Delay^>PT30S^</Delay^>
echo     ^</BootTrigger^>
echo   ^</Triggers^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<RestartOnFailure^>
echo       ^<Interval^>PT1M^</Interval^>
echo       ^<Count^>10^</Count^>
echo     ^</RestartOnFailure^>
echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
echo   ^</Settings^>
echo   ^<Actions^>
echo     ^<Exec^>
echo       ^<Command^>%PYTHON_EXE%^</Command^>
echo       ^<Arguments^>-m uvicorn web_app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile ssl/server.key --ssl-certfile ssl/server.crt --workers 2^</Arguments^>
echo       ^<WorkingDirectory^>%PROJECT_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo ^</Task^>
) > "%XML_FILE%"

:: Registrar la tarea
schtasks /create /tn "%TASK_NAME%" /xml "%XML_FILE%" /f
del "%XML_FILE%"

if %errorlevel% equ 0 (
    echo.
    echo Servicio instalado correctamente.
    echo   Nombre:     %TASK_NAME%
    echo   Arranque:   Automatico al iniciar Windows ^(con 30s de retardo^)
    echo   URL:        https://192.168.0.40:8443
    echo.
    echo Para iniciar ahora sin reiniciar:
    echo   schtasks /run /tn "%TASK_NAME%"
    echo.
    set /p INICIAR=Iniciar ahora? [S/N]:
    if /i "%INICIAR%"=="S" schtasks /run /tn "%TASK_NAME%"
) else (
    echo ERROR al registrar la tarea.
)

pause
