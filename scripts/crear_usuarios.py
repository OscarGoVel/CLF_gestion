#!/usr/bin/env python3
"""
Crea usuarios iniciales en clf_usuarios.
Ejecutar desde la raíz del proyecto:
    python scripts/crear_usuarios.py

Para producción (Cloud SQL via proxy):
    CLF_PG_PASSWORD=<pwd> CLF_PG_HOST=127.0.0.1 python scripts/crear_usuarios.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from web_app.auth import hash_password
from web_app.database import pool_usuarios

USUARIOS = [
    {"username": "larry.yussef",     "nombre": "Larry Yussef",     "rol": "Administrador", "password": "Admin2026"},
    {"username": "christopher.gamboa", "nombre": "Christopher Gamboa", "rol": "Administrador", "password": "Admin2026"},
]

def crear(username, nombre, rol, password):
    phash, salt = hash_password(password)
    with pool_usuarios.conexion() as (conn, cur):
        cur.execute(
            "SELECT id FROM usuarios WHERE username = %s", (username,)
        )
        if cur.fetchone():
            print(f"  SKIP  — '{username}' ya existe")
            return
        cur.execute(
            "INSERT INTO usuarios (username, nombre, password_hash, salt, rol, activo) "
            "VALUES (%s, %s, %s, %s, %s, 1) RETURNING id",
            (username, nombre, phash, salt, rol),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        print(f"  OK    — '{username}' creado (id={new_id}, rol={rol})")

if __name__ == "__main__":
    print("Creando usuarios…")
    for u in USUARIOS:
        crear(**u)
    print("Listo.")
