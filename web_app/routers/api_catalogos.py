# -*- coding: utf-8 -*-
"""
web_app/routers/api_catalogos.py
/api/catalogos — clientes, productos, proveedores para el SPA React.
"""

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/catalogos", tags=["api"])


def _serial(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v

def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


# ── Clientes ──────────────────────────────────────────────────────────────────

@router.get("/clientes")
async def listar_clientes(
    q: str = Query(""),
    tipo: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    clauses = ["(c.activo IS NULL OR c.activo = TRUE)"]
    params: list = []
    if tipo:
        clauses.append("c.tipo = %s"); params.append(tipo)
    if q:
        clauses.append("(c.nombre_comercial ILIKE %s OR c.rfc ILIKE %s OR c.contacto ILIKE %s)")
        params += [f"%{q}%"] * 3
    where = "WHERE " + " AND ".join(clauses)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT c.id, c.nombre_comercial, c.razon_social, c.tipo,
                   c.rfc, c.contacto, c.telefono, c.email, c.direccion,
                   COUNT(cot.id)      AS num_cotizaciones,
                   MAX(cot.fecha)     AS ultima_cotizacion,
                   COALESCE(SUM(cot.total) FILTER (
                       WHERE cot.estado IN (
                           'Programada','Parcialmente Entregada',
                           'Entregada','Facturada','Pagada'
                       )
                   ), 0)              AS monto_total
            FROM clientes c
            LEFT JOIN cotizaciones cot ON cot.cliente_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.nombre_comercial
        """, params or None)
        clientes = _rows(cur)

        cur.execute("SELECT DISTINCT tipo FROM clientes WHERE tipo IS NOT NULL ORDER BY tipo")
        tipos = [r[0] for r in cur.fetchall()]

    return JSONResponse({"clientes": clientes, "tipos": tipos})


@router.post("/clientes", status_code=201)
async def crear_cliente(request: Request, user: dict = Depends(get_usuario_api)):
    body = await request.json()
    nombre = (body.get("nombre_comercial") or "").strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="nombre_comercial requerido")

    fields = ["nombre_comercial", "razon_social", "tipo", "rfc",
              "contacto", "telefono", "email", "direccion"]
    data = {f: (body.get(f) or "").strip() or None for f in fields}
    data["nombre_comercial"] = nombre

    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))

    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute(
            f"INSERT INTO clientes ({cols}) VALUES ({placeholders}) RETURNING id",
            list(data.values()),
        )
        new_id = cur.fetchone()[0]
        conn.commit()

    return JSONResponse({"id": new_id}, status_code=201)


@router.get("/clientes/{cliente_id}")
async def detalle_cliente(cliente_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
        row = cur.fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        cols = [d[0] for d in cur.description]
        cliente = {k: _serial(v) for k, v in zip(cols, row)}

        cur.execute("""
            SELECT c.id, c.folio, c.fecha, c.estado, c.total, c.orden_compra
            FROM cotizaciones c
            WHERE c.cliente_id = %s
            ORDER BY c.fecha DESC
            LIMIT 50
        """, (cliente_id,))
        cotizaciones = _rows(cur)

    return JSONResponse({"cliente": cliente, "cotizaciones": cotizaciones})


# ── Productos ─────────────────────────────────────────────────────────────────

@router.get("/productos")
async def listar_productos(
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
                   p.aplica_iva,
                   cat.nombre  AS categoria,
                   sub.nombre  AS subcategoria,
                   COALESCE(AVG(cd.costo_unitario), p.precio_base, 0) AS costo_prom,
                   prov.nombre AS proveedor_principal
            FROM productos p
            LEFT JOIN categorias     cat  ON cat.id  = p.categoria_id
            LEFT JOIN subcategorias  sub  ON sub.id  = p.subcategoria_id
            LEFT JOIN compra_detalle cd   ON cd.producto_id  = p.id
            LEFT JOIN producto_proveedor pp ON pp.producto_id = p.id AND pp.es_principal = 1
            LEFT JOIN proveedores    prov ON prov.id = pp.proveedor_id
            {where}
            GROUP BY p.id, cat.nombre, sub.nombre, prov.nombre
            ORDER BY cat.nombre NULLS LAST, p.nombre
        """, params or None)
        productos = _rows(cur)

        cur.execute("SELECT nombre FROM categorias ORDER BY nombre")
        categorias = [r[0] for r in cur.fetchall()]

    # stats
    total_valor   = sum((p["stock_actual"] or 0) * (p["costo_prom"] or p["precio_base"] or 0) for p in productos)
    bajo_min_cnt  = sum(1 for p in productos if (p["stock_minimo"] or 0) > 0 and (p["stock_actual"] or 0) < (p["stock_minimo"] or 0))
    sin_stock_cnt = sum(1 for p in productos if (p["stock_actual"] or 0) == 0)

    return JSONResponse({
        "productos": productos,
        "categorias": categorias,
        "stats": {
            "total": len(productos),
            "total_valor": round(total_valor, 2),
            "bajo_minimo": bajo_min_cnt,
            "sin_stock": sin_stock_cnt,
        },
    })


# ── Proveedores ───────────────────────────────────────────────────────────────

@router.get("/proveedores")
async def listar_proveedores(
    q: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    clauses, params = [], []
    if q:
        clauses.append("(p.nombre ILIKE %s OR p.rfc ILIKE %s)")
        params += [f"%{q}%"] * 2
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT p.id, p.nombre, p.rfc, p.contacto, p.telefono, p.email,
                   COUNT(DISTINCT c.id)              AS num_compras,
                   COALESCE(SUM(c.total), 0)         AS monto_total,
                   MAX(c.fecha_compra)               AS ultima_compra
            FROM proveedores p
            LEFT JOIN compras c ON c.proveedor_id = p.id
            {where}
            GROUP BY p.id
            ORDER BY p.nombre
        """, params or None)
        proveedores = _rows(cur)

    return JSONResponse({"proveedores": proveedores})
