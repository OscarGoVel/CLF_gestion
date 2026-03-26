# -*- coding: utf-8 -*-
"""
web_app/routers/catalogos.py
Seccion Catalogos: Clientes, Productos y Proveedores.
"""

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual

router = APIRouter(prefix="/catalogos")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

POR_PAGINA_PRODUCTOS = 30

TIPO_CLIENTE_COLOR = {
    "Empresa":  ("bg-blue-100",   "text-blue-700"),
    "Gobierno": ("bg-purple-100", "text-purple-700"),
    "Persona":  ("bg-green-100",  "text-green-700"),
}


def _floats(d: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Raíz: redirige a clientes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def raiz(request: Request):
    return RedirectResponse("/catalogos/clientes")


# ─────────────────────────────────────────────────────────────────────────────
# CLIENTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/clientes", response_class=HTMLResponse)
async def lista_clientes(request: Request, tipo: str = "", buscar: str = ""):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    where, params = [], []
    if tipo:
        where.append("c.tipo = %s"); params.append(tipo)
    if buscar:
        where.append("(c.nombre_comercial ILIKE %s OR c.rfc ILIKE %s OR c.contacto ILIKE %s)")
        params += [f"%{buscar}%"] * 3
    w = ("WHERE " + " AND ".join(where)) if where else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT c.id, c.nombre_comercial, c.razon_social, c.tipo,
                   c.rfc, c.contacto, c.telefono, c.email,
                   COUNT(cot.id)  AS num_cotizaciones,
                   MAX(cot.fecha) AS ultima_cotizacion
            FROM clientes c
            LEFT JOIN cotizaciones cot ON cot.cliente_id = c.id
            {w}
            GROUP BY c.id
            ORDER BY c.nombre_comercial
        """, params or None)
        cols     = [d[0] for d in cur.description]
        clientes = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

        cur.execute("SELECT DISTINCT tipo FROM clientes WHERE tipo IS NOT NULL ORDER BY tipo")
        tipos = [r[0] for r in cur.fetchall()]

    ctx = {
        "user": user,
        "clientes": clientes,
        "tipos": tipos,
        "tipo_sel": tipo,
        "buscar": buscar,
        "tipo_color": TIPO_CLIENTE_COLOR,
        "seccion": "clientes",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="catalogos/_clientes_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="catalogos/clientes.html", context=ctx
    )


@router.get("/clientes/{cliente_id}", response_class=HTMLResponse)
async def detalle_cliente(request: Request, cliente_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        cliente = _floats(dict(zip([d[0] for d in cur.description], row)))

        cur.execute("""
            SELECT id, folio, fecha, total, estado, orden_compra
            FROM cotizaciones
            WHERE cliente_id = %s
            ORDER BY fecha DESC, id DESC
            LIMIT 20
        """, (cliente_id,))
        dcols = [d[0] for d in cur.description]
        cotizaciones = [_floats(dict(zip(dcols, r))) for r in cur.fetchall()]

        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(total),0),
                   COUNT(*) FILTER (WHERE estado='Pagada'),
                   COUNT(*) FILTER (WHERE estado='Pendiente')
            FROM cotizaciones WHERE cliente_id = %s
        """, (cliente_id,))
        stats_row = cur.fetchone()
        stats = {
            "total_cots": stats_row[0],
            "monto_total": float(stats_row[1]),
            "pagadas":     stats_row[2],
            "pendientes":  stats_row[3],
        }

    from web_app.routers.cotizaciones import ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="catalogos/cliente_detalle.html",
        context={
            "user": user, "cliente": cliente,
            "cotizaciones": cotizaciones, "stats": stats,
            "tipo_color": TIPO_CLIENTE_COLOR,
            "estado_color": ESTADO_COLOR,
            "seccion": "clientes",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTOS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/productos", response_class=HTMLResponse)
async def lista_productos(
    request: Request,
    buscar: str = "",
    categoria: str = "",
    con_stock: str = "",
    pagina: int = 1,
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    where, params = [], []
    if buscar:
        where.append("(p.nombre ILIKE %s OR p.codigo ILIKE %s OR p.descripcion ILIKE %s)")
        params += [f"%{buscar}%"] * 3
    if categoria:
        where.append("cat.nombre = %s"); params.append(categoria)
    if con_stock == "1":
        where.append("p.stock_actual > 0")
    elif con_stock == "0":
        where.append("(p.stock_actual IS NULL OR p.stock_actual = 0)")

    w      = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (pagina - 1) * POR_PAGINA_PRODUCTOS

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   p.precio_base, p.aplica_iva, p.stock_actual, p.stock_minimo,
                   cat.nombre AS categoria, sub.nombre AS subcategoria
            FROM productos p
            LEFT JOIN categorias   cat ON cat.id = p.categoria_id
            LEFT JOIN subcategorias sub ON sub.id = p.subcategoria_id
            {w}
            ORDER BY cat.nombre, p.nombre
            LIMIT {POR_PAGINA_PRODUCTOS} OFFSET {offset}
        """, params or None)
        cols      = [d[0] for d in cur.description]
        productos = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COUNT(*)
            FROM productos p
            LEFT JOIN categorias cat ON cat.id = p.categoria_id
            {w}
        """, params or None)
        total = cur.fetchone()[0]

        cur.execute("SELECT nombre FROM categorias ORDER BY nombre")
        categorias = [r[0] for r in cur.fetchall()]

    total_pags = max(1, (total + POR_PAGINA_PRODUCTOS - 1) // POR_PAGINA_PRODUCTOS)

    ctx = {
        "user": user,
        "productos": productos,
        "categorias": categorias,
        "buscar": buscar,
        "categoria_sel": categoria,
        "con_stock": con_stock,
        "pagina": pagina,
        "total": total,
        "total_pags": total_pags,
        "por_pagina": POR_PAGINA_PRODUCTOS,
        "seccion": "productos",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="catalogos/_productos_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="catalogos/productos.html", context=ctx
    )


@router.get("/productos/{producto_id}", response_class=HTMLResponse)
async def detalle_producto(request: Request, producto_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT p.*,
                   cat.nombre AS categoria,
                   sub.nombre AS subcategoria
            FROM productos p
            LEFT JOIN categorias    cat ON cat.id = p.categoria_id
            LEFT JOIN subcategorias sub ON sub.id = p.subcategoria_id
            WHERE p.id = %s
        """, (producto_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
        producto = _floats(dict(zip([d[0] for d in cur.description], row)))

        # Historial de precios
        cur.execute("""
            SELECT precio, fecha, motivo, fuente
            FROM producto_precio_historial
            WHERE producto_id = %s
            ORDER BY fecha DESC LIMIT 10
        """, (producto_id,))
        hcols     = [d[0] for d in cur.description]
        historial = [_floats(dict(zip(hcols, r))) for r in cur.fetchall()]

        # Proveedores vinculados
        cur.execute("""
            SELECT prov.nombre, prov.telefono, prov.email
            FROM producto_proveedor pp
            JOIN proveedores prov ON prov.id = pp.proveedor_id
            WHERE pp.producto_id = %s
        """, (producto_id,))
        pcols      = [d[0] for d in cur.description]
        proveedores = [dict(zip(pcols, r)) for r in cur.fetchall()]

        # Ultimas cotizaciones donde aparece
        cur.execute("""
            SELECT cot.folio, cot.fecha, cot.estado,
                   cd.cantidad, cd.precio_unitario
            FROM cotizacion_detalle cd
            JOIN cotizaciones cot ON cot.id = cd.cotizacion_id
            WHERE cd.producto_id = %s
            ORDER BY cot.fecha DESC LIMIT 5
        """, (producto_id,))
        ucols    = [d[0] for d in cur.description]
        uso_cots = [_floats(dict(zip(ucols, r))) for r in cur.fetchall()]

    from web_app.routers.cotizaciones import ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="catalogos/producto_detalle.html",
        context={
            "user": user, "producto": producto,
            "historial": historial, "proveedores": proveedores,
            "uso_cots": uso_cots, "estado_color": ESTADO_COLOR,
            "seccion": "productos",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/proveedores", response_class=HTMLResponse)
async def lista_proveedores(request: Request, buscar: str = ""):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    where, params = [], []
    if buscar:
        where.append("(p.nombre ILIKE %s OR p.rfc ILIKE %s OR p.contacto ILIKE %s)")
        params += [f"%{buscar}%"] * 3
    w = ("WHERE " + " AND ".join(where)) if where else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT p.id, p.nombre, p.rfc, p.contacto, p.telefono, p.email,
                   COUNT(pp.producto_id) AS num_productos
            FROM proveedores p
            LEFT JOIN producto_proveedor pp ON pp.proveedor_id = p.id
            {w}
            GROUP BY p.id
            ORDER BY p.nombre
        """, params or None)
        cols       = [d[0] for d in cur.description]
        proveedores = [dict(zip(cols, r)) for r in cur.fetchall()]

    ctx = {
        "user": user,
        "proveedores": proveedores,
        "buscar": buscar,
        "seccion": "proveedores",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="catalogos/_proveedores_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="catalogos/proveedores.html", context=ctx
    )


@router.get("/proveedores/{prov_id}", response_class=HTMLResponse)
async def detalle_proveedor(request: Request, prov_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM proveedores WHERE id = %s", (prov_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Proveedor no encontrado")
        proveedor = dict(zip([d[0] for d in cur.description], row))

        cur.execute("""
            SELECT p.id, p.codigo, p.nombre, p.precio_base, p.unidad_medida,
                   cat.nombre AS categoria
            FROM producto_proveedor pp
            JOIN productos    p   ON p.id   = pp.producto_id
            LEFT JOIN categorias cat ON cat.id = p.categoria_id
            WHERE pp.proveedor_id = %s
            ORDER BY cat.nombre, p.nombre
        """, (prov_id,))
        pcols     = [d[0] for d in cur.description]
        productos = [_floats(dict(zip(pcols, r))) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="catalogos/proveedor_detalle.html",
        context={
            "user": user, "proveedor": proveedor,
            "productos": productos, "seccion": "proveedores",
        },
    )
