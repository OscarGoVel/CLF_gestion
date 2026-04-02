# -*- coding: utf-8 -*-
"""
web_app/routers/estudio_mercado.py
Módulo de Estudio de Mercado: crear estudios, capturar cotizaciones de proveedores
y aplicar el precio ganador al catálogo de productos.
"""

from datetime import date as _date, datetime as _dt
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.rbac import require_rol

router = APIRouter(prefix="/estudio-mercado")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [{c: _f(v) for c, v in zip(cols, row)} for row in cur.fetchall()]


def _asegurar_tablas(empresa_db: str) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS estudios_mercado (
        id             SERIAL PRIMARY KEY,
        nombre         TEXT NOT NULL,
        fecha          TEXT NOT NULL,
        descripcion    TEXT,
        estado         TEXT NOT NULL DEFAULT 'abierto',
        fecha_registro TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS estudio_mercado_items (
        id              SERIAL PRIMARY KEY,
        estudio_id      INTEGER NOT NULL REFERENCES estudios_mercado(id) ON DELETE CASCADE,
        producto_id     INTEGER REFERENCES productos(id),
        nombre_articulo TEXT NOT NULL,
        cantidad        REAL NOT NULL DEFAULT 1,
        unidad          TEXT
    );
    CREATE TABLE IF NOT EXISTS estudio_mercado_cotizaciones (
        id               SERIAL PRIMARY KEY,
        item_id          INTEGER NOT NULL REFERENCES estudio_mercado_items(id) ON DELETE CASCADE,
        proveedor_id     INTEGER REFERENCES proveedores(id),
        nombre_proveedor TEXT NOT NULL,
        precio_unitario  REAL NOT NULL,
        notas            TEXT
    );
    """
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        for stmt in ddl.strip().split(";"):
            s = stmt.strip()
            if s:
                cur.execute(s)


# ─────────────────────────────────────────────────────────────────────────────
# LISTA DE ESTUDIOS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def lista_estudios(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
):
    _asegurar_tablas(user["empresa_db"])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT e.id, e.nombre, e.fecha, e.estado, e.fecha_registro,
                   COUNT(DISTINCT i.id) AS total_items,
                   COUNT(DISTINCT c.id) AS total_cotizaciones
            FROM estudios_mercado e
            LEFT JOIN estudio_mercado_items i ON i.estudio_id = e.id
            LEFT JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id
            GROUP BY e.id
            ORDER BY e.fecha_registro DESC
        """)
        estudios = _rows(cur)

    return templates.TemplateResponse(
        request=request,
        name="estudio_mercado/index.html",
        context={"user": user, "estudios": estudios, "seccion": "catalogos"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREAR ESTUDIO
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", response_class=HTMLResponse)
async def crear_estudio(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    user=Depends(require_rol("Administrador", "Operador")),
):
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse("/estudio-mercado", status_code=303)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO estudios_mercado (nombre, fecha, descripcion)
            VALUES (%s, %s, %s) RETURNING id
        """, (nombre, _date.today().isoformat(), descripcion.strip() or None))
        estudio_id = cur.fetchone()[0]

    return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# DETALLE DE ESTUDIO
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{estudio_id}", response_class=HTMLResponse)
async def detalle_estudio(
    request: Request,
    estudio_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre, fecha, descripcion, estado FROM estudios_mercado WHERE id = %s",
            (estudio_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Estudio no encontrado")
        estudio = dict(zip(["id", "nombre", "fecha", "descripcion", "estado"], row))

        # Items con sus cotizaciones
        cur.execute("""
            SELECT i.id, i.nombre_articulo, i.cantidad, i.unidad, i.producto_id,
                   p.codigo AS producto_codigo
            FROM estudio_mercado_items i
            LEFT JOIN productos p ON p.id = i.producto_id
            WHERE i.estudio_id = %s
            ORDER BY i.id
        """, (estudio_id,))
        items = _rows(cur)

        for item in items:
            cur.execute("""
                SELECT id, nombre_proveedor, precio_unitario, notas
                FROM estudio_mercado_cotizaciones
                WHERE item_id = %s
                ORDER BY precio_unitario ASC
            """, (item["id"],))
            cotizaciones = _rows(cur)
            item["cotizaciones"] = cotizaciones
            item["precio_minimo"] = cotizaciones[0]["precio_unitario"] if cotizaciones else None

        # Proveedores para el selector
        cur.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
        proveedores = [dict(zip(["id", "nombre"], r)) for r in cur.fetchall()]

        # Productos para el selector de items
        cur.execute("SELECT id, codigo, nombre FROM productos ORDER BY nombre LIMIT 200")
        productos = [dict(zip(["id", "codigo", "nombre"], r)) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="estudio_mercado/detalle.html",
        context={
            "user": user,
            "estudio": estudio,
            "items": items,
            "proveedores": proveedores,
            "productos": productos,
            "seccion": "catalogos",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# AGREGAR ITEM
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{estudio_id}/item", response_class=HTMLResponse)
async def agregar_item(
    request: Request,
    estudio_id: int,
    nombre_articulo: str = Form(...),
    cantidad: float = Form(1.0),
    unidad: str = Form(""),
    producto_id: str = Form(""),
    user=Depends(require_rol("Administrador", "Operador")),
):
    pid = int(producto_id) if producto_id.strip() else None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT estado FROM estudios_mercado WHERE id = %s", (estudio_id,))
        row = cur.fetchone()
        if not row or row[0] == "cerrado":
            raise HTTPException(400, "El estudio está cerrado.")

        cur.execute("""
            INSERT INTO estudio_mercado_items
                (estudio_id, producto_id, nombre_articulo, cantidad, unidad)
            VALUES (%s, %s, %s, %s, %s)
        """, (estudio_id, pid, nombre_articulo.strip(), cantidad, unidad.strip() or None))

    return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR ITEM
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/item/{item_id}/eliminar", response_class=HTMLResponse)
async def eliminar_item(
    request: Request,
    item_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "DELETE FROM estudio_mercado_items WHERE id = %s RETURNING estudio_id",
            (item_id,)
        )
        row = cur.fetchone()
        estudio_id = row[0] if row else None

    if estudio_id:
        return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)
    return RedirectResponse("/estudio-mercado", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# AGREGAR COTIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/item/{item_id}/cotizacion", response_class=HTMLResponse)
async def agregar_cotizacion(
    request: Request,
    item_id: int,
    nombre_proveedor: str = Form(...),
    precio_unitario: float = Form(...),
    notas: str = Form(""),
    proveedor_id: str = Form(""),
    user=Depends(require_rol("Administrador", "Operador")),
):
    pid = int(proveedor_id) if proveedor_id.strip() else None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT estudio_id FROM estudio_mercado_items WHERE id = %s", (item_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404)
        estudio_id = row[0]

        cur.execute("""
            INSERT INTO estudio_mercado_cotizaciones
                (item_id, proveedor_id, nombre_proveedor, precio_unitario, notas)
            VALUES (%s, %s, %s, %s, %s)
        """, (item_id, pid, nombre_proveedor.strip(), precio_unitario, notas.strip() or None))

    return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR COTIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/cotizacion/{cot_id}/eliminar", response_class=HTMLResponse)
async def eliminar_cotizacion(
    request: Request,
    cot_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            DELETE FROM estudio_mercado_cotizaciones WHERE id = %s
            RETURNING (SELECT estudio_id FROM estudio_mercado_items WHERE id = item_id)
        """, (cot_id,))
        row = cur.fetchone()
        estudio_id = row[0] if row else None

    if estudio_id:
        return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)
    return RedirectResponse("/estudio-mercado", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# APLICAR PRECIO GANADOR AL PRODUCTO
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/item/{item_id}/aplicar", response_class=HTMLResponse)
async def aplicar_precio_ganador(
    request: Request,
    item_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Obtener item y precio mínimo
        cur.execute("""
            SELECT i.producto_id, i.nombre_articulo,
                   e.nombre AS estudio_nombre, e.id AS estudio_id,
                   MIN(c.precio_unitario) AS precio_minimo
            FROM estudio_mercado_items i
            JOIN estudios_mercado e ON e.id = i.estudio_id
            LEFT JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id
            WHERE i.id = %s
            GROUP BY i.producto_id, i.nombre_articulo, e.nombre, e.id
        """, (item_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Item no encontrado")

        producto_id, nombre_articulo, estudio_nombre, estudio_id, precio_minimo = row

        if precio_minimo is None:
            raise HTTPException(400, "El item no tiene cotizaciones.")
        if not producto_id:
            raise HTTPException(400, "El item no está vinculado a un producto del catálogo.")

        precio_minimo = float(precio_minimo)

        # Obtener precio actual
        cur.execute("SELECT precio_base FROM productos WHERE id = %s", (producto_id,))
        p_row = cur.fetchone()
        if not p_row:
            raise HTTPException(404, "Producto no encontrado.")
        precio_actual = float(p_row[0] or 0)

        # Actualizar solo si hay cambio real
        if abs(precio_minimo - precio_actual) > 0.001:
            cur.execute(
                "UPDATE productos SET precio_base = %s WHERE id = %s",
                (precio_minimo, producto_id)
            )
            cur.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente)
                VALUES (%s, %s, %s, %s, 'estudio_mercado')
            """, (
                producto_id, precio_minimo,
                _date.today().isoformat(),
                f"Estudio de mercado: {estudio_nombre}",
            ))

    return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# CERRAR ESTUDIO
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{estudio_id}/cerrar", response_class=HTMLResponse)
async def cerrar_estudio(
    request: Request,
    estudio_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE estudios_mercado SET estado = 'cerrado' WHERE id = %s",
            (estudio_id,)
        )

    return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)
