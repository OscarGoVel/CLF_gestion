# -*- coding: utf-8 -*-
"""
core/crm/scheduler.py
APScheduler para procesar envíos CRM programados.
Se inicializa desde el lifespan de FastAPI (main.py).
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

_log = logging.getLogger('clf.crm.scheduler')
_scheduler: AsyncIOScheduler | None = None


def iniciar(pool_fn, empresas_fn) -> AsyncIOScheduler:
    """
    Inicia el scheduler.  Recibe callables para no crear dependencias circulares:
      pool_fn(db)     → pool de empresa
      empresas_fn()   → lista de empresas
    """
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone='America/Merida')

    _scheduler.add_job(
        _procesar_envios_pendientes,
        'interval',
        minutes=5,
        id='crm_envios',
        args=[pool_fn, empresas_fn],
        next_run_time=datetime.now(timezone.utc),
    )

    _scheduler.add_job(
        _avanzar_secuencias,
        'cron',
        hour=7, minute=0,
        id='crm_secuencias',
        args=[pool_fn, empresas_fn],
    )

    _scheduler.add_job(
        _recalcular_rfm,
        'cron',
        hour=3, minute=0,
        id='crm_rfm_diario',
        args=[pool_fn, empresas_fn],
    )

    _scheduler.start()
    _log.info("CRM scheduler iniciado")
    return _scheduler


def detener():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _log.info("CRM scheduler detenido")


async def _procesar_envios_pendientes(pool_fn, empresas_fn):
    from core.crm.envios import enviar_correo
    from core.crm.plantillas import renderizar, contexto_cliente

    for emp in empresas_fn():
        db = emp.get('pg_database') or emp.get('empresa_db') or emp.get('db')
        if not db:
            continue
        try:
            with pool_fn(db).conexion() as (_, cur):
                cur.execute("""
                    SELECT e.id, e.contacto_id, e.email_destino, e.asunto,
                           ct.contacto, ct.nombre_comercial,
                           p.html_body
                    FROM crm_envios e
                    LEFT JOIN crm_campanas c   ON c.id = e.campana_id
                    LEFT JOIN crm_plantillas p ON p.id = c.plantilla_id
                    LEFT JOIN crm_contactos co ON co.id = e.contacto_id
                    LEFT JOIN clientes ct      ON ct.id = co.cliente_id
                    WHERE e.estado = 'pendiente'
                      AND (e.fecha_programada IS NULL OR e.fecha_programada <= NOW())
                    ORDER BY e.fecha_programada NULLS FIRST
                    LIMIT 50
                """)
                cols  = [d[0] for d in cur.description]
                filas = [dict(zip(cols, r)) for r in cur.fetchall()]

            for fila in filas:
                from core.crm.tokens import unsub_url
                ctx  = {'nombre_comercial': fila.get('nombre_comercial', ''),
                        'contacto':         fila.get('contacto', ''),
                        'unsubscribe_url':  unsub_url(db, fila['contacto_id'])}
                html = renderizar(fila.get('html_body') or '', ctx)
                ok, msg_id = enviar_correo(
                    to_email=fila['email_destino'],
                    to_name=fila.get('contacto') or fila['email_destino'],
                    subject=fila['asunto'],
                    html_content=html,
                )
                nuevo_estado = 'enviado' if ok else 'fallido'
                with pool_fn(db).conexion() as (_, cur):
                    cur.execute("""
                        UPDATE crm_envios
                        SET estado = %s, proveedor_msg_id = %s, fecha_envio = NOW()
                        WHERE id = %s
                    """, (nuevo_estado, msg_id, fila['id']))

        except Exception as exc:
            _log.error("Error procesando envíos de %s: %s", db, exc)


async def _avanzar_secuencias(pool_fn, empresas_fn):
    """Evalúa inscripciones activas y genera envíos para el siguiente paso."""
    from core.crm.envios import enviar_correo
    from core.crm.plantillas import renderizar

    for emp in empresas_fn():
        db = emp.get('pg_database') or emp.get('empresa_db') or emp.get('db')
        if not db:
            continue
        try:
            with pool_fn(db).conexion() as (_, cur):
                cur.execute("""
                    SELECT i.id, i.secuencia_id, i.cliente_id, i.paso_actual,
                           sp.id AS paso_id, sp.orden, sp.dias_offset,
                           sp.asunto, sp.plantilla_id, sp.condicion_salida,
                           cl.nombre_comercial, cl.contacto,
                           co.email AS contacto_email, co.id AS contacto_id
                    FROM crm_secuencia_inscripciones i
                    JOIN crm_secuencia_pasos sp
                         ON sp.secuencia_id = i.secuencia_id
                        AND sp.orden = i.paso_actual + 1
                    JOIN clientes cl ON cl.id = i.cliente_id
                    LEFT JOIN crm_contactos co
                           ON co.cliente_id = i.cliente_id
                          AND co.es_principal = TRUE
                          AND co.opt_out = FALSE
                          AND co.activo = TRUE
                    WHERE i.estado = 'activa'
                      AND i.fecha_inicio + (sp.dias_offset || ' days')::INTERVAL <= NOW()
                    ORDER BY i.id
                """)
                cols  = [d[0] for d in cur.description]
                filas = [dict(zip(cols, r)) for r in cur.fetchall()]

            for fila in filas:
                email_dest = fila.get('contacto_email')
                if not email_dest:
                    continue

                with pool_fn(db).conexion() as (_, cur):
                    cur.execute("""
                        INSERT INTO crm_envios
                            (secuencia_inscripcion_id, contacto_id,
                             email_destino, asunto, estado, fecha_programada)
                        VALUES (%s, %s, %s, %s, 'pendiente', NOW())
                    """, (fila['id'], fila['contacto_id'],
                          email_dest, fila['asunto']))

                    cur.execute("""
                        UPDATE crm_secuencia_inscripciones
                        SET paso_actual = %s
                        WHERE id = %s
                    """, (fila['orden'], fila['id']))

                    cur.execute("""
                        SELECT COUNT(*) FROM crm_secuencia_pasos
                        WHERE secuencia_id = %s AND orden > %s
                    """, (fila['secuencia_id'], fila['orden']))
                    hay_mas = cur.fetchone()[0] > 0

                    if not hay_mas:
                        cur.execute("""
                            UPDATE crm_secuencia_inscripciones
                            SET estado = 'completada', fecha_fin = NOW(),
                                motivo_fin = 'secuencia_completada'
                            WHERE id = %s
                        """, (fila['id'],))

        except Exception as exc:
            _log.error("Error avanzando secuencias de %s: %s", db, exc)


async def _recalcular_rfm(pool_fn, empresas_fn):
    """
    Recalcula el snapshot RFM diariamente.
    Detecta clientes que pasan a 'At Risk' e inscribe automáticamente
    en la primera secuencia activa de tipo 'reactivacion'.
    """
    from core.crm.segmentacion import calcular_rfm, guardar_rfm_snapshot

    for emp in empresas_fn():
        db = emp.get('pg_database') or emp.get('empresa_db') or emp.get('db')
        if not db:
            continue
        try:
            with pool_fn(db).conexion() as (_, cur):
                # Leer snapshot anterior
                cur.execute("""
                    SELECT cliente_id, segmento_rfm
                    FROM crm_rfm_snapshot
                """)
                anterior = {r[0]: r[1] for r in cur.fetchall()}

                # Calcular nuevo RFM
                nuevos = calcular_rfm(cur)
                guardar_rfm_snapshot(cur, nuevos)

                # Detectar transiciones → At Risk
                at_risk_nuevos = [
                    r['cliente_id'] for r in nuevos
                    if r['segmento_rfm'] == 'At Risk'
                    and anterior.get(r['cliente_id']) not in ('At Risk', 'Lost')
                ]

                if not at_risk_nuevos:
                    _log.info("RFM recalculado para %s — sin nuevos At Risk", db)
                    continue

                # Buscar secuencia de reactivación activa
                cur.execute("""
                    SELECT id FROM crm_secuencias
                    WHERE tipo = 'reactivacion' AND activa = TRUE
                    ORDER BY id LIMIT 1
                """)
                sec_row = cur.fetchone()
                if not sec_row:
                    _log.info("RFM: %d nuevos At Risk en %s, sin secuencia reactivacion", len(at_risk_nuevos), db)
                    continue

                sec_id = sec_row[0]
                inscritos = 0
                for cid in at_risk_nuevos:
                    # No re-inscribir si ya está activo en esta secuencia
                    cur.execute("""
                        SELECT id FROM crm_secuencia_inscripciones
                        WHERE secuencia_id = %s AND cliente_id = %s
                          AND estado = 'activa'
                    """, (sec_id, cid))
                    if cur.fetchone():
                        continue
                    cur.execute("""
                        INSERT INTO crm_secuencia_inscripciones
                            (secuencia_id, cliente_id, origen)
                        VALUES (%s, %s, 'rfm_at_risk')
                    """, (sec_id, cid))
                    inscritos += 1

                _log.info("RFM %s: %d nuevos At Risk, %d inscritos en secuencia %d", db, len(at_risk_nuevos), inscritos, sec_id)

        except Exception as exc:
            _log.error("Error recalculando RFM de %s: %s", db, exc)
