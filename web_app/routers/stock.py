# -*- coding: utf-8 -*-
"""
web_app/routers/stock.py
Módulo de Stock: vista de inventario, movimientos, entradas y salidas.
"""

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual
from core.constants import MOTIVOS_SALIDA
from core.stock import clasificar_abc

router = APIRouter(prefix="/stock")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _floats(d: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


def _calcular_abc(productos: list) -> None:
    """Asigna campo 'abc' y 'valor_inv' a cada producto in-place usando core.stock."""
    datos = [
        (i, (p["stock_actual"] or 0) * (p["costo_prom"] or p["precio_base"] or 0))
        for i, p in enumerate(productos)
    ]
    resultado = clasificar_abc(datos)
    for i, p in enumerate(productos):
        info = resultado.get(i, {"categoria": "C", "valor": 0.0})
        p["abc"]      = info["categoria"]
        p["valor_inv"] = info["valor"]


# ─────────────────────────────────────────────────────────────────────────────
# VISTA PRINCIPAL — inventario
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def vista_stock(
    request: Request,
    buscar: str = "",
    categoria: str = "",
    bajo_minimo: str = "",
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    where, params = [], []
    if buscar:
        where.append("(p.nombre ILIKE %s OR p.codigo ILIKE %s)")
        params += [f"%{buscar}%"] * 2
    if categoria:
        where.append("cat.nombre = %s"); params.append(categoria)
    if bajo_minimo == "1":
        where.append("p.stock_actual < p.stock_minimo AND p.stock_minimo > 0")

    w = ("WHERE " + " AND ".join(where)) if where else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   p.stock_actual, p.stock_minimo, p.precio_base,
                   cat.nombre AS categoria, sub.nombre AS subcategoria,
                   COALESCE(AVG(cd.costo_unitario), p.precio_base, 0) AS costo_prom
            FROM productos p
            LEFT JOIN categorias     cat ON cat.id = p.categoria_id
            LEFT JOIN subcategorias  sub ON sub.id = p.subcategoria_id
            LEFT JOIN compra_detalle cd  ON cd.producto_id = p.id
            {w}
            GROUP BY p.id, cat.nombre, sub.nombre
            ORDER BY cat.nombre NULLS LAST, p.nombre
        """, params or None)
        cols      = [d[0] for d in cur.description]
        productos = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

        cur.execute("SELECT nombre FROM categorias ORDER BY nombre")
        categorias = [r[0] for r in cur.fetchall()]

    _calcular_abc(productos)

    # Stats resumen
    total_valor   = sum(p["valor_inv"] for p in productos)
    bajo_min_cnt  = sum(1 for p in productos
                        if (p["stock_minimo"] or 0) > 0
                        and (p["stock_actual"] or 0) < (p["stock_minimo"] or 0))
    sin_stock_cnt = sum(1 for p in productos if not (p["stock_actual"] or 0))
    abc_counts    = {"A": 0, "B": 0, "C": 0}
    abc_valores   = {"A": 0.0, "B": 0.0, "C": 0.0}
    for p in productos:
        abc_counts[p["abc"]] += 1
        abc_valores[p["abc"]] += p["valor_inv"]

    ctx = {
        "user": user,
        "productos": productos,
        "categorias": categorias,
        "buscar": buscar,
        "categoria_sel": categoria,
        "bajo_minimo": bajo_minimo,
        "total_valor": total_valor,
        "bajo_min_cnt": bajo_min_cnt,
        "sin_stock_cnt": sin_stock_cnt,
        "abc_counts": abc_counts,
        "abc_valores": abc_valores,
        "motivos_salida": MOTIVOS_SALIDA,
        "seccion": "stock",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="stock/_stock_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="stock/index.html", context=ctx
    )


# ─────────────────────────────────────────────────────────────────────────────
# HISTORIAL DE MOVIMIENTOS
# ─────────────────────────────────────────────────────────────────────────────

_POR_PAGINA_MOV = 50


@router.get("/movimientos", response_class=HTMLResponse)
async def historial_movimientos(
    request: Request,
    buscar: str = "",
    tipo: str = "",
    pagina: int = 1,
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    pagina = max(1, pagina)
    where, params = [], []
    if buscar:
        where.append("(p.nombre ILIKE %s OR p.codigo ILIKE %s OR m.referencia ILIKE %s)")
        params += [f"%{buscar}%"] * 3
    if tipo:
        where.append("m.tipo = %s"); params.append(tipo)

    w = ("WHERE " + " AND ".join(where)) if where else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT COUNT(*) FROM movimientos_stock m
            JOIN productos p ON p.id = m.producto_id {w}
        """, params or None)
        total_movimientos = cur.fetchone()[0]

        offset = (pagina - 1) * _POR_PAGINA_MOV
        cur.execute(f"""
            SELECT m.id, m.tipo, m.motivo, m.cantidad,
                   m.stock_antes, m.stock_despues,
                   m.referencia, m.notas, m.usuario, m.fecha,
                   p.id AS producto_id, p.nombre AS producto_nombre,
                   p.codigo AS producto_codigo, p.unidad_medida
            FROM movimientos_stock m
            JOIN productos p ON p.id = m.producto_id
            {w}
            ORDER BY m.fecha DESC, m.id DESC
            LIMIT %s OFFSET %s
        """, (params or []) + [_POR_PAGINA_MOV, offset])
        cols = [d[0] for d in cur.description]
        movimientos = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

    import math
    total_paginas = max(1, math.ceil(total_movimientos / _POR_PAGINA_MOV))
    pagina = min(pagina, total_paginas)

    ctx = {
        "user": user,
        "movimientos": movimientos,
        "buscar": buscar,
        "tipo_sel": tipo,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "total_movimientos": total_movimientos,
        "seccion": "stock",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="stock/_movimientos_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="stock/movimientos.html", context=ctx
    )


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRAR ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/entrada", response_class=HTMLResponse)
async def registrar_entrada(
    request: Request,
    producto_id: int = Form(...),
    cantidad: float = Form(...),
    motivo: str = Form("Compra"),
    referencia: str = Form(""),
    notas: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador",):
        return templates.TemplateResponse(
            request=request,
            name="stock/_mov_result.html",
            context={"error": "Solo el Administrador puede registrar entradas manuales.", "user": user},
        )

    if cantidad <= 0:
        return templates.TemplateResponse(
            request=request,
            name="stock/_mov_result.html",
            context={"error": "La cantidad debe ser mayor a cero.", "user": user},
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id, nombre, stock_actual FROM productos WHERE id = %s", (producto_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
        pid, nombre, stock_antes = row[0], row[1], float(row[2] or 0)

        stock_despues = stock_antes + cantidad
        cur.execute(
            "UPDATE productos SET stock_actual = %s WHERE id = %s",
            (stock_despues, pid),
        )
        cur.execute("""
            INSERT INTO movimientos_stock
                (producto_id, tipo, motivo, cantidad,
                 stock_antes, stock_despues, referencia, notas, usuario)
            VALUES (%s,'entrada',%s,%s,%s,%s,%s,%s,%s)
        """, (pid, motivo or "Entrada manual", cantidad,
              stock_antes, stock_despues,
              referencia or None, notas or None,
              user["nombre"]))

    return templates.TemplateResponse(
        request=request,
        name="stock/_mov_result.html",
        context={
            "ok": True,
            "tipo": "entrada",
            "producto": nombre,
            "cantidad": cantidad,
            "stock_despues": stock_despues,
            "user": user,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRAR SALIDA
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/salida", response_class=HTMLResponse)
async def registrar_salida(
    request: Request,
    producto_id: int = Form(...),
    cantidad: float = Form(...),
    motivo: str = Form(...),
    referencia: str = Form(""),
    notas: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador",):
        return templates.TemplateResponse(
            request=request,
            name="stock/_mov_result.html",
            context={"error": "Solo el Administrador puede registrar salidas manuales.", "user": user},
        )

    if cantidad <= 0:
        return templates.TemplateResponse(
            request=request,
            name="stock/_mov_result.html",
            context={"error": "La cantidad debe ser mayor a cero.", "user": user},
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id, nombre, stock_actual FROM productos WHERE id = %s", (producto_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
        pid, nombre, stock_antes = row[0], row[1], float(row[2] or 0)

        stock_despues = stock_antes - cantidad
        cur.execute(
            "UPDATE productos SET stock_actual = %s WHERE id = %s",
            (stock_despues, pid),
        )
        cur.execute("""
            INSERT INTO movimientos_stock
                (producto_id, tipo, motivo, cantidad,
                 stock_antes, stock_despues, referencia, notas, usuario)
            VALUES (%s,'salida',%s,%s,%s,%s,%s,%s,%s)
        """, (pid, motivo, cantidad,
              stock_antes, stock_despues,
              referencia or None, notas or None,
              user["nombre"]))

    return templates.TemplateResponse(
        request=request,
        name="stock/_mov_result.html",
        context={
            "ok": True,
            "tipo": "salida",
            "producto": nombre,
            "cantidad": cantidad,
            "stock_despues": stock_despues,
            "user": user,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# BUSCAR PRODUCTO (para autocomplete en modales)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/buscar-producto", response_class=HTMLResponse)
async def buscar_producto(request: Request, q: str = ""):
    user = get_usuario_actual(request)
    if not user:
        return HTMLResponse("")

    if len(q) < 2:
        return HTMLResponse("")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, codigo, nombre, stock_actual, unidad_medida
            FROM productos
            WHERE nombre ILIKE %s OR codigo ILIKE %s
            ORDER BY nombre LIMIT 8
        """, (f"%{q}%", f"%{q}%"))
        cols = [d[0] for d in cur.description]
        resultados = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="stock/_producto_sugerencias.html",
        context={"resultados": resultados, "user": user},
    )


# ─────────────────────────────────────────────────────────────────────────────
# UBICACIONES — asignación producto → área
# ─────────────────────────────────────────────────────────────────────────────

def _asegurar_stock_ubicaciones(empresa_db: str) -> None:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sucursales (
                id SERIAL PRIMARY KEY, nombre TEXT NOT NULL, descripcion TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS areas (
                id SERIAL PRIMARY KEY,
                sucursal_id INTEGER NOT NULL REFERENCES sucursales(id) ON DELETE CASCADE,
                nombre TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_ubicaciones (
                producto_id INTEGER PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
                area_id     INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE
            )
        """)


@router.get("/ubicaciones", response_class=HTMLResponse)
async def vista_ubicaciones(request: Request, buscar: str = "", area_id: str = ""):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    _asegurar_stock_ubicaciones(user["empresa_db"])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Sucursales con áreas para el selector
        cur.execute("""
            SELECT a.id, a.nombre, s.nombre AS sucursal_nombre
            FROM areas a JOIN sucursales s ON s.id = a.sucursal_id
            ORDER BY s.nombre, a.nombre
        """)
        areas_raw = cur.fetchall()
        sucursales_map: dict = {}
        for aid, anom, snom in areas_raw:
            sucursales_map.setdefault(snom, []).append({"id": aid, "nombre": anom})
        sucursales = [{"nombre": k, "areas": v} for k, v in sucursales_map.items()]

        # Productos con su ubicación actual
        where, params = [], []
        if buscar:
            where.append("(p.nombre ILIKE %s OR p.codigo ILIKE %s)")
            params += [f"%{buscar}%"] * 2
        if area_id and area_id.isdigit():
            where.append("su.area_id = %s")
            params.append(int(area_id))
        elif area_id == "sin":
            where.append("su.area_id IS NULL")
        w = ("WHERE " + " AND ".join(where)) if where else ""

        cur.execute(f"""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   su.area_id,
                   a.nombre AS area_nombre,
                   s.nombre AS sucursal_nombre
            FROM productos p
            LEFT JOIN stock_ubicaciones su ON su.producto_id = p.id
            LEFT JOIN areas a ON a.id = su.area_id
            LEFT JOIN sucursales s ON s.id = a.sucursal_id
            {w}
            ORDER BY p.nombre
        """, params or None)
        cols = [d[0] for d in cur.description]
        productos = [dict(zip(cols, r)) for r in cur.fetchall()]

    ctx = {
        "user": user,
        "productos": productos,
        "sucursales": sucursales,
        "buscar": buscar,
        "area_sel": area_id,
        "subseccion": "ubicaciones",
        "seccion": "stock",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="stock/_ubicaciones_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="stock/ubicaciones.html", context=ctx
    )


@router.post("/producto/{producto_id}/ubicar", response_class=HTMLResponse)
async def ubicar_producto(
    request: Request,
    producto_id: int,
    area_id: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        return HTMLResponse("", status_code=401)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        if area_id and area_id.isdigit():
            cur.execute("""
                INSERT INTO stock_ubicaciones (producto_id, area_id) VALUES (%s, %s)
                ON CONFLICT (producto_id) DO UPDATE SET area_id = EXCLUDED.area_id
            """, (producto_id, int(area_id)))
            cur.execute("""
                SELECT a.nombre, s.nombre FROM areas a
                JOIN sucursales s ON s.id = a.sucursal_id
                WHERE a.id = %s
            """, (int(area_id),))
            row = cur.fetchone()
            area_txt = f"{row[1]} › {row[0]}" if row else "—"
        else:
            cur.execute(
                "DELETE FROM stock_ubicaciones WHERE producto_id = %s", (producto_id,)
            )
            area_txt = None

    if area_txt:
        return HTMLResponse(
            f'<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 '
            f'cursor-pointer hover:bg-blue-200" '
            f'onclick="abrirUbicar({producto_id})" title="Cambiar área">'
            f'📍 {area_txt}</span>'
        )
    return HTMLResponse(
        f'<span class="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-400 '
        f'cursor-pointer hover:bg-gray-200" '
        f'onclick="abrirUbicar({producto_id})" title="Asignar área">'
        f'Sin área</span>'
    )
