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

router = APIRouter(prefix="/stock")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

MOTIVOS_SALIDA = [
    "Merma / Daño",
    "Uso interno",
    "Devolución a proveedor",
    "Ajuste de inventario",
    "Muestra / Demo",
    "Pérdida",
    "Otro",
]


def _floats(d: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


def _calcular_abc(productos: list) -> None:
    """Asigna campo 'abc' y 'valor_inv' a cada producto in-place."""
    con_valor = [
        (p, (p["stock_actual"] or 0) * (p["costo_prom"] or p["precio_base"] or 0))
        for p in productos
    ]
    total = sum(v for _, v in con_valor)
    if total == 0:
        for p, _ in con_valor:
            p["abc"] = "C"
            p["valor_inv"] = 0.0
        return

    con_valor.sort(key=lambda x: x[1], reverse=True)
    acum = 0.0
    for p, valor in con_valor:
        acum += valor
        pct = acum / total * 100
        p["valor_inv"] = round(valor, 2)
        p["abc"] = "A" if pct <= 80 else ("B" if pct <= 95 else "C")


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
