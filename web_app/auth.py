# -*- coding: utf-8 -*-
"""
web_app/auth.py
Utilidades de autenticacion: hash de contrasena compatible con la app de escritorio
y generacion/validacion de tokens JWT.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from jose import JWTError, jwt
from web_app.config import settings

# ── Configuracion JWT ─────────────────────────────────────────────────────────
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8

# Salt estático heredado — solo para verificar hashes antiguos durante la migración
_SALT_LEGACY = b'clf_sistema'


# ── Contraseñas ───────────────────────────────────────────────────────────────

def _hash_legacy(password: str) -> str:
    """Hash con salt estático (esquema antiguo). Solo para verificación."""
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), _SALT_LEGACY, 200_000
    ).hex()


def hash_password(password: str) -> Tuple[str, str]:
    """
    Genera un hash seguro con salt aleatorio por usuario.
    Retorna (password_hash, salt) — ambos deben guardarse en la BD.
    """
    salt = secrets.token_hex(32)
    phash = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt.encode('utf-8'), 200_000
    ).hex()
    return phash, salt


def verificar_password(password: str, stored_hash: str, salt: Optional[str] = None) -> bool:
    """
    Verifica una contraseña contra su hash almacenado.
    - Si salt es None o vacío: usa el esquema heredado (salt estático).
    - Si salt está presente: usa el esquema nuevo (salt por usuario).
    """
    if not salt:
        return _hash_legacy(password) == stored_hash
    computed = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt.encode('utf-8'), 200_000
    ).hex()
    return computed == stored_hash


# ── JWT ───────────────────────────────────────────────────────────────────────

def crear_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(data, settings.secret_key_efectiva, algorithm=ALGORITHM)


def decodificar_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key_efectiva, algorithms=[ALGORITHM])
    except JWTError:
        return None


# Alias para compatibilidad con código legacy que importa _hash_password
def _hash_password(password: str) -> str:
    """Alias heredado. Usa el esquema antiguo; usar hash_password() para nuevos hashes."""
    return _hash_legacy(password)
