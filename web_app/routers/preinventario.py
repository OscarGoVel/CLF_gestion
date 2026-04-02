# -*- coding: utf-8 -*-
"""
web_app/routers/preinventario.py
Módulo de Pre-Inventario: captura de conteos físicos con flujo de autorización.

Flujo:
  Operario captura → sesión "abierta"
  Operario cierra  → sesión "cerrada" (pendiente revisión)
  Admin aprueba    → ajustes aplicados a movimientos_stock / productos
  Admin rechaza    → sin cambios en stock
"""

import json
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.auth import verificar_password
from web_app.database import get_pool_empresa, pool_usuarios
from web_app.dependencies import get_usuario_actual
from web_app.rbac import require_rol

router = APIRouter(prefix="/preinventario")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [{c: _f(v) for c, v in zip(cols, row)} for row in cur.fetchall()]


# ─────────────────────────────────────────────────────────────────────────────
# MIGRACIÓN AUTOMÁTICA DE TABLAS
# ─────────────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS sucursales (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS areas (
    id          SERIAL PRIMARY KEY,
    sucursal_id INTEGER NOT NULL REFERENCES sucursales(id) ON DELETE CASCADE,
    nombre      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_ubicaciones (
    producto_id INTEGER PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
    area_id     INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS preinventario_sesiones (
    id               SERIAL PRIMARY KEY,
    nombre           TEXT NOT NULL,
    creado_por       TEXT NOT NULL,
    estado           TEXT NOT NULL DEFAULT 'abierta',
    tipo             TEXT NOT NULL DEFAULT 'parcial',
    fecha_creacion   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_cierre     TIMESTAMPTZ,
    aprobado_por     TEXT,
    fecha_aprobacion TIMESTAMPTZ,
    notas_aprobacion TEXT
);

CREATE TABLE IF NOT EXISTS preinventario_items (
    id               SERIAL PRIMARY KEY,
    sesion_id        INTEGER NOT NULL REFERENCES preinventario_sesiones(id) ON DELETE CASCADE,
    producto_id      INTEGER NOT NULL REFERENCES productos(id),
    cantidad_teorica REAL,
    cantidad_fisica  REAL NOT NULL,
    capturado_por    TEXT NOT NULL,
    fecha_captura    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ajustado_por     TEXT,
    cantidad_ajustada REAL,
    notas            TEXT
);

CREATE TABLE IF NOT EXISTS sesion_areas (
    sesion_id INTEGER NOT NULL REFERENCES preinventario_sesiones(id) ON DELETE CASCADE,
    area_id   INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    PRIMARY KEY (sesion_id, area_id)
);

CREATE TABLE IF NOT EXISTS preinventario_historico (
    id               SERIAL PRIMARY KEY,
    sesion_id        INTEGER NOT NULL REFERENCES preinventario_sesiones(id),
    nombre           TEXT NOT NULL,
    fecha_aprobacion TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    aprobado_por     TEXT NOT NULL,
    total_items      INTEGER NOT NULL DEFAULT 0,
    items_ajustados  INTEGER NOT NULL DEFAULT 0,
    snapshot         JSONB NOT NULL
);
"""


def _asegurar_tablas(empresa_db: str) -> None:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        # Migraciones para tablas existentes
        cur.execute("ALTER TABLE preinventario_sesiones ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'parcial'")


# ─────────────────────────────────────────────────────────────────────────────
# OPERARIO — Lista de sesiones
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def lista_sesiones(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    _asegurar_tablas(user["empresa_db"])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT s.id, s.nombre, s.estado, s.creado_por,
                   s.fecha_creacion, s.fecha_cierre, s.tipo,
                   COUNT(i.id) AS total_items
            FROM preinventario_sesiones s
            LEFT JOIN preinventario_items i ON i.sesion_id = s.id
            GROUP BY s.id
            ORDER BY s.fecha_creacion DESC
            LIMIT 50
        """)
        sesiones = _rows(cur)

        # Áreas agrupadas por sucursal para el form de creación
        cur.execute("""
            SELECT a.id, a.nombre, s.id AS sucursal_id, s.nombre AS sucursal_nombre
            FROM areas a
            JOIN sucursales s ON s.id = a.sucursal_id
            ORDER BY s.nombre, a.nombre
        """)
        areas_raw = cur.fetchall()

    sucursales_map: dict = {}
    for area_id, area_nombre, suc_id, suc_nombre in areas_raw:
        if suc_id not in sucursales_map:
            sucursales_map[suc_id] = {"id": suc_id, "nombre": suc_nombre, "areas": []}
        sucursales_map[suc_id]["areas"].append({"id": area_id, "nombre": area_nombre})
    sucursales = list(sucursales_map.values())

    return templates.TemplateResponse(
        request=request,
        name="preinventario/index.html",
        context={
            "user": user,
            "sesiones": sesiones,
            "sucursales": sucursales,
            "seccion": "preinventario",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPERARIO — Crear sesión
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sesion", response_class=HTMLResponse)
async def crear_sesion(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    form = await request.form()
    nombre = (form.get("nombre") or "").strip()
    tipo   = form.get("tipo", "parcial")
    if tipo not in ("completo", "parcial"):
        tipo = "parcial"
    area_ids = [int(v) for v in form.getlist("area_ids") if str(v).isdigit()]

    if not nombre:
        return RedirectResponse("/preinventario")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO preinventario_sesiones (nombre, creado_por, tipo)
            VALUES (%s, %s, %s) RETURNING id
        """, (nombre, user["nombre"], tipo))
        sesion_id = cur.fetchone()[0]

        for area_id in area_ids:
            cur.execute(
                "INSERT INTO sesion_areas (sesion_id, area_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (sesion_id, area_id),
            )

    return RedirectResponse(f"/preinventario/sesion/{sesion_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# OPERARIO — Vista de captura de una sesión
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sesion/{sesion_id}", response_class=HTMLResponse)
async def vista_sesion(request: Request, sesion_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre, estado, creado_por, fecha_creacion, tipo FROM preinventario_sesiones WHERE id = %s",
            (sesion_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Sesión no encontrada")
        sesion = dict(zip(["id", "nombre", "estado", "creado_por", "fecha_creacion", "tipo"], row))

        cur.execute("""
            SELECT a.id, a.nombre, s.nombre AS sucursal_nombre
            FROM sesion_areas sa
            JOIN areas a ON a.id = sa.area_id
            JOIN sucursales s ON s.id = a.sucursal_id
            WHERE sa.sesion_id = %s
            ORDER BY s.nombre, a.nombre
        """, (sesion_id,))
        sesion["areas"] = [{"id": r[0], "nombre": r[1], "sucursal": r[2]} for r in cur.fetchall()]

        cur.execute("""
            SELECT i.id, p.codigo, p.nombre, p.unidad_medida,
                   i.cantidad_teorica, i.cantidad_fisica,
                   i.capturado_por, i.fecha_captura, i.notas
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY i.fecha_captura DESC
        """, (sesion_id,))
        items = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/sesion.html",
        context={
            "user": user,
            "sesion": sesion,
            "items": items,
            "seccion": "preinventario",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPERARIO — Agregar / actualizar item
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sesion/{sesion_id}/item", response_class=HTMLResponse)
async def agregar_item(
    request: Request,
    sesion_id: int,
    producto_id: int = Form(...),
    cantidad_fisica: float = Form(...),
    notas: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        return HTMLResponse("", status_code=401)

    if cantidad_fisica < 0:
        return templates.TemplateResponse(
            request=request,
            name="preinventario/_item_fila.html",
            context={"error": "La cantidad no puede ser negativa.", "user": user},
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Verificar sesión abierta
        cur.execute("SELECT estado FROM preinventario_sesiones WHERE id = %s", (sesion_id,))
        row = cur.fetchone()
        if not row or row[0] != "abierta":
            return templates.TemplateResponse(
                request=request,
                name="preinventario/_item_fila.html",
                context={"error": "La sesión no está abierta para captura.", "user": user},
            )

        # Capturar stock teórico actual
        cur.execute("SELECT stock_actual FROM productos WHERE id = %s", (producto_id,))
        p_row = cur.fetchone()
        if not p_row:
            return templates.TemplateResponse(
                request=request,
                name="preinventario/_item_fila.html",
                context={"error": "Producto no encontrado.", "user": user},
            )
        cantidad_teorica = float(p_row[0] or 0)

        # Upsert: si ya existe el producto en la sesión, actualizar
        cur.execute("""
            SELECT id FROM preinventario_items
            WHERE sesion_id = %s AND producto_id = %s
        """, (sesion_id, producto_id))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE preinventario_items
                SET cantidad_fisica = %s, cantidad_teorica = %s,
                    notas = %s, capturado_por = %s, fecha_captura = NOW()
                WHERE id = %s
            """, (cantidad_fisica, cantidad_teorica, notas or None,
                  user["nombre"], existing[0]))
        else:
            cur.execute("""
                INSERT INTO preinventario_items
                    (sesion_id, producto_id, cantidad_teorica, cantidad_fisica,
                     capturado_por, notas)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (sesion_id, producto_id, cantidad_teorica, cantidad_fisica,
                  user["nombre"], notas or None))

        # Devolver tabla actualizada
        cur.execute("""
            SELECT i.id, p.codigo, p.nombre, p.unidad_medida,
                   i.cantidad_teorica, i.cantidad_fisica,
                   i.capturado_por, i.fecha_captura, i.notas
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY i.fecha_captura DESC
        """, (sesion_id,))
        items = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/_items_tabla.html",
        context={"user": user, "items": items, "sesion_id": sesion_id,
                 "sesion_estado": "abierta"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPERARIO — Eliminar item
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/item/{item_id}", response_class=HTMLResponse)
async def eliminar_item(request: Request, item_id: int):
    user = get_usuario_actual(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT i.sesion_id, s.estado
            FROM preinventario_items i
            JOIN preinventario_sesiones s ON s.id = i.sesion_id
            WHERE i.id = %s
        """, (item_id,))
        row = cur.fetchone()
        if not row:
            return HTMLResponse("")
        sesion_id, estado = row

        if estado != "abierta":
            return HTMLResponse("")

        cur.execute("DELETE FROM preinventario_items WHERE id = %s", (item_id,))

        cur.execute("""
            SELECT i.id, p.codigo, p.nombre, p.unidad_medida,
                   i.cantidad_teorica, i.cantidad_fisica,
                   i.capturado_por, i.fecha_captura, i.notas
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY i.fecha_captura DESC
        """, (sesion_id,))
        items = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/_items_tabla.html",
        context={"user": user, "items": items, "sesion_id": sesion_id,
                 "sesion_estado": "abierta"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPERARIO — Cerrar sesión
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sesion/{sesion_id}/cerrar", response_class=HTMLResponse)
async def cerrar_sesion(request: Request, sesion_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE preinventario_sesiones
            SET estado = 'cerrada', fecha_cierre = NOW()
            WHERE id = %s AND estado = 'abierta'
        """, (sesion_id,))

    return RedirectResponse("/preinventario", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# BUSCAR PRODUCTO — autocomplete (HTMX)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/buscar", response_class=HTMLResponse)
async def buscar_producto(request: Request, q: str = ""):
    user = get_usuario_actual(request)
    if not user:
        return HTMLResponse("")

    if len(q.strip()) < 2:
        return HTMLResponse("")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS codigo_barras TEXT")
        cur.execute("""
            SELECT id, codigo, nombre, stock_actual, unidad_medida
            FROM productos
            WHERE nombre ILIKE %s OR codigo ILIKE %s OR codigo_barras ILIKE %s
            ORDER BY nombre LIMIT 8
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        resultados = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/_sugerencias.html",
        context={"resultados": resultados, "user": user},
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Lista de sesiones pendientes de revisión
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_lista(
    request: Request,
    user=Depends(require_rol("Administrador")),
):
    _asegurar_tablas(user["empresa_db"])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT s.id, s.nombre, s.estado, s.creado_por,
                   s.fecha_creacion, s.fecha_cierre, s.aprobado_por,
                   s.fecha_aprobacion,
                   COUNT(i.id) AS total_items,
                   SUM(ABS(COALESCE(i.cantidad_ajustada, i.cantidad_fisica) - COALESCE(i.cantidad_teorica, 0))) AS total_diferencia
            FROM preinventario_sesiones s
            LEFT JOIN preinventario_items i ON i.sesion_id = s.id
            GROUP BY s.id
            ORDER BY
                CASE s.estado WHEN 'cerrada' THEN 0 WHEN 'abierta' THEN 1 ELSE 2 END,
                s.fecha_cierre DESC NULLS LAST
        """)
        sesiones = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/admin_lista.html",
        context={"user": user, "sesiones": sesiones, "seccion": "preinventario"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Revisión detallada de una sesión
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/sesion/{sesion_id}", response_class=HTMLResponse)
async def admin_sesion(
    request: Request,
    sesion_id: int,
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre, estado, creado_por, fecha_creacion, fecha_cierre, aprobado_por, notas_aprobacion FROM preinventario_sesiones WHERE id = %s",
            (sesion_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Sesión no encontrada")
        cols = ["id", "nombre", "estado", "creado_por", "fecha_creacion",
                "fecha_cierre", "aprobado_por", "notas_aprobacion"]
        sesion = dict(zip(cols, row))

        cur.execute("""
            SELECT i.id, p.id AS producto_id, p.codigo, p.nombre, p.unidad_medida,
                   i.cantidad_teorica, i.cantidad_fisica, i.cantidad_ajustada,
                   COALESCE(i.cantidad_ajustada, i.cantidad_fisica) - COALESCE(i.cantidad_teorica, 0) AS diferencia,
                   i.capturado_por, i.ajustado_por, i.fecha_captura, i.notas
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY ABS(COALESCE(i.cantidad_ajustada, i.cantidad_fisica) - COALESCE(i.cantidad_teorica, 0)) DESC
        """, (sesion_id,))
        items = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/admin_sesion.html",
        context={
            "user": user,
            "sesion": sesion,
            "items": items,
            "seccion": "preinventario",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Ajustar cantidad de un item
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin/item/{item_id}/ajustar", response_class=HTMLResponse)
async def ajustar_item(
    request: Request,
    item_id: int,
    cantidad_ajustada: float = Form(...),
    notas: str = Form(""),
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE preinventario_items
            SET cantidad_ajustada = %s, ajustado_por = %s,
                notas = COALESCE(NULLIF(%s, ''), notas)
            WHERE id = %s
            RETURNING sesion_id
        """, (cantidad_ajustada, user["nombre"], notas, item_id))
        row = cur.fetchone()
        if not row:
            return HTMLResponse("")
        sesion_id = row[0]

        cur.execute("""
            SELECT i.id, p.id AS producto_id, p.codigo, p.nombre, p.unidad_medida,
                   i.cantidad_teorica, i.cantidad_fisica, i.cantidad_ajustada,
                   COALESCE(i.cantidad_ajustada, i.cantidad_fisica) - COALESCE(i.cantidad_teorica, 0) AS diferencia,
                   i.capturado_por, i.ajustado_por, i.fecha_captura, i.notas
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY ABS(COALESCE(i.cantidad_ajustada, i.cantidad_fisica) - COALESCE(i.cantidad_teorica, 0)) DESC
        """, (sesion_id,))
        items = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/_tabla_items_admin.html",
        context={"user": user, "items": items, "sesion_id": sesion_id,
                 "sesion": {"estado": "cerrada"}},
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Pre-aprobación: análisis de discrepancias (HTMX fragment)
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_no_contados(cur, sesion_id: int, tipo: str, fecha_creacion,
                        product_ids_contados: list) -> tuple[list, list]:
    """
    Retorna (no_contados, sin_area_advertencias) según tipo de sesión y áreas.
    no_contados: productos que se zerarán al aprobar.
    sin_area_advertencias: productos del catálogo sin área asignada (solo tipo completo sin áreas).
    """
    if tipo == "parcial":
        return [], []

    # Áreas seleccionadas para esta sesión
    cur.execute("""
        SELECT area_id FROM sesion_areas WHERE sesion_id = %s
    """, (sesion_id,))
    area_ids = [r[0] for r in cur.fetchall()]

    if area_ids:
        # Completo con áreas: productos asignados a esas áreas que no se contaron
        cur.execute("""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida, p.stock_actual,
                   a.nombre AS area_nombre, s.nombre AS sucursal_nombre
            FROM stock_ubicaciones su
            JOIN productos p ON p.id = su.producto_id
            JOIN areas a ON a.id = su.area_id
            JOIN sucursales s ON s.id = a.sucursal_id
            WHERE su.area_id = ANY(%s)
              AND p.id != ALL(%s)
            ORDER BY p.nombre
        """, (area_ids, product_ids_contados or [0]))
        no_contados = [
            {
                "producto_id": r[0], "codigo": r[1], "nombre": r[2],
                "unidad_medida": r[3], "stock_ahora": float(r[4] or 0),
                "area_nombre": r[5], "sucursal_nombre": r[6],
                "tipo_fila": "no_contado",
            }
            for r in cur.fetchall()
        ]
        return no_contados, []
    else:
        # Completo sin áreas: TODOS los productos del catálogo
        cur.execute("""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida, p.stock_actual,
                   a.nombre AS area_nombre, s.nombre AS sucursal_nombre
            FROM productos p
            LEFT JOIN stock_ubicaciones su ON su.producto_id = p.id
            LEFT JOIN areas a ON a.id = su.area_id
            LEFT JOIN sucursales s ON s.id = a.sucursal_id
            WHERE p.id != ALL(%s)
            ORDER BY p.nombre
        """, (product_ids_contados or [0],))
        rows = cur.fetchall()
        no_contados = []
        sin_area = []
        for r in rows:
            entry = {
                "producto_id": r[0], "codigo": r[1], "nombre": r[2],
                "unidad_medida": r[3], "stock_ahora": float(r[4] or 0),
                "area_nombre": r[5], "sucursal_nombre": r[6],
                "tipo_fila": "no_contado",
            }
            if r[5] is None:
                entry["tipo_fila"] = "sin_area"
                sin_area.append(entry)
            else:
                no_contados.append(entry)
        return no_contados, sin_area


@router.get("/admin/sesion/{sesion_id}/preaprobacion", response_class=HTMLResponse)
async def preaprobacion(
    request: Request,
    sesion_id: int,
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre, estado, fecha_creacion, tipo FROM preinventario_sesiones WHERE id = %s",
            (sesion_id,),
        )
        row = cur.fetchone()
        if not row or row[2] != "cerrada":
            raise HTTPException(400, "La sesión debe estar cerrada para aprobar.")
        sesion = {"id": row[0], "nombre": row[1], "fecha_creacion": row[3], "tipo": row[4]}

        cur.execute("""
            SELECT i.id, p.id AS producto_id, p.codigo, p.nombre, p.unidad_medida,
                   p.stock_actual                                          AS stock_ahora,
                   i.cantidad_teorica,
                   i.cantidad_fisica,
                   i.cantidad_ajustada,
                   COALESCE(i.cantidad_ajustada, i.cantidad_fisica)        AS cantidad_final,
                   i.fecha_captura
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY ABS(COALESCE(i.cantidad_ajustada, i.cantidad_fisica)
                         - p.stock_actual) DESC
        """, (sesion_id,))
        items_raw = _rows(cur)
        product_ids_contados = [i["producto_id"] for i in items_raw]

        # Movimientos por producto desde apertura de sesión
        if items_raw:
            cur.execute("""
                SELECT
                    m.producto_id,
                    SUM(CASE WHEN m.tipo = 'entrada' THEN m.cantidad ELSE -m.cantidad END) AS mov_neto,
                    COUNT(*)                                                                AS num_movs,
                    STRING_AGG(DISTINCT m.motivo, ', ')                                    AS motivos
                FROM movimientos_stock m
                WHERE m.producto_id = ANY(%s)
                  AND m.fecha >= %s
                  AND m.motivo != 'Ajuste por inventario físico'
                GROUP BY m.producto_id
            """, (product_ids_contados, sesion["fecha_creacion"]))
            mov_map = {
                r[0]: {"neto": float(r[1] or 0), "count": int(r[2]), "motivos": r[3] or ""}
                for r in cur.fetchall()
            }
        else:
            mov_map = {}

        no_contados, sin_area = _cargar_no_contados(
            cur, sesion_id, sesion["tipo"], sesion["fecha_creacion"], product_ids_contados
        )

    items = []
    tiene_discrepancias = False
    for i in items_raw:
        stock_ahora  = float(i["stock_ahora"] or 0)
        teorica      = float(i["cantidad_teorica"] or 0)
        final        = float(i["cantidad_final"])
        delta_conteo = final - teorica
        ajuste_real  = final - stock_ahora
        mov          = mov_map.get(i["producto_id"], {"neto": 0.0, "count": 0, "motivos": ""})
        stock_cambio = stock_ahora - teorica

        discrepancia = abs(stock_cambio) > 0.01 and abs(ajuste_real) > 0.01
        if discrepancia:
            tiene_discrepancias = True

        items.append({
            **i,
            "stock_ahora": stock_ahora,
            "delta_conteo": delta_conteo,
            "ajuste_real": ajuste_real,
            "stock_cambio": stock_cambio,
            "mov_neto": mov["neto"],
            "mov_count": mov["count"],
            "mov_motivos": mov["motivos"],
            "discrepancia": discrepancia,
            "tipo_fila": "contado",
        })

    return templates.TemplateResponse(
        request=request,
        name="preinventario/_preaprobacion.html",
        context={
            "user": user,
            "sesion": sesion,
            "items": items,
            "no_contados": no_contados,
            "sin_area": sin_area,
            "tiene_discrepancias": tiene_discrepancias,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Aprobar sesión → aplica ajustes al stock
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin/sesion/{sesion_id}/aprobar", response_class=HTMLResponse)
async def aprobar_sesion(
    request: Request,
    sesion_id: int,
    clave: str = Form(...),
    notas_aprobacion: str = Form(""),
    confirmar_discrepancias: str = Form(""),
    user=Depends(require_rol("Administrador")),
):
    # ── Verificar contraseña del admin ────────────────────────────────────────
    with pool_usuarios.conexion() as (_, cur):
        cur.execute(
            "SELECT password_hash FROM usuarios WHERE username = %s AND activo = 1",
            (user["username"],),
        )
        row = cur.fetchone()
    if not row or not verificar_password(clave, row[0]):
        # Devolver el modal con error sin cerrar
        return templates.TemplateResponse(
            request=request,
            name="preinventario/_preaprobacion.html",
            context={
                "user": user,
                "sesion": {"id": sesion_id, "nombre": ""},
                "items": [],
                "tiene_discrepancias": False,
                "error_clave": "Contraseña incorrecta. Verifique e intente de nuevo.",
            },
            status_code=401,
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute(
            "SELECT estado, nombre, tipo FROM preinventario_sesiones WHERE id = %s FOR UPDATE",
            (sesion_id,),
        )
        row = cur.fetchone()
        if not row or row[0] != "cerrada":
            raise HTTPException(400, "La sesión debe estar en estado 'cerrada' para aprobar.")
        sesion_nombre = row[1]
        sesion_tipo   = row[2]

        # ── Productos contados ────────────────────────────────────────────
        cur.execute("""
            SELECT i.producto_id, p.nombre, p.stock_actual,
                   p.codigo, p.unidad_medida,
                   i.cantidad_teorica, i.cantidad_fisica, i.cantidad_ajustada,
                   COALESCE(i.cantidad_ajustada, i.cantidad_fisica) AS cantidad_final
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
        """, (sesion_id,))
        items_contados = cur.fetchall()
        product_ids_contados = [r[0] for r in items_contados]

        snapshot_items = []

        def _aplicar_ajuste(cur, producto_id, stock_antes, cantidad_final,
                            codigo, nombre, unidad, cant_teorica, cant_fisica,
                            cant_ajustada, notas_aprobacion, sesion_id, usuario):
            stock_antes    = float(stock_antes or 0)
            cantidad_final = float(cantidad_final)
            diferencia     = cantidad_final - stock_antes
            snapshot_items.append({
                "producto_id":      producto_id,
                "codigo":           codigo,
                "nombre":           nombre,
                "unidad_medida":    unidad,
                "cantidad_teorica": float(cant_teorica or 0) if cant_teorica is not None else None,
                "cantidad_fisica":  float(cant_fisica) if cant_fisica is not None else None,
                "cantidad_ajustada": float(cant_ajustada) if cant_ajustada is not None else None,
                "stock_antes":      stock_antes,
                "stock_despues":    cantidad_final,
                "diferencia":       diferencia,
            })
            if abs(diferencia) < 0.001:
                return
            tipo_mov     = "entrada" if diferencia > 0 else "salida"
            cantidad_mov = abs(diferencia)
            cur.execute(
                "UPDATE productos SET stock_actual = %s WHERE id = %s",
                (cantidad_final, producto_id),
            )
            cur.execute("""
                INSERT INTO movimientos_stock
                    (producto_id, tipo, motivo, cantidad,
                     stock_antes, stock_despues, referencia, notas, usuario)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (producto_id, tipo_mov, "Ajuste por inventario físico",
                  cantidad_mov, stock_antes, cantidad_final,
                  f"PREINV-{sesion_id}", notas_aprobacion or None, usuario))

        for (producto_id, nombre, stock_antes, codigo, unidad,
             cant_teorica, cant_fisica, cant_ajustada, cantidad_final) in items_contados:
            _aplicar_ajuste(cur, producto_id, stock_antes, cantidad_final,
                            codigo, nombre, unidad, cant_teorica, cant_fisica,
                            cant_ajustada, notas_aprobacion, sesion_id, user["nombre"])

        # ── Productos no contados (solo inventario completo) ──────────────
        no_contados_rows, _ = _cargar_no_contados(
            cur, sesion_id, sesion_tipo, None, product_ids_contados
        )
        for nc in no_contados_rows:
            cur.execute(
                "SELECT stock_actual FROM productos WHERE id = %s", (nc["producto_id"],)
            )
            stock_row = cur.fetchone()
            stock_actual = float(stock_row[0] or 0) if stock_row else 0.0
            _aplicar_ajuste(cur, nc["producto_id"], stock_actual, 0.0,
                            nc.get("codigo"), nc["nombre"], nc.get("unidad_medida"),
                            None, None, None,
                            notas_aprobacion, sesion_id, user["nombre"])

        # ── Guardar estado aprobado ───────────────────────────────────────
        cur.execute("""
            UPDATE preinventario_sesiones
            SET estado = 'aprobada', aprobado_por = %s,
                fecha_aprobacion = NOW(), notas_aprobacion = %s
            WHERE id = %s
        """, (user["nombre"], notas_aprobacion or None, sesion_id))

        items_ajustados = sum(1 for it in snapshot_items if abs(it["diferencia"]) > 0.001)
        cur.execute("""
            INSERT INTO preinventario_historico
                (sesion_id, nombre, aprobado_por, total_items, items_ajustados, snapshot)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb)
        """, (
            sesion_id, sesion_nombre, user["nombre"],
            len(snapshot_items), items_ajustados,
            json.dumps({"items": snapshot_items}),
        ))

    return RedirectResponse(f"/preinventario/admin/sesion/{sesion_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Rechazar sesión
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin/sesion/{sesion_id}/rechazar", response_class=HTMLResponse)
async def rechazar_sesion(
    request: Request,
    sesion_id: int,
    notas_aprobacion: str = Form(""),
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE preinventario_sesiones
            SET estado = 'rechazada', aprobado_por = %s,
                fecha_aprobacion = NOW(), notas_aprobacion = %s
            WHERE id = %s AND estado = 'cerrada'
        """, (user["nombre"], notas_aprobacion or None, sesion_id))

    return RedirectResponse(f"/preinventario/admin/sesion/{sesion_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — Historial de cierres aprobados
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/admin/historico", response_class=HTMLResponse)
async def admin_historico(
    request: Request,
    user=Depends(require_rol("Administrador")),
):
    _asegurar_tablas(user["empresa_db"])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, sesion_id, nombre, fecha_aprobacion,
                   aprobado_por, total_items, items_ajustados
            FROM preinventario_historico
            ORDER BY fecha_aprobacion DESC
            LIMIT 100
        """)
        snapshots = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/admin_historico.html",
        context={
            "user": user,
            "snapshots": snapshots,
            "seccion": "preinventario",
        },
    )


@router.get("/admin/historico/{hist_id}", response_class=HTMLResponse)
async def admin_historico_detalle(
    request: Request,
    hist_id: int,
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, sesion_id, nombre, fecha_aprobacion,
                   aprobado_por, total_items, items_ajustados, snapshot
            FROM preinventario_historico
            WHERE id = %s
        """, (hist_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Registro no encontrado")
        cols = ["id", "sesion_id", "nombre", "fecha_aprobacion",
                "aprobado_por", "total_items", "items_ajustados", "snapshot"]
        hist = dict(zip(cols, row))
        items = hist["snapshot"].get("items", []) if hist["snapshot"] else []

    return templates.TemplateResponse(
        request=request,
        name="preinventario/admin_historico_detalle.html",
        context={
            "user": user,
            "hist": hist,
            "items": items,
            "seccion": "preinventario",
        },
    )
