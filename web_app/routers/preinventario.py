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

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
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
CREATE TABLE IF NOT EXISTS preinventario_sesiones (
    id               SERIAL PRIMARY KEY,
    nombre           TEXT NOT NULL,
    creado_por       TEXT NOT NULL,
    estado           TEXT NOT NULL DEFAULT 'abierta',
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
"""


def _asegurar_tablas(empresa_db: str) -> None:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)


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
                   s.fecha_creacion, s.fecha_cierre,
                   COUNT(i.id) AS total_items
            FROM preinventario_sesiones s
            LEFT JOIN preinventario_items i ON i.sesion_id = s.id
            GROUP BY s.id
            ORDER BY s.fecha_creacion DESC
            LIMIT 50
        """)
        sesiones = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="preinventario/index.html",
        context={"user": user, "sesiones": sesiones, "seccion": "preinventario"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# OPERARIO — Crear sesión
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sesion", response_class=HTMLResponse)
async def crear_sesion(
    request: Request,
    nombre: str = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse("/preinventario")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO preinventario_sesiones (nombre, creado_por)
            VALUES (%s, %s) RETURNING id
        """, (nombre, user["nombre"]))
        sesion_id = cur.fetchone()[0]

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
            "SELECT id, nombre, estado, creado_por, fecha_creacion FROM preinventario_sesiones WHERE id = %s",
            (sesion_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Sesión no encontrada")
        sesion = dict(zip(["id", "nombre", "estado", "creado_por", "fecha_creacion"], row))

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
# ADMIN — Aprobar sesión → aplica ajustes al stock
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/admin/sesion/{sesion_id}/aprobar", response_class=HTMLResponse)
async def aprobar_sesion(
    request: Request,
    sesion_id: int,
    notas_aprobacion: str = Form(""),
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute(
            "SELECT estado FROM preinventario_sesiones WHERE id = %s FOR UPDATE",
            (sesion_id,)
        )
        row = cur.fetchone()
        if not row or row[0] != "cerrada":
            raise HTTPException(400, "La sesión debe estar en estado 'cerrada' para aprobar.")

        cur.execute("""
            SELECT i.producto_id, p.nombre, p.stock_actual,
                   COALESCE(i.cantidad_ajustada, i.cantidad_fisica) AS cantidad_final
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
        """, (sesion_id,))
        items = cur.fetchall()

        for producto_id, nombre, stock_antes, cantidad_final in items:
            stock_antes = float(stock_antes or 0)
            cantidad_final = float(cantidad_final)
            diferencia = cantidad_final - stock_antes
            if diferencia == 0:
                continue

            tipo = "entrada" if diferencia > 0 else "salida"
            cantidad_mov = abs(diferencia)
            stock_despues = cantidad_final

            cur.execute(
                "UPDATE productos SET stock_actual = %s WHERE id = %s",
                (stock_despues, producto_id)
            )
            cur.execute("""
                INSERT INTO movimientos_stock
                    (producto_id, tipo, motivo, cantidad,
                     stock_antes, stock_despues, referencia, notas, usuario)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                producto_id, tipo,
                "Ajuste por inventario físico",
                cantidad_mov, stock_antes, stock_despues,
                f"PREINV-{sesion_id}",
                notas_aprobacion or None,
                user["nombre"],
            ))

        cur.execute("""
            UPDATE preinventario_sesiones
            SET estado = 'aprobada', aprobado_por = %s,
                fecha_aprobacion = NOW(), notas_aprobacion = %s
            WHERE id = %s
        """, (user["nombre"], notas_aprobacion or None, sesion_id))

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
