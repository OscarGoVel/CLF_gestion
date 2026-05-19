# -*- coding: utf-8 -*-
"""
web_app/routers/api_crm.py
/api/crm — CRM y automatización de marketing.
"""

from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/crm", tags=["crm"])


def _serial(v):
    if isinstance(v, Decimal): return float(v)
    if isinstance(v, datetime): return v.isoformat()
    if hasattr(v, 'isoformat'): return v.isoformat()
    return v


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


def _row(cur) -> dict | None:
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return {k: _serial(v) for k, v in zip(cols, row)}


# ── Contactos ─────────────────────────────────────────────────────────────────

@router.get("/contactos")
async def listar_contactos(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT co.id, co.cliente_id, cl.nombre_comercial,
                   co.nombre, co.cargo, co.email, co.telefono,
                   co.es_principal, co.opt_out, co.activo, co.created_at
            FROM crm_contactos co
            JOIN clientes cl ON cl.id = co.cliente_id
            WHERE co.activo = TRUE
            ORDER BY cl.nombre_comercial, co.nombre
        """)
        return JSONResponse({"contactos": _rows(cur)})


@router.get("/contactos/cliente/{cliente_id}")
async def contactos_de_cliente(cliente_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, nombre, cargo, email, telefono,
                   es_principal, opt_out, activo, created_at
            FROM crm_contactos
            WHERE cliente_id = %s AND activo = TRUE
            ORDER BY es_principal DESC, nombre
        """, (cliente_id,))
        return JSONResponse({"contactos": _rows(cur)})


@router.post("/contactos", status_code=201)
async def crear_contacto(request: Request, user: dict = Depends(get_usuario_api)):
    b = await request.json()
    cliente_id = b.get("cliente_id")
    nombre     = (b.get("nombre") or "").strip()
    email      = (b.get("email") or "").strip()
    if not cliente_id or not nombre or not email:
        raise HTTPException(422, "cliente_id, nombre y email son requeridos")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id FROM clientes WHERE id = %s", (cliente_id,))
        if not cur.fetchone():
            raise HTTPException(404, "cliente no encontrado")

        if b.get("es_principal"):
            cur.execute("""
                UPDATE crm_contactos SET es_principal = FALSE
                WHERE cliente_id = %s
            """, (cliente_id,))

        cur.execute("""
            INSERT INTO crm_contactos
                (cliente_id, nombre, cargo, email, telefono, es_principal)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (cliente_id, nombre, b.get("cargo"), email,
              b.get("telefono"), bool(b.get("es_principal"))))
        nuevo_id = cur.fetchone()[0]

    return JSONResponse({"id": nuevo_id}, status_code=201)


@router.patch("/contactos/{contacto_id}")
async def actualizar_contacto(contacto_id: int, request: Request,
                               user: dict = Depends(get_usuario_api)):
    b = await request.json()
    campos = {}
    for f in ("nombre", "cargo", "email", "telefono", "opt_out", "activo", "es_principal"):
        if f in b:
            campos[f] = b[f]
    if not campos:
        raise HTTPException(422, "sin campos para actualizar")

    sets  = ", ".join(f"{k} = %s" for k in campos)
    vals  = list(campos.values()) + [contacto_id]
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        if b.get("opt_out"):
            cur.execute("UPDATE crm_contactos SET fecha_opt_out = NOW() WHERE id = %s", (contacto_id,))
        cur.execute(f"UPDATE crm_contactos SET {sets} WHERE id = %s", vals)

    return JSONResponse({"ok": True})


# ── Plantillas ────────────────────────────────────────────────────────────────

@router.get("/plantillas")
async def listar_plantillas(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, nombre, categoria, asunto_default,
                   variables_json, activo, created_at, updated_at
            FROM crm_plantillas
            WHERE activo = TRUE
            ORDER BY nombre
        """)
        return JSONResponse({"plantillas": _rows(cur)})


