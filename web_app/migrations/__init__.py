# -*- coding: utf-8 -*-
"""
web_app/migrations/__init__.py
Runner de migraciones Alembic para CLF Gestión.

Uso desde main.py:
    from web_app.migrations import aplicar_migraciones, build_db_url
    aplicar_migraciones(build_db_url("clf_empresa"), log)
"""

import os
import urllib.parse
from pathlib import Path

from alembic.config import Config
from alembic import command

_MIGRATIONS_DIR = Path(__file__).parent


def build_db_url(dbname: str) -> str:
    password  = os.environ.get("CLF_PG_PASSWORD", "")
    user      = os.environ.get("CLF_PG_USER", "postgres")
    cloud_sql = os.environ.get("CLF_CLOUD_SQL_INSTANCE", "").strip()
    pw_enc    = urllib.parse.quote_plus(password)

    if cloud_sql:
        socket = f"/cloudsql/{cloud_sql}"
        return f"postgresql+psycopg2://{user}:{pw_enc}@/{dbname}?host={socket}"

    host = os.environ.get("CLF_PG_HOST", "localhost")
    port = int(os.environ.get("CLF_PG_PORT", "5432"))
    return f"postgresql+psycopg2://{user}:{pw_enc}@{host}:{port}/{dbname}"


def _make_cfg(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("version_table", "alembic_version")
    return cfg


def aplicar_migraciones(db_url: str, log=None) -> None:
    """Aplica todas las migraciones pendientes a la base de datos indicada."""
    try:
        command.upgrade(_make_cfg(db_url), "head")
        if log:
            log.info(f"Migraciones aplicadas: {db_url.split('@')[-1]}")
    except Exception as e:
        if log:
            log.error(f"Error en migraciones ({db_url.split('@')[-1]}): {e}")
        raise
