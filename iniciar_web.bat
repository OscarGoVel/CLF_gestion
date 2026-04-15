@echo off
:: CLF Gestion Web — Arranque HTTP (red local, sin SSL)
:: Accesible en: http://192.168.0.40:8000  (celulares, tablets, otras PCs)

cd /d "%~dp0"

:: Liberar puerto 8000 si esta ocupado
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Cerrando proceso anterior en puerto 8000 ^(PID %%a^)...
    taskkill /F /PID %%a >nul 2>&1
)

echo Iniciando CLF Gestion Web ^(HTTP puerto 8000^)...
python -m uvicorn web_app.main:app --host 0.0.0.0 --port 8000 --workers 4 --loop asyncio
pause