@router.get("/plantillas/{plantilla_id}")
async def obtener_plantilla(plantilla_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, nombre, categoria, asunto_default,
                   html_body, variables_json, activo, created_at, updated_at
            FROM crm_plantillas
            WHERE id = %s
        """, (plantilla_id,))
        row = _row(cur)
    if not row:
        raise HTTPException(404, "plantilla no encontrada")
    return JSONResponse(row)


@router.post("/plantillas", status_code=201)
async def crear_plantilla(request: Request, user: dict = Depends(get_usuario_api)):
    b      = await request.json()
    nombre = (b.get("nombre") or "").strip()
    html   = b.get("html_body", "")
    if not nombre:
        raise HTTPException(422, "nombre requerido")

    from core.crm.plantillas import extraer_variables
    import json
    variables = json.dumps(extraer_variables(html))

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO crm_plantillas
                (nombre, categoria, asunto_default, html_body, variables_json)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id
        """, (nombre, b.get("categoria", "informativo"),
              b.get("asunto_default"), html, variables))
        nuevo_id = cur.fetchone()[0]

    return JSONResponse({"id": nuevo_id}, status_code=201)


@router.patch("/plantillas/{plantilla_id}")
async def actualizar_plantilla(plantilla_id: int, request: Request,
                                user: dict = Depends(get_usuario_api)):
    b = await request.json()
    campos = {}
    for f in ("nombre", "categoria", "asunto_default", "html_body", "activo"):
        if f in b:
            campos[f] = b[f]
    if not campos:
        raise HTTPException(422, "sin campos para actualizar")

    if "html_body" in campos:
        from core.crm.plantillas import extraer_variables
        import json
        campos["variables_json"] = json.dumps(extraer_variables(campos["html_body"]))
        campos["updated_at"] = "NOW()"

    sets = []
    vals = []
    for k, v in campos.items():
        if v == "NOW()":
            sets.append(f"{k} = NOW()")
        elif k == "variables_json":
            sets.append(f"{k} = %s::jsonb")
            vals.append(v)
        else:
            sets.append(f"{k} = %s")
            vals.append(v)

    vals.append(plantilla_id)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"UPDATE crm_plantillas SET {', '.join(sets)} WHERE id = %s", vals)

    return JSONResponse({"ok": True})


@router.post("/plantillas/{plantilla_id}/preview")
async def preview_plantilla(plantilla_id: int, request: Request,
                             user: dict = Depends(get_usuario_api)):
    """Renderiza la plantilla con datos de un cliente para vista previa."""
    b          = await request.json()
    cliente_id = b.get("cliente_id")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT html_body FROM crm_plantillas WHERE id = %s", (plantilla_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "plantilla no encontrada")
        html_body = row[0]

        ctx = {}
        if cliente_id:
            cur.execute("""
                SELECT nombre_comercial, razon_social, contacto, email, telefono, rfc
                FROM clientes WHERE id = %s
            """, (cliente_id,))
            c = cur.fetchone()
            if c:
                cols = [d[0] for d in cur.description]
                ctx  = dict(zip(cols, c))

    from core.crm.plantillas import renderizar, contexto_cliente
    html_rendered = renderizar(html_body, contexto_cliente(ctx))
    return JSONResponse({"html": html_rendered})


# ── Segmentos ─────────────────────────────────────────────────────────────────

