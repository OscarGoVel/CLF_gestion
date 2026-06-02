# -*- coding: utf-8 -*-
"""
web_app/routers/api_cotizaciones.py
/api/cotizaciones — endpoints JSON para el SPA React.
Coexiste con el router HTML legacy en cotizaciones.py.
"""

import csv
import io
import json
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api
from web_app.historial import log_evento
from core.constants import ESTADOS_COTIZACION as ESTADOS, formato_folio

router = APIRouter(prefix="/api/comercial/cotizaciones", tags=["api"])

POR_PAGINA = 25


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serial(v):
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


def _generar_folio_en_tx(cur, año: int) -> str:
    cur.execute("SELECT pg_advisory_xact_lock(hashtext('folio_cotizacion'))")
    cur.execute(
        "SELECT COALESCE(MAX(CAST(SPLIT_PART(folio, '-', 3) AS INTEGER)), 0) + 1 "
        "FROM cotizaciones WHERE folio LIKE %s",
        (f"COT-{año}-%",),
    )
    return formato_folio(año, cur.fetchone()[0])


# ── Pydantic models ───────────────────────────────────────────────────────────

class PartidaIn(BaseModel):
    producto_id: Optional[int] = None
    descripcion_libre: Optional[str] = None
    cantidad: float
    precio_unitario: float
    aplica_iva: bool = False


class CotizacionIn(BaseModel):
    cliente_id: int
    comprador_id: Optional[int] = None
    fecha: str
    orden_compra: Optional[str] = None
    notas: Optional[str] = None
    utilidad_pct: float = 0.0
    partidas: List[PartidaIn]
    razon_social_id: Optional[int] = None


# ── GET /api/cotizaciones ─────────────────────────────────────────────────────

@router.get("")
async def listar(
    estado: List[str] = Query([]),
    cliente_id: List[int] = Query([]),
    q: str = Query(""),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    pagina: int = Query(1, ge=1),
    razon_social_id: Optional[int] = Query(None),
    user: dict = Depends(get_usuario_api),
):
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso a cotizaciones")

    empresa_db = user["empresa_db"]
    clauses, params = [], []
    if razon_social_id is not None:
        clauses.append("c.razon_social_id = %s")
        params.append(razon_social_id)
    if estado:
        placeholders = ",".join(["%s"] * len(estado))
        clauses.append(f"c.estado IN ({placeholders})")
        params.extend(estado)
    if cliente_id:
        placeholders = ",".join(["%s"] * len(cliente_id))
        clauses.append(f"c.cliente_id IN ({placeholders})")
        params.extend(cliente_id)
    if fecha_desde:
        clauses.append("c.fecha >= %s")
        params.append(fecha_desde)
    if fecha_hasta:
        clauses.append("c.fecha <= %s")
        params.append(fecha_hasta)
    if q:
        clauses.append("(c.folio ILIKE %s OR COALESCE(cl.nombre_comercial,'') ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    offset = (pagina - 1) * POR_PAGINA

    sql = f"""
        SELECT c.id, c.folio, c.fecha,
               COALESCE(cl.nombre_comercial, '—') AS cliente,
               cl.tipo                             AS tipo_cliente,
               c.total, c.estado,
               c.orden_compra, c.numero_factura,
               COUNT(cd.id)                        AS num_productos,
               EXISTS(
                   SELECT 1 FROM compra_detalle_cotizacion cdc
                   WHERE cdc.cotizacion_id = c.id
               )                                   AS tiene_costo_real,
               COALESCE(rs.nombre, '—')            AS razon_social_nombre
        FROM cotizaciones c
        LEFT JOIN clientes          cl ON cl.id = c.cliente_id
        LEFT JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
        LEFT JOIN razones_sociales  rs ON rs.id = c.razon_social_id
        {where}
        GROUP BY c.id, cl.nombre_comercial, cl.tipo, rs.nombre
        ORDER BY c.fecha DESC, c.id DESC
        LIMIT {POR_PAGINA} OFFSET {offset}
    """
    count_sql = f"""
        SELECT COUNT(DISTINCT c.id)
        FROM cotizaciones c
        LEFT JOIN clientes cl ON cl.id = c.cliente_id
        {where}
    """

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(sql, params or None)
        rows = _rows(cur)

        cur.execute(count_sql, params or None)
        total = cur.fetchone()[0]

        cur.execute("SELECT estado, COUNT(*) FROM cotizaciones GROUP BY estado")
        conteo_estado = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("""
            SELECT DISTINCT cl.id, cl.nombre_comercial
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            ORDER BY cl.nombre_comercial
        """)
        clientes_lista = [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]

    total_pags = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)

    return JSONResponse({
        "cotizaciones": rows,
        "total": total,
        "pagina": pagina,
        "total_pags": total_pags,
        "conteo_estado": conteo_estado,
        "clientes": clientes_lista,
    })


