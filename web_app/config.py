# -*- coding: utf-8 -*-
"""
web_app/config.py
Configuracion centralizada leida desde el archivo .env en la raiz del proyecto.
Si una variable no existe en .env se usa el valor por defecto.

Variables disponibles en .env:
    CLF_SECRET_KEY   → clave secreta JWT (OBLIGATORIA en produccion)
    CLF_HOST         → interfaz de escucha (default: 0.0.0.0)
    CLF_PORT         → puerto HTTP  (default: 8000)
    CLF_HTTPS_PORT   → puerto HTTPS (default: 8443)
    CLF_SSL_CERT     → ruta al certificado SSL (default: ssl/server.crt)
    CLF_SSL_KEY      → ruta a la clave privada SSL (default: ssl/server.key)
    CLF_ENV          → "development" | "production" (default: development)
"""

import os
import secrets
from pathlib import Path

# Cargar .env si existe
_ROOT = Path(__file__).parent.parent
_ENV_FILE = _ROOT / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE)
except ImportError:
    pass


class Settings:
    # Seguridad
    SECRET_KEY:   str = os.environ.get("CLF_SECRET_KEY", "")
    ENVIRONMENT:  str = os.environ.get("CLF_ENV", "development")

    # CRM / Email
    SENDGRID_API_KEY: str = os.environ.get("SENDGRID_API_KEY", "")
    CRM_FROM_EMAIL:   str = os.environ.get("CRM_FROM_EMAIL", "noreply@logos-gestion.web.app")
    CRM_FROM_NAME:    str = os.environ.get("CRM_FROM_NAME",  "LOGOS")
    CRM_BASE_URL:     str = os.environ.get("CRM_BASE_URL",   "https://logos-gestion.web.app")

    # Almacenamiento Cloud (XMLs de facturas)
    GCS_XML_BUCKET: str = os.environ.get("GCS_XML_BUCKET", "")

    # Red
    HOST:       str = os.environ.get("CLF_HOST", "0.0.0.0")
    PORT:       int = int(os.environ.get("CLF_PORT", "8000"))
    HTTPS_PORT: int = int(os.environ.get("CLF_HTTPS_PORT", "8443"))

    # SSL
    SSL_CERT: str = os.environ.get("CLF_SSL_CERT", str(_ROOT / "ssl" / "server.crt"))
    SSL_KEY:  str = os.environ.get("CLF_SSL_KEY",  str(_ROOT / "ssl" / "server.key"))

    def __init__(self):
        # Clave de desarrollo fija por sesión — se genera una sola vez al arrancar
        self._dev_secret = "dev-" + secrets.token_hex(32)

    @property
    def es_produccion(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def secret_key_efectiva(self) -> str:
        """Retorna el SECRET_KEY. En desarrollo genera uno fijo por sesión si no hay."""
        if self.SECRET_KEY:
            return self.SECRET_KEY
        if self.es_produccion:
            raise RuntimeError(
                "CLF_SECRET_KEY no configurada. "
                "Agrega CLF_SECRET_KEY=<valor-seguro> al archivo .env"
            )
        return self._dev_secret

    @property
    def ssl_disponible(self) -> bool:
        return Path(self.SSL_CERT).exists() and Path(self.SSL_KEY).exists()


settings = Settings()