@router.get("/segmentos")
async def listar_segmentos(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT s.id, s.nombre, s.descripcion, s.tipo, s.activo,
                   COUNT(sc.cliente_id) AS num_clientes
            FROM crm_segmentos s
            LEFT JOIN crm_segmento_clientes sc ON sc.segmento_id = s.id
            WHERE s.activo = TRUE
            GROUP BY s.id
            ORDER BY s.nombre
        """)
        return JSONResponse({"segmentos": _rows(cur)})


@router.post("/segmentos", status_code=201)
async def crear_segmento(request: Request, user: dict = Depends(get_usuario_api)):
    b      = await request.json()
    nombre = (b.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(422, "nombre requerido")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO crm_segmentos (nombre, descripcion, tipo)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (nombre, b.get("descripcion"), b.get("tipo", "manual")))
        nuevo_id = cur.fetchone()[0]

    return JSONResponse({"id": nuevo_id}, status_code=201)


@router.post("/segmentos/{segmento_id}/clientes")
async def asignar_clientes(segmento_id: int, request: Request,
                            user: dict = Depends(get_usuario_api)):
    b           = await request.json()
    cliente_ids = b.get("cliente_ids", [])
    if not cliente_ids:
        raise HTTPException(422, "cliente_ids requerido")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        for cid in cliente_ids:
            cur.execute("""
                INSERT INTO crm_segmento_clientes (segmento_id, cliente_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (segmento_id, cid))

    return JSONResponse({"ok": True})


@router.delete("/segmentos/{segmento_id}/clientes/{cliente_id}")
async def quitar_cliente_segmento(segmento_id: int, cliente_id: int,
                                   user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            DELETE FROM crm_segmento_clientes
            WHERE segmento_id = %s AND cliente_id = %s
        """, (segmento_id, cliente_id))
    return JSONResponse({"ok": True})


# ── Campañas ──────────────────────────────────────────────────────────────────

@router.get("/campanas")
async def listar_campanas(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT c.id, c.nombre, c.asunto, c.estado,
                   c.fecha_programada, c.fecha_aprobacion,
                   c.notas, c.created_at,
                   p.nombre AS plantilla_nombre,
                   s.nombre AS segmento_nombre,
                   COUNT(DISTINCT e.id)                                 AS total_envios,
                   COUNT(DISTINCT e.id) FILTER (WHERE e.estado='enviado') AS enviados,
                   COUNT(DISTINCT ev.id) FILTER (WHERE ev.tipo='apertura') AS aperturas,
                   COUNT(DISTINCT ev.id) FILTER (WHERE ev.tipo='clic')    AS clics
            FROM crm_campanas c
            LEFT JOIN crm_plantillas p ON p.id = c.plantilla_id
            LEFT JOIN crm_segmentos s  ON s.id = c.segmento_id
            LEFT JOIN crm_envios e     ON e.campana_id = c.id
            LEFT JOIN crm_envio_eventos ev ON ev.envio_id = e.id
            GROUP BY c.id, p.nombre, s.nombre
            ORDER BY c.created_at DESC
        """)
        return JSONResponse({"campanas": _rows(cur)})


@router.post("/campanas", status_code=201)
async def crear_campana(request: Request, user: dict = Depends(get_usuario_api)):
    b      = await request.json()
    nombre = (b.get("nombre") or "").strip()
    asunto = (b.get("asunto") or "").strip()
    if not nombre or not asunto:
        raise HTTPException(422, "nombre y asunto son requeridos")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO crm_campanas
                (nombre, asunto, plantilla_id, segmento_id,
                 fecha_programada, notas)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (nombre, asunto,
              b.get("plantilla_id"), b.get("segmento_id"),
              b.get("fecha_programada"), b.get("notas")))
        nuevo_id = cur.fetchone()[0]

    return JSONResponse({"id": nuevo_id}, status_code=201)


@router.patch("/campanas/{campana_id}")
async def actualizar_campana(campana_id: int, request: Request,
                              user: dict = Depends(get_usuario_api)):
    b = await request.json()
    campos = {}
    for f in ("nombre", "asunto", "plantilla_id", "segmento_id",
              "estado", "fecha_programada", "notas", "adjunto_url"):
        if f in b:
            campos[f] = b[f]

    if b.get("estado") == "aprobada":
        campos["fecha_aprobacion"] = None
        campos["aprobado_por"]     = int(user.get("sub", 0))

    if not campos:
        raise HTTPException(422, "sin campos para actualizar")

    sets = []
    vals = []
    for k, v in campos.items():
        if k == "fecha_aprobacion" and v is None:
            sets.append(f"{k} = NOW()")
        else:
            sets.append(f"{k} = %s")
            vals.append(v)

    vals.append(campana_id)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"UPDATE crm_campanas SET {', '.join(sets)} WHERE id = %s", vals)

    return JSONResponse({"ok": True})


