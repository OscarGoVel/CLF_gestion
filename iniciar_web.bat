@echo off
:: CLF Gestion Web — Arranque HTTP (desarrollo)
:: Accesible en: http://localhost:8000  o  http://192.168.0.40:8000

cd /d "%~dp0"
echo Iniciando CLF Gestion Web (HTTP puerto 8000)...
python -m uvicorn web_app.main:app --reload --host 0.0.0.0 --port 8000
pause
