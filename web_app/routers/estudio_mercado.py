# -*- coding: utf-8 -*-
"""
web_app/routers/estudio_mercado.py
Módulo de Estudio de Mercado: crear estudios, capturar cotizaciones de proveedores,
comparar precios horizontalmente y aplicar precios al catálogo o a cotizaciones.
"""

from datetime import date as _date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.rbac import require_rol

router = APIRouter(prefix="/estudio-mercado")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

_ESTADOS_AVANZADOS = {"Parcialmente Entregada", "Entregada", "Facturada", "Pagada"}


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


def _pivotear_items(items_raw: list[dict], margen_pct: float) -> tuple[list[dict], list[str]]:
    """
    Convierte la lista plana de ítems+cotizaciones en estructura pivotada:
    - proveedores_unicos: lista ordenada de nombres de proveedor del estudio
    - items: cada ítem lleva precios_por_prov {nombre: precio}, min_precio, precio_estimado
    """
    # Recolectar todos los proveedores únicos del estudio
    proveedores_set: list[str] = []
    for item in items_raw:
        for cot in item.get("cotizaciones", []):
            nombre = cot["nombre_proveedor"]
            if nombre not in proveedores_set:
                proveedores_set.append(nombre)

    for item in items_raw:
        precios_por_prov: dict[str, float | None] = {p: None for p in proveedores_set}
        for cot in item.get("cotizaciones", []):
            precios_por_prov[cot["nombre_proveedor"]] = cot["precio_unitario"]

        precios_validos = [v for v in precios_por_prov.values() if v is not None]
        min_precio = min(precios_validos) if precios_validos else None
        precio_estimado = round(min_precio * (1 + margen_pct), 4) if min_precio is not None else None

        item["precios_por_prov"] = precios_por_prov
        item["min_precio"] = min_precio
        item["precio_estimado"] = precio_estimado
        # nombre del mejor proveedor
        if min_precio is not None:
            for cot in item["cotizaciones"]:
                if cot["precio_unitario"] == min_precio:
                    item["mejor_proveedor"] = cot["nombre_proveedor"]
                    break
        else:
            item["mejor_proveedor"] = None

    return items_raw, proveedores_set


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
# CREAR ESTUDIO (libre)
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
# CREAR ESTUDIO DESDE COTIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/desde-cotizacion/{cot_id}", response_class=HTMLResponse)
async def crear_desde_cotizacion(
    request: Request,
    cot_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    _asegurar_tablas(user["empresa_db"])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT folio FROM cotizaciones WHERE id = %s",
            (cot_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Cotización no encontrada")
        folio = row[0]

        cur.execute("""
            INSERT INTO estudios_mercado (nombre, fecha, cotizacion_id)
            VALUES (%s, %s, %s) RETURNING id
        """, (f"Estudio – {folio}", _date.today().isoformat(), cot_id))
        estudio_id = cur.fetchone()[0]

        # Pre-llenar ítems con las líneas de la cotización (solo las con producto_id)
        cur.execute("""
            SELECT cd.producto_id,
                   COALESCE(cd.descripcion_libre, p.nombre) AS nombre_articulo,
                   cd.cantidad,
                   p.unidad_medida
            FROM cotizacion_detalle cd
            LEFT JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s AND cd.producto_id IS NOT NULL
            ORDER BY cd.id
        """, (cot_id,))
        lineas = cur.fetchall()

        for prod_id, nombre_art, cantidad, unidad in lineas:
            cur.execute("""
                INSERT INTO estudio_mercado_items
                    (estudio_id, producto_id, nombre_articulo, cantidad, unidad)
                VALUES (%s, %s, %s, %s, %s)
            """, (estudio_id, prod_id, nombre_art, cantidad, unidad))

    return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# DETALLE DE ESTUDIO (vista horizontal pivotada)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{estudio_id}", response_class=HTMLResponse)
async def detalle_estudio(
    request: Request,
    estudio_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT e.id, e.nombre, e.fecha, e.descripcion, e.estado,
                   COALESCE(e.margen_pct, 0.35) AS margen_pct,
                   e.cotizacion_id,
                   c.folio AS cot_folio,
                   cl.nombre_comercial AS cot_cliente
            FROM estudios_mercado e
            LEFT JOIN cotizaciones c ON c.id = e.cotizacion_id
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE e.id = %s
        """, (estudio_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Estudio no encontrado")
        cols = ["id", "nombre", "fecha", "descripcion", "estado", "margen_pct",
                "cotizacion_id", "cot_folio", "cot_cliente"]
        estudio = {c: _f(v) for c, v in zip(cols, row)}

        # Items con sus cotizaciones
        cur.execute("""
            SELECT i.id, i.nombre_articulo, i.cantidad, i.unidad, i.producto_id,
                   p.codigo AS producto_codigo, p.precio_venta AS precio_venta_actual
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
            item["cotizaciones"] = _rows(cur)

        # Pivotear para vista horizontal
        items, proveedores_unicos = _pivotear_items(items, float(estudio["margen_pct"]))

        # Historial de aplicaciones de este estudio
        cur.execute("""
            SELECT ea.fecha, ea.forzado, ea.estado_cot,
                   c.folio AS cot_folio,
                   u.nombre AS aplicado_por
            FROM estudio_aplicaciones ea
            JOIN cotizaciones c ON c.id = ea.cotizacion_id
            LEFT JOIN usuarios u ON u.id = ea.aplicado_por
            WHERE ea.estudio_id = %s
            ORDER BY ea.fecha DESC
        """, (estudio_id,))
        historial = _rows(cur)

        # Proveedores para el selector
        cur.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
        proveedores = [dict(zip(["id", "nombre"], r)) for r in cur.fetchall()]

        # Productos para el selector de items
        cur.execute("SELECT id, codigo, nombre FROM productos ORDER BY nombre")
        productos = [dict(zip(["id", "codigo", "nombre"], r)) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="estudio_mercado/detalle.html",
        context={
            "user": user,
            "estudio": estudio,
            "items": items,
            "proveedores_unicos": proveedores_unicos,
            "proveedores": proveedores,
            "productos": productos,
            "historial": historial,
            "margen_pct_display": round(float(estudio["margen_pct"]) * 100, 2),
            "seccion": "catalogos",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# ACTUALIZAR MARGEN DEL ESTUDIO
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{estudio_id}/margen", response_class=HTMLResponse)
async def actualizar_margen(
    request: Request,
    estudio_id: int,
    margen_pct: float = Form(...),
    user=Depends(require_rol("Administrador", "Operador")),
):
    # Recibir como porcentaje (ej. 35) y guardar como decimal (0.35)
    margen_decimal = max(0.0, min(margen_pct, 100.0)) / 100.0

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE estudios_mercado SET margen_pct = %s WHERE id = %s",
            (margen_decimal, estudio_id)
        )

    return RedirectResponse(f"/estudio-mercado/{estudio_id}", status_code=303)


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
# AGREGAR COTIZACIÓN DE PROVEEDOR A UN ÍTEM
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
# APLICAR PRECIO GANADOR AL CATÁLOGO (precio_base + precio_venta)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/item/{item_id}/aplicar", response_class=HTMLResponse)
async def aplicar_precio_ganador(
    request: Request,
    item_id: int,
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT i.producto_id, i.nombre_articulo,
                   e.nombre AS estudio_nombre, e.id AS estudio_id,
                   COALESCE(e.margen_pct, 0.35) AS margen_pct,
                   MIN(c.precio_unitario) AS precio_minimo
            FROM estudio_mercado_items i
            JOIN estudios_mercado e ON e.id = i.estudio_id
            LEFT JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id
            WHERE i.id = %s
            GROUP BY i.producto_id, i.nombre_articulo, e.nombre, e.id, e.margen_pct
        """, (item_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Item no encontrado")

        producto_id, nombre_articulo, estudio_nombre, estudio_id, margen_pct, precio_minimo = row

        if precio_minimo is None:
            raise HTTPException(400, "El item no tiene cotizaciones.")
        if not producto_id:
            raise HTTPException(400, "El item no está vinculado a un producto del catálogo.")

        precio_minimo = float(precio_minimo)
        margen_pct = float(margen_pct)
        precio_venta = round(precio_minimo * (1 + margen_pct), 4)

        cur.execute("SELECT precio_base FROM productos WHERE id = %s", (producto_id,))
        p_row = cur.fetchone()
        if not p_row:
            raise HTTPException(404, "Producto no encontrado.")
        precio_actual = float(p_row[0] or 0)

        if abs(precio_minimo - precio_actual) > 0.001:
            cur.execute(
                "UPDATE productos SET precio_base = %s, precio_venta = %s WHERE id = %s",
                (precio_minimo, precio_venta, producto_id)
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
        else:
            # Solo actualizar precio_venta aunque no haya cambio en precio_base
            cur.execute(
                "UPDATE productos SET precio_venta = %s WHERE id = %s",
                (precio_venta, producto_id)
            )

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


# ─────────────────────────────────────────────────────────────────────────────
# ENVIAR PRECIOS A COTIZACIÓN — Paso 1: seleccionar cotización
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{estudio_id}/enviar-cotizacion", response_class=HTMLResponse)
async def enviar_cotizacion_get(
    request: Request,
    estudio_id: int,
    cotizacion_id: int | None = None,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT e.id, e.nombre, e.estado,
                   COALESCE(e.margen_pct, 0.35) AS margen_pct
            FROM estudios_mercado e WHERE e.id = %s
        """, (estudio_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Estudio no encontrado")
        estudio = dict(zip(["id", "nombre", "estado", "margen_pct"], [_f(v) for v in row]))

        # Ítems del estudio con precios
        cur.execute("""
            SELECT i.id, i.nombre_articulo, i.cantidad, i.unidad, i.producto_id,
                   MIN(c.precio_unitario) AS min_precio
            FROM estudio_mercado_items i
            LEFT JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id
            WHERE i.estudio_id = %s
            GROUP BY i.id, i.nombre_articulo, i.cantidad, i.unidad, i.producto_id
            HAVING MIN(c.precio_unitario) IS NOT NULL
            ORDER BY i.id
        """, (estudio_id,))
        items = _rows(cur)
        margen = float(estudio["margen_pct"])
        for item in items:
            item["precio_estimado"] = round(float(item["min_precio"]) * (1 + margen), 4)

        if not items:
            raise HTTPException(400, "El estudio no tiene ítems con precios.")

        # Si no se seleccionó cotización aún → mostrar selector
        if cotizacion_id is None:
            cur.execute("""
                SELECT c.id, c.folio, COALESCE(cl.nombre_comercial, '— sin cliente —') AS cliente, c.estado
                FROM cotizaciones c
                LEFT JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.estado NOT IN ('Cancelada', 'Pagada')
                ORDER BY c.fecha DESC
                LIMIT 200
            """)
            cotizaciones = _rows(cur)
            return templates.TemplateResponse(
                request=request,
                name="estudio_mercado/enviar_seleccionar.html",
                context={"user": user, "estudio": estudio, "cotizaciones": cotizaciones,
                         "seccion": "catalogos"},
            )

        # Cotización seleccionada → mostrar pantalla de mapeo
        cur.execute("""
            SELECT c.id, c.folio, c.estado,
                   COALESCE(cl.nombre_comercial, '— sin cliente —') AS cliente
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = %s
        """, (cotizacion_id,))
        cot_row = cur.fetchone()
        if not cot_row:
            raise HTTPException(404, "Cotización no encontrada")
        cotizacion = dict(zip(["id", "folio", "estado", "cliente"], cot_row))

        # Líneas de la cotización
        cur.execute("""
            SELECT cd.id,
                   COALESCE(cd.descripcion_libre, p.nombre, '— sin nombre —') AS descripcion,
                   cd.cantidad,
                   cd.precio_unitario,
                   cd.producto_id,
                   p.precio_venta AS precio_venta_catalogo
            FROM cotizacion_detalle cd
            LEFT JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
        """, (cotizacion_id,))
        lineas_cot = _rows(cur)

        es_estado_avanzado = cotizacion["estado"] in _ESTADOS_AVANZADOS
        es_admin = user.get("rol") == "Administrador"

    return templates.TemplateResponse(
        request=request,
        name="estudio_mercado/enviar_mapeo.html",
        context={
            "user": user,
            "estudio": estudio,
            "cotizacion": cotizacion,
            "items": items,
            "lineas_cot": lineas_cot,
            "es_estado_avanzado": es_estado_avanzado,
            "es_admin": es_admin,
            "seccion": "catalogos",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENVIAR PRECIOS A COTIZACIÓN — Paso 2: confirmar y aplicar
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{estudio_id}/enviar-cotizacion", response_class=HTMLResponse)
async def enviar_cotizacion_post(
    request: Request,
    estudio_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    form = await request.form()
    cotizacion_id = int(form.get("cotizacion_id"))
    forzar = form.get("forzar") == "true"

    # Recolectar mappings: item_{item_id} = cotizacion_detalle_id | "nueva"
    mappings: list[tuple[int, str]] = []
    for key, val in form.items():
        if key.startswith("item_") and val:
            item_id = int(key[5:])
            mappings.append((item_id, val))

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Verificar cotización y estado
        cur.execute("SELECT estado FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        cot_row = cur.fetchone()
        if not cot_row:
            raise HTTPException(404, "Cotización no encontrada")
        estado_cot = cot_row[0]

        if estado_cot in _ESTADOS_AVANZADOS:
            if user.get("rol") != "Administrador":
                raise HTTPException(403, "Se requiere autorización de administrador para modificar esta cotización.")
            if not forzar:
                raise HTTPException(400, "Se requiere confirmación explícita para estados avanzados.")

        # Obtener margen del estudio
        cur.execute(
            "SELECT COALESCE(margen_pct, 0.35) FROM estudios_mercado WHERE id = %s",
            (estudio_id,)
        )
        margen_pct = float(cur.fetchone()[0])

        # Procesar cada mapping
        for item_id, destino in mappings:
            # Obtener precio estimado del ítem
            cur.execute("""
                SELECT i.nombre_articulo, i.cantidad, i.unidad, i.producto_id,
                       MIN(c.precio_unitario) AS min_precio
                FROM estudio_mercado_items i
                LEFT JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id
                WHERE i.id = %s
                GROUP BY i.id
            """, (item_id,))
            item_row = cur.fetchone()
            if not item_row or item_row[4] is None:
                continue
            nombre_art, cantidad, unidad, producto_id, min_precio = item_row
            precio_estimado = round(float(min_precio) * (1 + margen_pct), 4)

            if destino == "nueva":
                # Insertar nueva línea en la cotización
                aplica_iva = False
                if producto_id:
                    cur.execute("SELECT aplica_iva FROM productos WHERE id = %s", (producto_id,))
                    iva_row = cur.fetchone()
                    aplica_iva = bool(iva_row[0]) if iva_row else False

                subtotal = round(float(cantidad) * precio_estimado, 4)
                iva = round(subtotal * 0.16, 4) if aplica_iva else 0.0
                total = round(subtotal + iva, 4)

                cur.execute("""
                    INSERT INTO cotizacion_detalle
                        (cotizacion_id, producto_id, descripcion_libre, cantidad,
                         precio_unitario, subtotal, iva, total, aplica_iva)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (cotizacion_id, producto_id, nombre_art if not producto_id else None,
                      cantidad, precio_estimado, subtotal, iva, total, aplica_iva))
            else:
                # Actualizar línea existente
                detalle_id = int(destino)
                cur.execute("""
                    SELECT cantidad, aplica_iva FROM cotizacion_detalle WHERE id = %s
                """, (detalle_id,))
                det_row = cur.fetchone()
                if not det_row:
                    continue
                cant_cot, aplica_iva = det_row
                subtotal = round(float(cant_cot) * precio_estimado, 4)
                iva = round(subtotal * 0.16, 4) if aplica_iva else 0.0
                total = round(subtotal + iva, 4)
                cur.execute("""
                    UPDATE cotizacion_detalle
                    SET precio_unitario = %s, subtotal = %s, iva = %s, total = %s
                    WHERE id = %s
                """, (precio_estimado, subtotal, iva, total, detalle_id))

        # Recalcular totales de la cotización
        cur.execute("""
            SELECT COALESCE(SUM(subtotal), 0), COALESCE(SUM(iva), 0), COALESCE(SUM(total), 0)
            FROM cotizacion_detalle WHERE cotizacion_id = %s
        """, (cotizacion_id,))
        subtotal_t, iva_t, total_t = cur.fetchone()
        cur.execute("""
            UPDATE cotizaciones SET subtotal = %s, iva = %s, total = %s WHERE id = %s
        """, (subtotal_t, iva_t, total_t, cotizacion_id))

        # Registrar en historial
        user_id = user.get("id")
        cur.execute("""
            INSERT INTO estudio_aplicaciones
                (estudio_id, cotizacion_id, aplicado_por, forzado, estado_cot)
            VALUES (%s, %s, %s, %s, %s)
        """, (estudio_id, cotizacion_id, user_id, forzar, estado_cot))

    return RedirectResponse(f"/cotizaciones/{cotizacion_id}", status_code=303)
