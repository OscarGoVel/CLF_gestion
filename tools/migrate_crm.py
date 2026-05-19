#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/migrate_crm.py
Crea las tablas crm_* en cada base de datos de empresa.
Es idempotente — seguro de ejecutar múltiples veces (CREATE TABLE IF NOT EXISTS).

Ejecución:
    python tools/migrate_crm.py
"""

import sys
import json
import os
import traceback

import psycopg2

_BASE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_BASE)


def _cfg():
    path = os.path.join(_ROOT, 'config.json')
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            with open(path, 'r', encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise RuntimeError("No se pudo leer config.json")


def _conectar(dbname):
    cfg = _cfg()['postgresql']
    os.environ['PGPASSWORD'] = cfg['password']
    os.environ['PGPASSFILE'] = os.devnull
    return psycopg2.connect(
        host=cfg['host'], port=cfg.get('port', 5432),
        dbname=dbname, user=cfg['user'], password=cfg['password']
    )


def _get_empresas():
    cfg = _cfg()
    return cfg.get('empresas', [])


SCHEMA_CRM = """
CREATE TABLE IF NOT EXISTS crm_contactos (
    id            SERIAL PRIMARY KEY,
    cliente_id    INTEGER NOT NULL REFERENCES clientes(id),
    nombre        TEXT NOT NULL,
    cargo         TEXT,
    email         TEXT NOT NULL,
    telefono      TEXT,
    es_principal  BOOLEAN DEFAULT FALSE,
    opt_out       BOOLEAN DEFAULT FALSE,
    fecha_opt_out TIMESTAMPTZ,
    activo        BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_segmentos (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL,
    descripcion TEXT,
    tipo        TEXT NOT NULL DEFAULT 'manual',
    regla_json  JSONB,
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_segmento_clientes (
    segmento_id  INTEGER REFERENCES crm_segmentos(id) ON DELETE CASCADE,
    cliente_id   INTEGER REFERENCES clientes(id) ON DELETE CASCADE,
    fecha_entrada TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (segmento_id, cliente_id)
);

CREATE TABLE IF NOT EXISTS crm_plantillas (
    id             SERIAL PRIMARY KEY,
    nombre         TEXT NOT NULL,
    categoria      TEXT NOT NULL DEFAULT 'informativo',
    asunto_default TEXT,
    html_body      TEXT NOT NULL DEFAULT '',
    variables_json JSONB DEFAULT '[]',
    activo         BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_campanas (
    id               SERIAL PRIMARY KEY,
    nombre           TEXT NOT NULL,
    asunto           TEXT NOT NULL,
    plantilla_id     INTEGER REFERENCES crm_plantillas(id),
    segmento_id      INTEGER REFERENCES crm_segmentos(id),
    estado           TEXT NOT NULL DEFAULT 'borrador',
    fecha_programada TIMESTAMPTZ,
    fecha_aprobacion TIMESTAMPTZ,
    aprobado_por     INTEGER,
    adjunto_url      TEXT,
    notas            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_secuencias (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL,
    tipo        TEXT NOT NULL DEFAULT 'seguimiento',
    descripcion TEXT,
    activa      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_secuencia_pasos (
    id               SERIAL PRIMARY KEY,
    secuencia_id     INTEGER REFERENCES crm_secuencias(id) ON DELETE CASCADE,
    orden            INTEGER NOT NULL,
    dias_offset      INTEGER NOT NULL DEFAULT 0,
    asunto           TEXT NOT NULL,
    plantilla_id     INTEGER REFERENCES crm_plantillas(id),
    condicion_salida TEXT
);

CREATE TABLE IF NOT EXISTS crm_secuencia_inscripciones (
    id           SERIAL PRIMARY KEY,
    secuencia_id INTEGER REFERENCES crm_secuencias(id),
    cliente_id   INTEGER REFERENCES clientes(id),
    paso_actual  INTEGER DEFAULT 0,
    estado       TEXT NOT NULL DEFAULT 'activa',
    fecha_inicio TIMESTAMPTZ DEFAULT NOW(),
    fecha_fin    TIMESTAMPTZ,
    motivo_fin   TEXT
);

CREATE TABLE IF NOT EXISTS crm_envios (
    id                         SERIAL PRIMARY KEY,
    campana_id                 INTEGER REFERENCES crm_campanas(id),
    secuencia_inscripcion_id   INTEGER REFERENCES crm_secuencia_inscripciones(id),
    contacto_id                INTEGER REFERENCES crm_contactos(id),
    email_destino              TEXT NOT NULL,
    asunto                     TEXT NOT NULL,
    estado                     TEXT NOT NULL DEFAULT 'pendiente',
    proveedor_msg_id           TEXT,
    fecha_programada           TIMESTAMPTZ,
    fecha_envio                TIMESTAMPTZ,
    created_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_envio_eventos (
    id          SERIAL PRIMARY KEY,
    envio_id    INTEGER REFERENCES crm_envios(id) ON DELETE CASCADE,
    tipo        TEXT NOT NULL,
    url_clicada TEXT,
    ip_origen   TEXT,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_rfm_snapshot (
    id            SERIAL PRIMARY KEY,
    cliente_id    INTEGER REFERENCES clientes(id),
    recencia_dias INTEGER,
    frecuencia    INTEGER,
    monto_total   NUMERIC(14,2),
    segmento_rfm  TEXT,
    calculado_en  TIMESTAMPTZ DEFAULT NOW()
);
"""

INDICES_CRM = [
    "CREATE INDEX IF NOT EXISTS idx_crm_contactos_cliente ON crm_contactos(cliente_id)",
    "CREATE INDEX IF NOT EXISTS idx_crm_envios_campana ON crm_envios(campana_id)",
    "CREATE INDEX IF NOT EXISTS idx_crm_envios_estado ON crm_envios(estado)",
    "CREATE INDEX IF NOT EXISTS idx_crm_envios_programada ON crm_envios(fecha_programada)",
    "CREATE INDEX IF NOT EXISTS idx_crm_eventos_envio ON crm_envio_eventos(envio_id)",
    "CREATE INDEX IF NOT EXISTS idx_crm_rfm_cliente ON crm_rfm_snapshot(cliente_id)",
]


def migrar(dbname: str) -> bool:
    print(f"  → Migrando {dbname}...")
    try:
        conn = _conectar(dbname)
        conn.autocommit = False
        cur = conn.cursor()
        try:
            cur.execute(SCHEMA_CRM)
            for idx in INDICES_CRM:
                cur.execute(idx)
            conn.commit()
            print(f"    ✓ tablas crm_* creadas/verificadas en {dbname}")
            return True
        except Exception as e:
            conn.rollback()
            print(f"    ✗ error en {dbname}: {e}")
            traceback.print_exc()
            return False
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"    ✗ no se pudo conectar a {dbname}: {e}")
        return False


def main():
    print("=== Migración CRM — CLF Gestión ===\n")
    empresas = _get_empresas()
    if not empresas:
        print("No se encontraron empresas en config.json")
        sys.exit(1)

    ok = 0
    for emp in empresas:
        db = emp.get('pg_database') or emp.get('empresa_db') or emp.get('db')
        if not db:
            print(f"  ⚠ empresa '{emp.get('nombre', '?')}' sin pg_database, omitida")
            continue
        if migrar(db):
            ok += 1

    print(f"\n✓ {ok}/{len(empresas)} empresas migradas correctamente")


if __name__ == '__main__':
    main()
