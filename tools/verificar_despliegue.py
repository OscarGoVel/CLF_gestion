#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/verificar_despliegue.py
Lista de verificacion pre-despliegue para CLF Gestion Web.

Ejecutar antes de poner el servidor en produccion:
    cd "c:/Users/oscar/OneDrive/Documentos/CLF Sistema/Gestion-CLF"
    python tools/verificar_despliegue.py
"""

import sys
import os
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OK   = "[OK]"
WARN = "[AVISO]"
FAIL = "[ERROR]"

resultados = []


def check(nombre, ok, detalle="", nivel="error"):
    marca = OK if ok else (WARN if nivel == "warn" else FAIL)
    resultados.append((marca, nombre, detalle))
    print(f"  {marca:8} {nombre}" + (f"  → {detalle}" if detalle else ""))


# ── 1. Archivo .env ───────────────────────────────────────────────────────────
print("\n── Configuracion ────────────────────────────────────────────────────")
env_path = ROOT / ".env"
check(".env existe", env_path.exists())

if env_path.exists():
    from dotenv import dotenv_values
    env = dotenv_values(env_path)
    sk = env.get("CLF_SECRET_KEY", "")
    check("CLF_SECRET_KEY configurada",    bool(sk) and "cambia-esto" not in sk,
          detalle="" if sk and "cambia-esto" not in sk else "usa el valor por defecto — cambialo")
    check("CLF_ENV=production",            env.get("CLF_ENV") == "production",
          nivel="warn", detalle=f"actual: {env.get('CLF_ENV', 'no definido')}")

# ── 2. SSL ────────────────────────────────────────────────────────────────────
print("\n── SSL ──────────────────────────────────────────────────────────────")
ssl_crt = ROOT / "ssl" / "server.crt"
ssl_key = ROOT / "ssl" / "server.key"
check("ssl/server.crt existe", ssl_crt.exists())
check("ssl/server.key existe", ssl_key.exists())

if ssl_crt.exists():
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import Encoding
        cert = x509.load_pem_x509_certificate(ssl_crt.read_bytes())
        from datetime import datetime, timezone
        dias = (cert.not_valid_after_utc - datetime.now(timezone.utc)).days
        check("Certificado vigente", dias > 0, detalle=f"expira en {dias} dias")
        check("Certificado > 30 dias", dias > 30, nivel="warn",
              detalle=f"renueva pronto: {dias} dias restantes")
    except Exception as e:
        check("Certificado valido", False, detalle=str(e))

# ── 3. Base de datos ──────────────────────────────────────────────────────────
print("\n── Base de datos ────────────────────────────────────────────────────")
try:
    import db_connection
    conn, cur = db_connection.conectar_usuarios()
    cur.execute("SELECT COUNT(*) FROM usuarios WHERE activo = 1")
    n = cur.fetchone()[0]
    conn.close()
    check("Conexion PostgreSQL usuarios", True, detalle=f"{n} usuario(s) activo(s)")
except Exception as e:
    check("Conexion PostgreSQL usuarios", False, detalle=str(e))

try:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    motor = cfg.get("motor", "sqlite")
    check("Motor postgresql activo", motor == "postgresql",
          nivel="warn", detalle=f"motor: {motor}")
except Exception as e:
    check("config.json legible", False, detalle=str(e))

# ── 4. Pool de conexiones ─────────────────────────────────────────────────────
print("\n── Pool de conexiones ───────────────────────────────────────────────")
try:
    from web_app.database import pool_usuarios, pool_empresa
    pool_usuarios._init()
    pool_empresa._init()
    check("Pool usuarios inicializado", True, detalle=pool_usuarios.estado()["db"])
    check("Pool empresa inicializado",  True, detalle=pool_empresa.estado()["db"])
except Exception as e:
    check("Pool de conexiones", False, detalle=str(e))

# ── 5. Dependencias web ───────────────────────────────────────────────────────
print("\n── Dependencias ─────────────────────────────────────────────────────")
paquetes = ["fastapi", "uvicorn", "jose", "jinja2", "multipart", "slowapi", "psycopg2"]
for pkg in paquetes:
    try:
        __import__(pkg)
        check(f"pip: {pkg}", True)
    except ImportError:
        check(f"pip: {pkg}", False, detalle=f"pip install {pkg}")

# ── 6. Archivos clave ─────────────────────────────────────────────────────────
print("\n── Archivos clave ───────────────────────────────────────────────────")
archivos = [
    "web_app/main.py",
    "web_app/auth.py",
    "web_app/config.py",
    "web_app/database.py",
    "web_app/templates/login.html",
    "web_app/templates/dashboard.html",
    "iniciar_web_https.bat",
]
for a in archivos:
    check(a, (ROOT / a).exists())

# ── Resumen ───────────────────────────────────────────────────────────────────
print()
errores = [r for r in resultados if r[0] == FAIL]
avisos  = [r for r in resultados if r[0] == WARN]
ok      = [r for r in resultados if r[0] == OK]

print(f"─" * 60)
print(f"  Resultado: {len(ok)} OK  |  {len(avisos)} avisos  |  {len(errores)} errores")

if errores:
    print(f"\n  Errores criticos (deben corregirse antes de continuar):")
    for _, nombre, detalle in errores:
        print(f"    • {nombre}" + (f": {detalle}" if detalle else ""))

if avisos:
    print(f"\n  Avisos (recomendado corregir):")
    for _, nombre, detalle in avisos:
        print(f"    • {nombre}" + (f": {detalle}" if detalle else ""))

if not errores:
    print("\n  Sistema listo para produccion.")
else:
    print("\n  Corrige los errores antes de desplegar.")

print()
sys.exit(1 if errores else 0)