@router.post("/campanas/{campana_id}/enviar")
async def enviar_campana(campana_id: int, background: BackgroundTasks,
                          user: dict = Depends(get_usuario_api)):
    """
    Genera los registros crm_envios para cada contacto del segmento
    y los encola con estado=pendiente para que el scheduler los procese.
    """
    db = user["empresa_db"]
    with get_pool_empresa(db).conexion() as (_, cur):
        cur.execute("""
            SELECT c.id, c.asunto, c.plantilla_id, c.segmento_id, c.estado,
                   c.fecha_programada
            FROM crm_campanas c
            WHERE c.id = %s
        """, (campana_id,))
        camp = _row(cur)

    if not camp:
        raise HTTPException(404, "campaña no encontrada")
    if camp["estado"] not in ("aprobada", "borrador"):
        raise HTTPException(409, f"estado actual es '{camp['estado']}', no se puede enviar")

    with get_pool_empresa(db).conexion() as (_, cur):
        if camp["segmento_id"]:
            cur.execute("""
                SELECT co.id, co.email, cl.nombre_comercial, cl.contacto
                FROM crm_segmento_clientes sc
                JOIN crm_contactos co
                     ON co.cliente_id = sc.cliente_id
                    AND co.opt_out = FALSE AND co.activo = TRUE
                JOIN clientes cl ON cl.id = co.cliente_id
                WHERE sc.segmento_id = %s
            """, (camp["segmento_id"],))
        else:
            cur.execute("""
                SELECT co.id, co.email, cl.nombre_comercial, cl.contacto
                FROM crm_contactos co
                JOIN clientes cl ON cl.id = co.cliente_id
                WHERE co.opt_out = FALSE AND co.activo = TRUE
            """)
        contactos = _rows(cur)

    if not contactos:
        raise HTTPException(422, "no hay contactos activos en el segmento")

    fecha_prog = camp.get("fecha_programada") or "NOW()"
    with get_pool_empresa(db).conexion() as (_, cur):
        for c in contactos:
            cur.execute("""
                INSERT INTO crm_envios
                    (campana_id, contacto_id, email_destino, asunto,
                     estado, fecha_programada)
                VALUES (%s, %s, %s, %s, 'pendiente', %s)
            """, (campana_id, c["id"], c["email"],
                  camp["asunto"],
                  None if fecha_prog == "NOW()" else fecha_prog))

        cur.execute("""
            UPDATE crm_campanas SET estado = 'enviando' WHERE id = %s
        """, (campana_id,))

    return JSONResponse({"ok": True, "envios_generados": len(contactos)})


# ── Secuencias ────────────────────────────────────────────────────────────────

@router.get("/secuencias")
async def listar_secuencias(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT s.id, s.nombre, s.tipo, s.descripcion, s.activa,
                   COUNT(p.id) AS num_pasos,
                   COUNT(i.id) FILTER (WHERE i.estado='activa') AS inscritos_activos
            FROM crm_secuencias s
            LEFT JOIN crm_secuencia_pasos p ON p.secuencia_id = s.id
            LEFT JOIN crm_secuencia_inscripciones i ON i.secuencia_id = s.id
            GROUP BY s.id
            ORDER BY s.nombre
        """)
        return JSONResponse({"secuencias": _rows(cur)})


@router.get("/secuencias/{secuencia_id}")
async def obtener_secuencia(secuencia_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM crm_secuencias WHERE id = %s", (secuencia_id,))
        sec = _row(cur)
        if not sec:
            raise HTTPException(404, "secuencia no encontrada")

        cur.execute("""
            SELECT p.id, p.orden, p.dias_offset, p.asunto,
                   p.condicion_salida, pt.nombre AS plantilla_nombre
            FROM crm_secuencia_pasos p
            LEFT JOIN crm_plantillas pt ON pt.id = p.plantilla_id
            WHERE p.secuencia_id = %s
            ORDER BY p.orden
        """, (secuencia_id,))
        sec["pasos"] = _rows(cur)

    return JSONResponse(sec)


@router.post("/secuencias", status_code=201)
async def crear_secuencia(request: Request, user: dict = Depends(get_usuario_api)):
    b      = await request.json()
    nombre = (b.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(422, "nombre requerido")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO crm_secuencias (nombre, tipo, descripcion)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (nombre, b.get("tipo", "seguimiento"), b.get("descripcion")))
        sec_id = cur.fetchone()[0]

        for paso in b.get("pasos", []):
            cur.execute("""
                INSERT INTO crm_secuencia_pasos
                    (secuencia_id, orden, dias_offset, asunto,
                     plantilla_id, condicion_salida)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sec_id, paso["orden"], paso.get("dias_offset", 0),
                  paso["asunto"], paso.get("plantilla_id"),
                  paso.get("condicion_salida")))

    return JSONResponse({"id": sec_id}, status_code=201)


