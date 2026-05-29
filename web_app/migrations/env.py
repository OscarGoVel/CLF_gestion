import json
import os
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

target_metadata = None

_BASE = Path(__file__).parent.parent.parent


def _db_url() -> str:
    url = os.environ.get("CLF_MIGRATE_DB_URL", "").strip()
    if url:
        return url
    cfg_path = _BASE / "config.json"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    pg = cfg["postgresql"]
    host = pg.get("host", "localhost")
    port = pg.get("port", 5432)
    user = pg.get("user", "postgres")
    password = pg.get("password", "")
    db = os.environ.get("CLF_MIGRATE_DB", pg.get("database_usuarios", "clf_empresa"))
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def run_migrations_online() -> None:
    engine = create_engine(_db_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
