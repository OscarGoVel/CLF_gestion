@echo off
:: CLF Gestion Web — Arranque HTTPS (produccion)
:: Accesible en: https://192.168.0.40:8443
::
:: Primera vez: ejecuta  python tools/generar_cert.py  para crear ssl/server.crt

cd /d "%~dp0"

if not exist ssl\server.crt (
    echo Certificado SSL no encontrado. Generando...
    python tools\generar_cert.py
)

echo Iniciando CLF Gestion Web ^(HTTPS puerto 8443^)...
python -m uvicorn web_app.main:app ^
    --host 0.0.0.0 ^
    --port 8443 ^
    --ssl-keyfile ssl/server.key ^
    --ssl-certfile ssl/server.crt ^
    --workers 1

pause