@router.post("/secuencias/{secuencia_id}/inscribir")
async def inscribir_cliente(secuencia_id: int, request: Request,
                             user: dict = Depends(get_usuario_api)):
    b           = await request.json()
    cliente_ids = b.get("cliente_ids", [])
    if not cliente_ids:
        raise HTTPException(422, "cliente_ids requerido")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        for cid in cliente_ids:
            cur.execute("""
                INSERT INTO crm_secuencia_inscripciones
                    (secuencia_id, cliente_id)
                VALUES (%s, %s)
            """, (secuencia_id, cid))

    return JSONResponse({"ok": True, "inscritos": len(cliente_ids)})


# ── RFM / Dashboard ──────────────────────────────────────────────────────────

@router.get("/rfm")
async def obtener_rfm(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT r.cliente_id, cl.nombre_comercial,
                   r.recencia_dias, r.frecuencia, r.monto_total,
                   r.segmento_rfm, r.calculado_en
            FROM crm_rfm_snapshot r
            JOIN clientes cl ON cl.id = r.cliente_id
            ORDER BY r.segmento_rfm, r.monto_total DESC
        """)
        rows = _rows(cur)

        cur.execute("""
            SELECT segmento_rfm, COUNT(*) AS total
            FROM crm_rfm_snapshot
            GROUP BY segmento_rfm
        """)
        distribucion = {r[0]: r[1] for r in cur.fetchall()}

    return JSONResponse({"clientes": rows, "distribucion": distribucion})


@router.post("/rfm/recalcular")
async def recalcular_rfm(user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador",):
        raise HTTPException(403, "solo Administrador puede recalcular RFM")

    db = user["empresa_db"]
    with get_pool_empresa(db).conexion() as (_, cur):
        from core.crm.segmentacion import calcular_rfm, guardar_rfm_snapshot
        rows = calcular_rfm(cur)
        guardar_rfm_snapshot(cur, rows)

    return JSONResponse({"ok": True, "clientes_calculados": len(rows)})


@router.get("/dashboard")
async def dashboard_crm(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT
                COUNT(*)                              AS total_contactos,
                COUNT(*) FILTER (WHERE opt_out=TRUE)  AS opt_outs
            FROM crm_contactos WHERE activo = TRUE
        """)
        r = cur.fetchone()
        contactos_stats = {"total": r[0], "opt_outs": r[1]}

        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE estado='borrador')    AS borradores,
                COUNT(*) FILTER (WHERE estado='aprobada')    AS aprobadas,
                COUNT(*) FILTER (WHERE estado='enviando')    AS enviando,
                COUNT(*) FILTER (WHERE estado='completada')  AS completadas
            FROM crm_campanas
        """)
        r = cur.fetchone()
        campanas_stats = {
            "borradores": r[0], "aprobadas": r[1],
            "enviando": r[2], "completadas": r[3],
        }

        cur.execute("""
            SELECT
                COUNT(*)                                              AS total_envios,
                COUNT(*) FILTER (WHERE e.estado='enviado')           AS enviados,
                COUNT(DISTINCT ev.id) FILTER (WHERE ev.tipo='apertura') AS aperturas,
                COUNT(DISTINCT ev.id) FILTER (WHERE ev.tipo='clic')     AS clics,
                COUNT(DISTINCT ev.id) FILTER (WHERE ev.tipo='rebote')   AS rebotes
            FROM crm_envios e
            LEFT JOIN crm_envio_eventos ev ON ev.envio_id = e.id
            WHERE e.created_at >= CURRENT_DATE - INTERVAL '30 days'
        """)
        r   = cur.fetchone()
        enviados = r[1] or 0
        metricas_30d = {
            "total_envios": r[0], "enviados": enviados,
            "aperturas":    r[2], "clics":    r[3], "rebotes": r[4],
            "tasa_apertura": round(r[2] / enviados * 100, 1) if enviados else 0,
            "tasa_clics":    round(r[3] / enviados * 100, 1) if enviados else 0,
        }

        cur.execute("""
            SELECT segmento_rfm, COUNT(*) AS total
            FROM crm_rfm_snapshot
            GROUP BY segmento_rfm
            ORDER BY total DESC
        """)
        distribucion_rfm = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("""
            SELECT c.id, c.nombre, c.estado, c.fecha_programada,
                   COUNT(e.id) AS envios,
                   COUNT(ev.id) FILTER (WHERE ev.tipo='apertura') AS aperturas,
                   COUNT(ev.id) FILTER (WHERE ev.tipo='clic')     AS clics
            FROM crm_campanas c
            LEFT JOIN crm_envios e ON e.campana_id = c.id
            LEFT JOIN crm_envio_eventos ev ON ev.envio_id = e.id
            WHERE c.created_at >= CURRENT_DATE - INTERVAL '60 days'
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT 10
        """)
        campanas_recientes = _rows(cur)

    return JSONResponse({
        "contactos":        contactos_stats,
        "campanas":         campanas_stats,
        "metricas_30d":     metricas_30d,
        "distribucion_rfm": distribucion_rfm,
        "campanas_recientes": campanas_recientes,
    })


# ── Webhook SendGrid ──────────────────────────────────────────────────────────

@router.post("/webhook/sendgrid")
async def webhook_sendgrid(request: Request):
    """
    Recibe eventos de SendGrid (apertura, clic, rebote, unsubscribe).
    No requiere autenticación JWT — usa verificación de IP/secreto opcional.
    """
    try:
        eventos = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)

    _TIPO_MAP = {
        "open":        "apertura",
        "click":       "clic",
        "bounce":      "rebote",
        "unsubscribe": "unsubscribe",
        "spamreport":  "unsubscribe",
    }

    from web_app.database import get_pool_empresa, get_empresas
    for evento in (eventos if isinstance(eventos, list) else [eventos]):
        msg_id = evento.get("sg_message_id", "").split(".")[0]
        tipo_sg = evento.get("event", "")
        tipo    = _TIPO_MAP.get(tipo_sg)
        if not tipo or not msg_id:
            continue

        for emp in get_empresas():
            db = emp.get("pg_database") or emp.get("empresa_db") or emp.get("db")
            if not db:
                continue
            try:
                with get_pool_empresa(db).conexion() as (_, cur):
                    cur.execute("""
                        SELECT id FROM crm_envios
                        WHERE proveedor_msg_id = %s
                        LIMIT 1
                    """, (msg_id,))
                    row = cur.fetchone()
                    if not row:
                        continue
                    envio_id = row[0]
                    cur.execute("""
                        INSERT INTO crm_envio_eventos
                            (envio_id, tipo, url_clicada, ip_origen, user_agent)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (envio_id, tipo,
                          evento.get("url"),
                          evento.get("ip"),
                          evento.get("useragent")))

                    if tipo == "unsubscribe":
                        cur.execute("""
                            UPDATE crm_contactos
                            SET opt_out = TRUE, fecha_opt_out = NOW()
                            WHERE email = %s
                        """, (evento.get("email"),))
                break
            except Exception:
                continue

    return JSONResponse({"ok": True})
