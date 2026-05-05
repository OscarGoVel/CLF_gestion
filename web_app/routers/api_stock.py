# -*- coding: utf-8 -*-
"""
web_app/routers/api_stock.py
/api/stock — inventario y movimientos para el SPA React.
"""

from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/stock", tags=["api"])


def _serial(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v

def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


@router.get("")
async def inventario(
    q: str = Query(""),
    categoria: str = Query(""),
    bajo_minimo: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    clauses, params = [], []
    if q:
        clauses.append("(p.nombre ILIKE %s OR p.codigo ILIKE %s)")
        params += [f"%{q}%"] * 2
    if categoria:
        clauses.append("cat.nombre = %s"); params.append(categoria)
    if bajo_minimo == "1":
        clauses.append("p.stock_actual < p.stock_minimo AND p.stock_minimo > 0")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   p.stock_actual, p.stock_minimo, p.precio_base,
                   cat.nombre  AS categoria,
                   sub.nombre  AS subcategoria,
                   COALESCE(AVG(cd.costo_unitario), p.precio_base, 0) AS costo_prom,
                   prov.nombre AS proveedor_principal
            FROM productos p
            LEFT JOIN categorias    cat  ON cat.id  = p.categoria_id
            LEFT JOIN subcategorias sub  ON sub.id  = p.subcategoria_id
            LEFT JOIN compra_detalle cd  ON cd.producto_id = p.id
            LEFT JOIN producto_proveedor pp ON pp.producto_id = p.id AND pp.es_principal = 1
            LEFT JOIN proveedores   prov ON prov.id = pp.proveedor_id
            {where}
            GROUP BY p.id, cat.nombre, sub.nombre, prov.nombre
            ORDER BY cat.nombre NULLS LAST, p.nombre
        """, params or None)
        productos = _rows(cur)

        cur.execute("SELECT nombre FROM categorias ORDER BY nombre")
        categorias = [r[0] for r in cur.fetchall()]

    total_valor   = sum((p["stock_actual"] or 0) * (p["costo_prom"] or p["precio_base"] or 0) for p in productos)
    bajo_min_cnt  = sum(1 for p in productos if (p["stock_minimo"] or 0) > 0 and (p["stock_actual"] or 0) < (p["stock_minimo"] or 0))
    negativo_cnt  = sum(1 for p in productos if (p["stock_actual"] or 0) < 0)
    sin_stock_cnt = sum(1 for p in productos if (p["stock_actual"] or 0) == 0)

    return JSONResponse({
        "productos": productos,
        "categorias": categorias,
        "stats": {
            "total_valor": round(total_valor, 2),
            "bajo_minimo": bajo_min_cnt,
            "negativo": negativo_cnt,
            "sin_stock": sin_stock_cnt,
            "total_productos": len(productos),
        },
    })


@router.get("/movimientos")
async def movimientos(
    producto_id: int = Query(0),
    tipo: str = Query(""),
    pagina: int = Query(1, ge=1),
    user: dict = Depends(get_usuario_api),
):
    POR_PAGINA = 50
    offset = (pagina - 1) * POR_PAGINA
    clauses, params = [], []
    if producto_id:
        clauses.append("m.producto_id = %s"); params.append(producto_id)
    if tipo:
        clauses.append("m.tipo = %s"); params.append(tipo)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT m.id, p.codigo, p.nombre, m.tipo, m.motivo,
                   m.cantidad, m.stock_antes, m.stock_despues,
                   m.referencia, m.notas, m.fecha
            FROM movimientos_stock m
            JOIN productos p ON p.id = m.producto_id
            {where}
            ORDER BY m.id DESC
            LIMIT {POR_PAGINA} OFFSET {offset}
        """, params or None)
        movimientos = _rows(cur)

        cur.execute(f"""
            SELECT COUNT(*) FROM movimientos_stock m
            JOIN productos p ON p.id = m.producto_id
            {where}
        """, params or None)
        total = cur.fetchone()[0]

    return JSONResponse({
        "movimientos": movimientos,
        "total": total,
        "pagina": pagina,
        "total_pags": max(1, (total + POR_PAGINA - 1) // POR_PAGINA),
    })