# ── Helpers internos ─────────────────────────────────────────────────────────

def _resolver_costo_entrega(cur, cot_id: int, prod_id: int) -> tuple:
    """Retorna (costo, tipo) para un producto al momento de marcar Entregada.
    Prioridad: compra asignada → costo promedio del producto → snapshot catálogo."""
    cur.execute("""
        SELECT SUM(comp.costo_unitario * cdc.cantidad) / NULLIF(SUM(cdc.cantidad), 0)
        FROM compra_detalle_cotizacion cdc
        JOIN compra_detalle comp ON comp.id = cdc.compra_detalle_id
        WHERE cdc.cotizacion_id = %s AND comp.producto_id = %s
    """, (cot_id, prod_id))
    r = cur.fetchone()[0]
    if r:
        return float(r), 'compra_directa'
    cur.execute("SELECT COALESCE(costo_promedio, 0) FROM productos WHERE id = %s", (prod_id,))
    prom = float(cur.fetchone()[0] or 0)
    if prom > 0:
        return prom, 'promedio'
    cur.execute(
        "SELECT costo_snapshot FROM cotizacion_detalle WHERE cotizacion_id = %s AND producto_id = %s",
        (cot_id, prod_id),
    )
    snap_row = cur.fetchone()
    snap = float(snap_row[0] or 0) if snap_row else 0
    return snap, 'catalogo'


# ── PATCH /api/cotizaciones/{cot_id}/estado ───────────────────────────────────

class EstadoIn(BaseModel):
    nuevo_estado: str
    fecha_entrega: Optional[str] = None
    fecha_pago: Optional[str] = None
    monto_pagado: Optional[float] = None
    numero_factura: Optional[str] = None
    orden_compra: Optional[str] = None


