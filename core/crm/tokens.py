# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac as _hmac


def _key() -> bytes:
    from web_app.config import settings
    return settings.secret_key_efectiva.encode()


def generate_unsub_token(empresa_db: str, contacto_id: int) -> str:
    payload = f"{empresa_db}:{contacto_id}"
    sig = _hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
    return f"{b64}.{sig}"


def verify_unsub_token(token: str) -> tuple[str, int] | None:
    """Returns (empresa_db, contacto_id) or None if invalid."""
    try:
        dot = token.rindex('.')
        b64, sig = token[:dot], token[dot + 1:]
        b64 += '=' * (-len(b64) % 4)
        payload = base64.urlsafe_b64decode(b64).decode()
        expected = _hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not _hmac.compare_digest(sig, expected):
            return None
        colon = payload.rindex(':')
        return payload[:colon], int(payload[colon + 1:])
    except Exception:
        return None


def unsub_url(empresa_db: str, contacto_id: int) -> str:
    from web_app.config import settings
    token = generate_unsub_token(empresa_db, contacto_id)
    base = settings.CRM_BASE_URL.rstrip('/')
    return f"{base}/api/comercial/crm/unsubscribe?token={token}"
