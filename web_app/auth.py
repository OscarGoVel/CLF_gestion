# -*- coding: utf-8 -*-
"""
web_app/auth.py
Utilidades de autenticacion: hash de contrasena compatible con la app de escritorio
y generacion/validacion de tokens JWT.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from web_app.config import settings

# ── Configuracion JWT ─────────────────────────────────────────────────────────
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 8


# ── Contrasenas ───────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Mismo algoritmo que usa la app de escritorio (ui/login.py)."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        b'clf_sistema',
        200_000,
    ).hex()


def verificar_password(password: str, stored_hash: str) -> bool:
    return _hash_password(password) == stored_hash


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