@router.patch("/{cot_id}/estado")
async def cambiar_estado(cot_id: int, body: EstadoIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso para cambiar estado")
    if body.nuevo_estado == "Pagada" and user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo el Administrador puede marcar como Pagada")
    if body.nuevo_estado not in ESTADOS:
        raise HTTPException(status_code=400, detail="Estado no válido")

    empresa_db = user["empresa_db"]

    if body.nuevo_estado == "Pagada":
        if not body.monto_pagado or body.monto_pagado <= 0:
            with get_pool_empresa(empresa_db).conexion() as (_, cur):
                cur.execute("SELECT COALESCE(monto_pagado, 0) FROM cotizaciones WHERE id = %s", (cot_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Cotización no encontrada")
                if float(row[0]) <= 0:
                    raise HTTPException(
                        status_code=422,
                        detail="Registra el monto pagado antes de marcar la cotización como Pagada.",
                    )

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            UPDATE cotizaciones SET
                estado         = %s,
                fecha_entrega  = COALESCE(%s::date,     fecha_entrega),
                fecha_pago     = COALESCE(%s::date,     fecha_pago),
                monto_pagado   = COALESCE(%s::numeric,  monto_pagado),
                numero_factura = COALESCE(NULLIF(%s,''), numero_factura),
                orden_compra   = COALESCE(NULLIF(%s,''), orden_compra)
            WHERE id = %s
        """, (
            body.nuevo_estado,
            body.fecha_entrega or None, body.fecha_pago or None,
            body.monto_pagado,
            body.numero_factura or '', body.orden_compra or '',
            cot_id,
        ))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")

        if body.nuevo_estado == "Entregada":
            cur.execute("SELECT folio FROM cotizaciones WHERE id = %s", (cot_id,))
            folio_cot = cur.fetchone()[0]

            cur.execute("""
                SELECT cd.producto_id, cd.cantidad,
                       COALESCE(SUM(ep.cantidad_entregada), 0) AS ya_entregado
                FROM cotizacion_detalle cd
                LEFT JOIN entregas_parciales ep
                       ON ep.cotizacion_id = cd.cotizacion_id
                      AND ep.producto_id   = cd.producto_id
                WHERE cd.cotizacion_id = %s AND cd.producto_id IS NOT NULL
                GROUP BY cd.producto_id, cd.cantidad
            """, (cot_id,))
            lineas = cur.fetchall()

            faltantes = []
            for prod_id, cant_total, ya_entregado in lineas:
                pendiente = float(cant_total) - float(ya_entregado)
                if pendiente <= 0:
                    continue
                cur.execute(
                    "SELECT COALESCE(stock_actual,0), nombre FROM productos WHERE id=%s", (prod_id,)
                )
                stock_row = cur.fetchone()
                if stock_row and float(stock_row[0]) < pendiente:
                    faltantes.append(stock_row[1] or f"producto #{prod_id}")
            if faltantes:
                raise HTTPException(
                    status_code=422,
                    detail=f"Stock insuficiente para: {', '.join(faltantes)}",
                )

            for prod_id, cant_total, ya_entregado in lineas:
                pendiente = float(cant_total) - float(ya_entregado)
                if pendiente <= 0:
                    continue
                cur.execute("SELECT COALESCE(stock_actual,0) FROM productos WHERE id=%s", (prod_id,))
                stock_antes = float(cur.fetchone()[0])
                stock_despues = stock_antes - pendiente
                cur.execute("UPDATE productos SET stock_actual=%s WHERE id=%s", (stock_despues, prod_id))
                costo_e, tipo_e = _resolver_costo_entrega(cur, cot_id, prod_id)
                cur.execute("""
                    UPDATE cotizacion_detalle
                       SET costo_entrega = %s, costo_entrega_tipo = %s
                     WHERE cotizacion_id = %s AND producto_id = %s
                """, (costo_e, tipo_e, cot_id, prod_id))
                cur.execute("""
                    INSERT INTO movimientos_stock
                        (producto_id, tipo, motivo, cantidad,
                         stock_antes, stock_despues, referencia, notas, fecha)
                    VALUES (%s,'salida','Entrega directa cotización',
                            %s,%s,%s,%s,%s,CURRENT_DATE)
                """, (prod_id, pendiente, stock_antes, stock_despues,
                      folio_cot, f"Cambio estado→Entregada {folio_cot}"))

        _etapa_map = {"Entregada": "Entregada", "Pagada": "Pagada"}
        if body.nuevo_estado in _etapa_map:
            _etapa = _etapa_map[body.nuevo_estado]
            _fecha_sync = body.fecha_entrega if body.nuevo_estado == "Entregada" else body.fecha_pago
            cur.execute("""
                INSERT INTO seguimiento_etapas
                    (cotizacion_id, etapa, completada, fecha_etapa)
                VALUES (%s, %s, 1, %s::date)
                ON CONFLICT (cotizacion_id, etapa) DO UPDATE SET
                    completada  = 1,
                    fecha_etapa = COALESCE(EXCLUDED.fecha_etapa, seguimiento_etapas.fecha_etapa)
            """, (cot_id, _etapa, _fecha_sync or None))

    from web_app.cache import cache as _cache
    _cache.invalidar(f"dashboard:{empresa_db}")

    log_evento(
        empresa_db, "cotizacion", cot_id,
        f"Estado → {body.nuevo_estado}",
        detalle=f"Cambiado por {user.get('username', '?')}",
        usuario=user.get("username"),
    )

    return JSONResponse({"ok": True})


# ── PATCH /api/cotizaciones/{cot_id}/resultado ────────────────────────────────

class ResultadoIn(BaseModel):
    resultado: str
    motivo_perdida: Optional[str] = None


@router.patch("/{cot_id}/resultado")
async def registrar_resultado(cot_id: int, body: ResultadoIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if body.resultado not in ("ganada", "perdida", "sin_respuesta"):
        raise HTTPException(status_code=400, detail="resultado debe ser ganada|perdida|sin_respuesta")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE cotizaciones
               SET resultado = %s, motivo_perdida = %s
             WHERE id = %s
        """, (body.resultado, body.motivo_perdida or None, cot_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")

    return JSONResponse({"ok": True})


# ── GET /api/cotizaciones/plantilla-import ────────────────────────────────────
# IMPORTANTE: debe estar ANTES de /{cot_id}

@router.get("/plantilla-import")
async def descargar_plantilla_import(user: dict = Depends(get_usuario_api)):
    """Descarga un CSV de ejemplo para importar líneas a una cotización."""
    contenido = (
        "descripcion,cantidad,unidad_medida\n"
        "Ejemplo Producto 1,10,pza\n"
        "Ejemplo Producto 2,5.5,kg\n"
    )
    return Response(
        content=contenido.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="plantilla_cotizacion.csv"'},
    )


# ── POST /api/cotizaciones/importar-plantilla ─────────────────────────────────

@router.post("/importar-plantilla")
async def importar_plantilla(
    file: UploadFile = File(...),
    user: dict = Depends(get_usuario_api),
):
    """
    Procesa un CSV con columnas: descripcion, cantidad, unidad_medida.
    Retorna filas matched (producto encontrado en catálogo) y unmatched.
    """
    raw = await file.read()
    try:
        texto = raw.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        texto = raw.decode("latin-1").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    reader = csv.DictReader(io.StringIO(texto))
    # Normalizar nombres de columnas (strip + lower)
    fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]
    if "descripcion" not in fieldnames:
        raise HTTPException(
            status_code=400,
            detail="El CSV debe tener una columna 'descripcion'.",
        )

    filas: list[dict] = []
    for row in reader:
        norm = {k.strip().lower(): v.strip() for k, v in row.items()}
        desc = norm.get("descripcion", "").strip()
        if not desc:
            continue
        try:
            cantidad = float(norm.get("cantidad", "1") or "1")
        except ValueError:
            cantidad = 1.0
        filas.append({
            "descripcion_csv": desc,
            "cantidad": cantidad,
            "unidad_medida": norm.get("unidad_medida", "").strip(),
        })

    if not filas:
        raise HTTPException(status_code=400, detail="El CSV no contiene filas válidas.")

    matched: list[dict] = []
    unmatched: list[dict] = []

    _SIMILARITY_THRESHOLD = 0.30

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        for fila in filas:
            desc_norm = fila["descripcion_csv"].strip()
            cur.execute("""
                SELECT p.id, p.nombre, p.unidad_medida,
                       COALESCE(p.precio_venta, p.precio_base, 0) AS precio,
                       p.aplica_iva,
                       GREATEST(
                           word_similarity(%s, p.nombre),
                           CASE WHEN p.codigo ILIKE %s THEN 1.0 ELSE 0.0 END
                       ) AS score
                FROM productos p
                WHERE p.nombre ILIKE %s
                   OR p.codigo ILIKE %s
                   OR word_similarity(%s, p.nombre) > %s
                ORDER BY score DESC
                LIMIT 1
            """, (desc_norm, desc_norm, f"%{desc_norm}%", desc_norm, desc_norm, _SIMILARITY_THRESHOLD))
            row = cur.fetchone()
            if row and row[5] >= _SIMILARITY_THRESHOLD:
                matched.append({
                    "descripcion_csv": fila["descripcion_csv"],
                    "producto_id":     row[0],
                    "nombre_catalogo": row[1],
                    "unidad_medida":   row[2] or fila["unidad_medida"],
                    "cantidad":        fila["cantidad"],
                    "precio":          _serial(row[3]),
                    "aplica_iva":      bool(row[4]),
                    "score":           round(float(row[5]), 2),
                })
            else:
                unmatched.append({
                    "descripcion_csv": fila["descripcion_csv"],
                    "cantidad":        fila["cantidad"],
                    "unidad_medida":   fila["unidad_medida"],
                })

    return JSONResponse({"matched": matched, "unmatched": unmatched})


# ── GET /api/cotizaciones/buscar-producto ────────────────────────────────────
# IMPORTANTE: debe estar ANTES de /{cot_id} para que FastAPI no lo capture como ID

@router.get("/buscar-producto")
async def buscar_producto(
    q: str = Query("", min_length=2),
    user: dict = Depends(get_usuario_api),
):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   COALESCE(p.costo_promedio, p.precio_base, 0) AS costo_promedio,
                   COALESCE(
                       p.precio_venta,
                       (SELECT MAX(h.precio) * 1.35
                        FROM producto_precio_historial h
                        WHERE h.producto_id = p.id),
                       p.precio_base * 1.35,
                       0
                   ) AS precio,
                   p.stock_actual, p.aplica_iva,
                   prov.nombre AS proveedor_nombre,
                   COALESCE(p.precio_desactualizado, FALSE) AS precio_desactualizado,
                   EXISTS(
                       SELECT 1 FROM producto_precio_historial h
                       WHERE h.producto_id = p.id AND h.fuente = 'compra'
                   ) AS tiene_historial_compras,
                   EXTRACT(DAY FROM NOW() - GREATEST(
                       (SELECT MAX(h.fecha_registro) FROM producto_precio_historial h
                        WHERE h.producto_id = p.id),
                       CASE WHEN p.precio_base_fecha IS NOT NULL
                            THEN p.precio_base_fecha::TIMESTAMPTZ
                            ELSE NULL END
                   ))::int AS dias_sin_actualizar
            FROM productos p
            LEFT JOIN producto_proveedor pp ON pp.producto_id = p.id AND pp.es_principal = 1
            LEFT JOIN proveedores prov ON prov.id = pp.proveedor_id
            WHERE p.nombre ILIKE %s
               OR p.codigo ILIKE %s
               OR word_similarity(%s, p.nombre) > 0.25
            ORDER BY
                word_similarity(%s, p.nombre) DESC,
                p.nombre
            LIMIT 12
        """, (f"%{q}%", f"%{q}%", q, q))
        resultados = _rows(cur)
    return JSONResponse({"resultados": resultados})


# ── GET /api/cotizaciones/export ─────────────────────────────────────────────

@router.get("/export")
async def exportar(user: dict = Depends(get_usuario_api)):
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT c.folio, c.fecha,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   c.total AS total_cotizacion, c.estado,
                   c.orden_compra, c.numero_factura,
                   COALESCE(p.codigo, '')                        AS codigo,
                   COALESCE(p.nombre, cd.descripcion_libre, '')  AS concepto,
                   COALESCE(p.unidad_medida, '')                 AS unidad,
                   cd.cantidad, cd.precio_unitario,
                   cd.subtotal, cd.iva, cd.total                 AS total_partida
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            LEFT JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            LEFT JOIN productos p ON p.id = cd.producto_id
            ORDER BY c.fecha DESC, c.id DESC, cd.id
        """)
        rows = _rows(cur)

        cur.execute("""
            SELECT
                SUM(total) FILTER (WHERE estado <> 'Cancelada')              AS solicitado,
                SUM(total) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada','Pagada'))                        AS entregado,
                SUM(total) FILTER (WHERE estado IN ('Facturada','Pagada'))   AS facturado,
                SUM(total) FILTER (WHERE estado = 'Pagada')                  AS pagado
            FROM cotizaciones
        """)
        r = cur.fetchone()

    totales = {
        "solicitado": _serial(r[0]) or 0,
        "entregado":  _serial(r[1]) or 0,
        "facturado":  _serial(r[2]) or 0,
        "pagado":     _serial(r[3]) or 0,
    }
    return JSONResponse({"partidas": rows, "totales": totales})


# ── GET /api/cotizaciones/{cot_id} ───────────────────────────────────────────

@router.get("/{cot_id}")
async def detalle(cot_id: int, user: dict = Depends(get_usuario_api)):
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso a cotizaciones")

    empresa_db = user["empresa_db"]

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        # Cabecera + datos de cliente y comprador
        cur.execute("""
            SELECT c.*,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cl.tipo      AS tipo_cliente,
                   cl.rfc       AS cliente_rfc,
                   cl.direccion AS cliente_dir,
                   cl.contacto  AS cliente_contacto,
                   cl.email     AS cliente_email,
                   cl.telefono  AS cliente_tel,
                   comp.nombre  AS comprador_nombre,
                   comp.cargo   AS comprador_cargo,
                   comp.telefono AS comprador_tel,
                   comp.email   AS comprador_email
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            LEFT JOIN compradores comp ON comp.id = c.comprador_id
            WHERE c.id = %s
        """, (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        cols = [d[0] for d in cur.description]
        cot = {k: _serial(v) for k, v in zip(cols, row)}

        # Partidas con stock actual del producto
        cur.execute("""
            SELECT cd.id,
                   cd.producto_id,
                   COALESCE(p.codigo, '')                          AS codigo,
                   COALESCE(p.nombre, cd.descripcion_libre, '')    AS nombre,
                   COALESCE(p.unidad_medida, '')                   AS unidad_medida,
                   cd.cantidad, cd.precio_unitario,
                   cd.subtotal, cd.iva, cd.total,
                   COALESCE(p.aplica_iva, 0)                       AS aplica_iva,
                   cd.descripcion_libre,
                   COALESCE(cd.pendiente_catalogo, FALSE)          AS pendiente_catalogo,
                   COALESCE(p.stock_actual, 0)                     AS stock_actual,
                   cd.cantidad <= COALESCE(p.stock_actual, 0)      AS stock_ok,
                   cd.costo_snapshot,
                   COALESCE(cd.margen_pct,
                       CASE WHEN cd.precio_unitario > 0
                       THEN (cd.precio_unitario - COALESCE(cd.costo_snapshot, 0))
                            / cd.precio_unitario * 100
                       ELSE NULL END
                   )                                               AS margen_pct,
                   COALESCE((
                       SELECT SUM(ep.cantidad_entregada)
                       FROM entregas_parciales ep
                       WHERE ep.cotizacion_id = cd.cotizacion_id
                         AND ep.producto_id   = cd.producto_id
                   ), 0)                                           AS ya_entregado,
                   cd.proveedor_id,
                   prov.nombre                                     AS proveedor_nombre
            FROM cotizacion_detalle cd
            LEFT JOIN productos p ON p.id = cd.producto_id
            LEFT JOIN proveedores prov ON prov.id = cd.proveedor_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
        """, (cot_id,))
        partidas = _rows(cur)

        # stock_ok global: todas las partidas de catálogo tienen stock suficiente
        cot["stock_ok"] = all(
            p["stock_ok"] for p in partidas if p["producto_id"] is not None
        )

        # Seguimiento de etapas
        cur.execute("""
            SELECT etapa, completada, referencia, fecha_etapa, notas
            FROM seguimiento_etapas
            WHERE cotizacion_id = %s
            ORDER BY id
        """, (cot_id,))
        etapas_db = {}
        for r in cur.fetchall():
            etapas_db[r[0]] = {
                "completada": bool(r[1]),
                "referencia": r[2] or "",
                "fecha_etapa": (r[3].isoformat() if hasattr(r[3], 'isoformat') else str(r[3])) if r[3] else "",
                "notas": r[4] or "",
            }

        # Facturas de venta vinculadas
        cur.execute("""
            SELECT f.id, f.uuid, f.serie, f.folio_factura, f.fecha, f.total,
                   f.nombre_receptor, f.tipo
            FROM factura_cotizaciones fc
            JOIN facturas f ON f.id = fc.factura_id
            WHERE fc.cotizacion_id = %s
            ORDER BY f.fecha DESC
        """, (cot_id,))
        facturas_vinculadas = _rows(cur)

        folio_factura_vinculada = None
        for fv in facturas_vinculadas:
            if fv.get("tipo") == "I":
                folio_factura_vinculada = (fv.get("serie") or "") + (fv.get("folio_factura") or "")
                break
        cot["folio_factura"] = folio_factura_vinculada or cot.get("numero_factura")

        # Compras vinculadas
        cur.execute("""
            SELECT DISTINCT comp.id, f.uuid, f.serie, f.folio_factura, f.fecha,
                            comp.total, COALESCE(f.nombre_emisor, '—') AS proveedor,
                            comp.folio AS compra_folio
            FROM compra_detalle_cotizacion cdc
            JOIN compra_detalle cd ON cd.id = cdc.compra_detalle_id
            JOIN compras comp ON comp.id = cd.compra_id
            LEFT JOIN facturas f ON f.id = comp.factura_xml_id
            WHERE cdc.cotizacion_id = %s
            ORDER BY f.fecha DESC
        """, (cot_id,))
        compras_vinculadas = _rows(cur)

        # Costos reales (para mostrar margen en detalle)
        cur.execute("""
            SELECT comp.producto_id,
                   SUM(comp.costo_unitario * cdc.cantidad) / NULLIF(SUM(cdc.cantidad), 0)
                       AS costo_real_avg
            FROM compra_detalle_cotizacion cdc
            JOIN compra_detalle comp ON comp.id = cdc.compra_detalle_id
            WHERE cdc.cotizacion_id = %s
            GROUP BY comp.producto_id
        """, (cot_id,))
        costos_reales = {r[0]: _serial(r[1]) for r in cur.fetchall() if r[1] is not None}

        cur.execute("""
            SELECT e.id, e.nombre, e.fecha, e.estado,
                   EXISTS(
                       SELECT 1 FROM estudio_mercado_items i
                       JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id AND c.ganador = TRUE
                       WHERE i.estudio_id = e.id AND i.cotizacion_detalle_id IS NOT NULL
                   ) AS tiene_ganadores_aplicables
            FROM estudios_mercado e
            WHERE e.cotizacion_id = %s
            ORDER BY e.fecha_registro DESC
        """, (cot_id,))
        estudios = _rows(cur)

    # Enriquecer partidas con costo real
    for p in partidas:
        pid = p.get("producto_id")
        p["costo_real"] = costos_reales.get(pid) if pid else None

    return JSONResponse({
        "cotizacion": cot,
        "partidas": partidas,
        "etapas": etapas_db,
        "facturas_vinculadas": facturas_vinculadas,
        "compras_vinculadas": compras_vinculadas,
        "estudios": estudios,
    })


# ── POST /api/cotizaciones ───────────────────────────────────────────────────

@router.post("")
async def crear(body: CotizacionIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if not body.partidas:
        raise HTTPException(status_code=400, detail="Debe incluir al menos una partida")

    empresa_db = user["empresa_db"]
    año = date.today().year
    subtotal_global = Decimal("0")
    iva_global = Decimal("0")

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        folio = _generar_folio_en_tx(cur, año)
        detalle_rows = []

        for p in body.partidas:
            cant = Decimal(str(p.cantidad))
            precio = Decimal(str(p.precio_unitario))
            sub = (cant * precio).quantize(Decimal("0.01"))
            es_libre = p.producto_id is None

            if es_libre:
                prod_iva = p.aplica_iva
                costo_snap = 0.0
                tiene_stock = True
                margen_pct = None
            else:
                cur.execute(
                    "SELECT COALESCE(NULLIF(costo_promedio,0), precio_base, 0), "
                    "aplica_iva, COALESCE(stock_actual,0) >= %s "
                    "FROM productos WHERE id = %s",
                    (float(cant), p.producto_id),
                )
                pb_row = cur.fetchone()
                costo_snap = float(pb_row[0]) if pb_row else 0.0
                prod_iva = bool(pb_row[1]) if pb_row else False
                tiene_stock = bool(pb_row[2]) if pb_row else False
                precio_f = float(precio)
                margen_pct = round((precio_f - costo_snap) / precio_f * 100, 4) if precio_f > 0 else 0.0

            p_iva = (sub * Decimal("0.16")).quantize(Decimal("0.01")) if prod_iva else Decimal("0")
            p_tot = (sub + p_iva).quantize(Decimal("0.01"))
            subtotal_global += sub
            iva_global += p_iva
            detalle_rows.append((
                p.producto_id,
                cant, precio, sub, p_iva, p_tot,
                tiene_stock, costo_snap,
                p.descripcion_libre if es_libre else None,
                es_libre, margen_pct,
            ))

        total_global = (subtotal_global + iva_global).quantize(Decimal("0.01"))
        hay_iva = iva_global > 0

        cur.execute(
            """
            INSERT INTO cotizaciones
              (folio, fecha, cliente_id, comprador_id, subtotal, iva, total,
               notas, estado, aplica_iva, orden_compra, utilidad_pct, razon_social_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pendiente', %s, %s, %s, %s)
            """,
            (folio, body.fecha, body.cliente_id, body.comprador_id,
             float(subtotal_global), float(iva_global), float(total_global),
             body.notas, 1 if hay_iva else 0,
             body.orden_compra, body.utilidad_pct, body.razon_social_id),
        )
        cot_id = cur.lastrowid

        for (prod_id, cant, precio, sub, p_iva, p_tot,
             tiene_stock, costo_snap, desc_libre, es_libre, margen_pct) in detalle_rows:
            cur.execute(
                """
                INSERT INTO cotizacion_detalle
                  (cotizacion_id, producto_id, descripcion_libre, pendiente_catalogo,
                   cantidad, precio_unitario, subtotal, iva, total,
                   tiene_stock, costo_snapshot, margen_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (cot_id, prod_id, desc_libre, es_libre,
                 float(cant), float(precio),
                 float(sub), float(p_iva), float(p_tot),
                 1 if tiene_stock else 0, costo_snap, margen_pct),
            )

    log_evento(
        empresa_db, "cotizacion", cot_id,
        "Cotización creada",
        detalle=f"Folio {folio}",
        usuario=user.get("username"),
    )
    return JSONResponse({"id": cot_id, "folio": folio}, status_code=201)


# ── PUT /api/cotizaciones/{cot_id} ───────────────────────────────────────────

@router.put("/{cot_id}")
async def actualizar(cot_id: int, body: CotizacionIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if not body.partidas:
        raise HTTPException(status_code=400, detail="Debe incluir al menos una partida")

    empresa_db = user["empresa_db"]
    subtotal_global = Decimal("0")
    iva_global      = Decimal("0")

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT folio FROM cotizaciones WHERE id = %s", (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        folio = row[0]

        cur.execute("DELETE FROM cotizacion_detalle WHERE cotizacion_id = %s", (cot_id,))

        detalle_rows = []
        for p in body.partidas:
            cant   = Decimal(str(p.cantidad))
            precio = Decimal(str(p.precio_unitario))
            sub    = (cant * precio).quantize(Decimal("0.01"))
            es_libre = p.producto_id is None

            if es_libre:
                prod_iva   = p.aplica_iva
                costo_snap = 0.0
                tiene_stock = True
                margen_pct = None
            else:
                cur.execute(
                    "SELECT COALESCE(NULLIF(costo_promedio,0), precio_base, 0), "
                    "aplica_iva, COALESCE(stock_actual,0) >= %s "
                    "FROM productos WHERE id = %s",
                    (float(cant), p.producto_id),
                )
                pb_row     = cur.fetchone()
                costo_snap  = float(pb_row[0]) if pb_row else 0.0
                prod_iva    = bool(pb_row[1])   if pb_row else False
                tiene_stock = bool(pb_row[2])   if pb_row else False
                precio_f = float(precio)
                margen_pct = round((precio_f - costo_snap) / precio_f * 100, 4) if precio_f > 0 else 0.0

            p_iva = (sub * Decimal("0.16")).quantize(Decimal("0.01")) if prod_iva else Decimal("0")
            p_tot = (sub + p_iva).quantize(Decimal("0.01"))
            subtotal_global += sub
            iva_global      += p_iva
            detalle_rows.append((
                p.producto_id,
                cant, precio, sub, p_iva, p_tot,
                tiene_stock, costo_snap,
                p.descripcion_libre if es_libre else None,
                es_libre, margen_pct,
            ))

        total_global = (subtotal_global + iva_global).quantize(Decimal("0.01"))
        hay_iva      = iva_global > 0

        cur.execute(
            """
            UPDATE cotizaciones
               SET cliente_id   = %s,
                   fecha        = %s,
                   notas        = %s,
                   subtotal     = %s,
                   iva          = %s,
                   total        = %s,
                   aplica_iva   = %s,
                   orden_compra = %s,
                   utilidad_pct = %s
             WHERE id = %s
            """,
            (body.cliente_id, body.fecha, body.notas,
             float(subtotal_global), float(iva_global), float(total_global),
             1 if hay_iva else 0, body.orden_compra, body.utilidad_pct,
             cot_id),
        )

        for (prod_id, cant, precio, sub, p_iva, p_tot,
             tiene_stock, costo_snap, desc_libre, es_libre, margen_pct) in detalle_rows:
            cur.execute(
                """
                INSERT INTO cotizacion_detalle
                  (cotizacion_id, producto_id, descripcion_libre, pendiente_catalogo,
                   cantidad, precio_unitario, subtotal, iva, total,
                   tiene_stock, costo_snapshot, margen_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (cot_id, prod_id, desc_libre, es_libre,
                 float(cant), float(precio),
                 float(sub), float(p_iva), float(p_tot),
                 1 if tiene_stock else 0, costo_snap, margen_pct),
            )

    return JSONResponse({"id": cot_id, "folio": folio})


# ── GET /api/cotizaciones/{cot_id}/pdf ────────────────────────────────────────

@router.get("/{cot_id}/pdf")
async def descargar_pdf(cot_id: int, user: dict = Depends(get_usuario_api)):
    try:
        from web_app.pdf_cotizacion import generar_pdf_cotizacion
        pdf_bytes = generar_pdf_cotizacion(user["empresa_db"], cot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {e}")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT folio FROM cotizaciones WHERE id = %s", (cot_id,))
        row = cur.fetchone()
    folio = row[0] if row else f"COT-{cot_id}"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Cotizacion_{folio}.pdf"'},
    )


# ── GET /api/cotizaciones/{cot_id}/estudios ──────────────────────────────────

@router.get("/{cot_id}/nota-remision/pdf")
async def descargar_nota_remision(cot_id: int, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador", "Almacenista"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    try:
        from web_app.pdf_nota_remision import generar_pdf_nota_remision
        pdf_bytes = generar_pdf_nota_remision(user["empresa_db"], cot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar nota de remision: {e}")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT folio FROM cotizaciones WHERE id = %s", (cot_id,))
        row = cur.fetchone()
    folio = row[0] if row else f"COT-{cot_id}"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="NotaRemision_{folio}.pdf"'},
    )


# ── POST /api/cotizaciones/{cot_id}/traslado ─────────────────────────────────

class TrasladoIn(BaseModel):
    origen: Optional[str] = None
    destino: Optional[str] = None
    transportista: Optional[str] = None
    placas: Optional[str] = None
    fecha_traslado: Optional[str] = None
    notas: Optional[str] = None


@router.post("/{cot_id}/traslado", status_code=201)
async def crear_traslado(cot_id: int, body: TrasladoIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT id FROM cotizaciones WHERE id = %s", (cot_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        cur.execute("""
            INSERT INTO traslados (cotizacion_id, origen, destino, transportista, placas, fecha_traslado, notas)
            VALUES (%s, %s, %s, %s, %s, %s::date, %s)
        """, (cot_id, body.origen, body.destino, body.transportista,
              body.placas, body.fecha_traslado or None, body.notas))
        traslado_id = cur.lastrowid
    return JSONResponse({"id": traslado_id}, status_code=201)


@router.get("/{cot_id}/traslado")
async def get_traslado(cot_id: int, user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT id, origen, destino, transportista, placas, fecha_traslado, notas, created_at
            FROM traslados WHERE cotizacion_id = %s ORDER BY id DESC LIMIT 1
        """, (cot_id,))
        row = cur.fetchone()
        if not row:
            return JSONResponse({"traslado": None})
        cols = ["id", "origen", "destino", "transportista", "placas", "fecha_traslado", "notas", "created_at"]
        return JSONResponse({"traslado": {k: _serial(v) for k, v in zip(cols, row)}})


@router.get("/{cot_id}/estudios")
async def estudios_de_cotizacion(cot_id: int, user: dict = Depends(get_usuario_api)):
    """Retorna los estudios de mercado vinculados a esta cotización."""
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT id, nombre, fecha, estado
            FROM estudios_mercado
            WHERE cotizacion_id = %s
            ORDER BY fecha_registro DESC
        """, (cot_id,))
        estudios = _rows(cur)
    return JSONResponse({"estudios": estudios})
