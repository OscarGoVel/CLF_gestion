# -*- coding: utf-8 -*-
"""
web_app/routers/api_catalogos.py
/api/catalogos — clientes, productos, proveedores para el SPA React.
"""

from decimal import Decimal
from typing import List
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
    tipo: List[str] = Query([]),
    user: dict = Depends(get_usuario_api),
):
    clauses = ["(c.activo IS NULL OR c.activo = TRUE)"]
    params: list = []
    if tipo:
        placeholders = ",".join(["%s"] * len(tipo))
        clauses.append(f"c.tipo IN ({placeholders})")
        params.extend(tipo)
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


@router.patch("/clientes/{cliente_id}")
async def editar_cliente(cliente_id: int, request: Request, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    body = await request.json()
    fields = ["nombre_comercial", "razon_social", "tipo", "rfc",
              "contacto", "telefono", "email", "direccion"]
    data = {f: (body.get(f) or "").strip() or None for f in fields if f in body}
    if "nombre_comercial" in data and not data["nombre_comercial"]:
        raise HTTPException(status_code=422, detail="nombre_comercial requerido")
    if not data:
        raise HTTPException(status_code=422, detail="Sin campos para actualizar")
    sets = ", ".join(f"{k} = %s" for k in data)
    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute(f"UPDATE clientes SET {sets} WHERE id = %s", [*data.values(), cliente_id])
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        conn.commit()
    return JSONResponse({"ok": True})


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
    categoria: List[str] = Query([]),
    bajo_minimo: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    clauses, params = [], []
    if q:
        clauses.append("(p.nombre ILIKE %s OR p.codigo ILIKE %s)")
        params += [f"%{q}%"] * 2
    if categoria:
        placeholders = ",".join(["%s"] * len(categoria))
        clauses.append(f"cat.nombre IN ({placeholders})")
        params.extend(categoria)
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


@router.get("/categorias")
async def listar_categorias(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        categorias = [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT id, nombre, categoria_id FROM subcategorias ORDER BY nombre")
        subcategorias = [{"id": r[0], "nombre": r[1], "categoria_id": r[2]} for r in cur.fetchall()]
    return JSONResponse({"categorias": categorias, "subcategorias": subcategorias})


@router.get("/generar-sku")
async def generar_sku(
    categoria_id: int = 0,
    subcategoria_id: int = 0,
    user: dict = Depends(get_usuario_api),
):
    if not categoria_id:
        return JSONResponse({"sku": ""})
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT nombre FROM categorias WHERE id = %s", (categoria_id,))
        row = cur.fetchone()
        if not row:
            return JSONResponse({"sku": ""})
        prefix = row[0][:3].upper()
        if subcategoria_id:
            cur.execute("SELECT nombre FROM subcategorias WHERE id = %s", (subcategoria_id,))
            sub_row = cur.fetchone()
            prefix += sub_row[0][:3].upper() if sub_row else "GEN"
        else:
            prefix += "GEN"
        cur.execute(
            "SELECT codigo FROM productos WHERE codigo LIKE %s ORDER BY codigo DESC LIMIT 1",
            (f"{prefix}%",)
        )
        ultimo = cur.fetchone()
        try:
            num = int(ultimo[0][len(prefix):]) + 1 if ultimo else 1
        except Exception:
            num = 1
    return JSONResponse({"sku": f"{prefix}{num:04d}"})


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


@router.patch("/proveedores/{proveedor_id}")
async def editar_proveedor(proveedor_id: int, request: Request, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    body = await request.json()
    fields = ["nombre", "razon_social", "rfc", "contacto", "telefono", "email", "notas"]
    data = {f: (body.get(f) or "").strip() or None for f in fields if f in body}
    if "nombre" in data and not data["nombre"]:
        raise HTTPException(status_code=422, detail="nombre requerido")
    if not data:
        raise HTTPException(status_code=422, detail="Sin campos para actualizar")
    sets = ", ".join(f"{k} = %s" for k in data)
    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute(f"UPDATE proveedores SET {sets} WHERE id = %s", [*data.values(), proveedor_id])
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        conn.commit()
    return JSONResponse({"ok": True})


@router.post("/proveedores", status_code=201)
async def crear_proveedor(request: Request, user: dict = Depends(get_usuario_api)):
    body = await request.json()
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="nombre requerido")

    fields = ["nombre", "razon_social", "rfc", "contacto", "telefono", "email", "notas"]
    data = {f: (body.get(f) or "").strip() or None for f in fields}
    data["nombre"] = nombre

    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))

    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute(
            f"INSERT INTO proveedores ({cols}) VALUES ({placeholders}) RETURNING id",
            list(data.values()),
        )
        new_id = cur.fetchone()[0]
        conn.commit()

    return JSONResponse({"id": new_id}, status_code=201)


@router.patch("/productos/{producto_id}")
async def editar_producto(producto_id: int, request: Request, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    body = await request.json()
    allowed = {"nombre", "codigo", "unidad_medida", "precio_base", "precio_venta", "stock_minimo", "aplica_iva"}
    data = {k: v for k, v in body.items() if k in allowed}
    for str_field in ("nombre", "codigo", "unidad_medida"):
        if str_field in data:
            data[str_field] = (data[str_field] or "").strip() or None
    if "nombre" in data and not data["nombre"]:
        raise HTTPException(status_code=422, detail="nombre requerido")
    if not data:
        raise HTTPException(status_code=422, detail="Sin campos para actualizar")
    sets = ", ".join(f"{k} = %s" for k in data)
    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute(f"UPDATE productos SET {sets} WHERE id = %s", [*data.values(), producto_id])
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        # Actualizar fecha cuando se toca el costo base de catálogo
        if "precio_base" in data:
            cur.execute(
                "UPDATE productos SET precio_base_fecha = CURRENT_DATE::TEXT WHERE id = %s",
                (producto_id,),
            )
        # Resetear alerta de precio desactualizado cuando el operador actualiza precio_venta
        if "precio_venta" in data:
            cur.execute(
                "UPDATE productos SET precio_desactualizado = FALSE, precio_venta_fecha = NOW() WHERE id = %s",
                (producto_id,),
            )
        conn.commit()
    return JSONResponse({"ok": True})


@router.post("/productos/rapido", status_code=201)
async def crear_producto_rapido(request: Request, user: dict = Depends(get_usuario_api)):
    body = await request.json()
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="nombre requerido")

    codigo = (body.get("codigo") or "").strip() or None
    categoria_id = body.get("categoria_id") or None
    subcategoria_id = body.get("subcategoria_id") or None
    try:
        precio_base = float(body.get("precio_base") or 0)
    except (TypeError, ValueError):
        precio_base = 0.0
    aplica_iva = 1 if body.get("aplica_iva", True) else 0

    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        if not codigo:
            if categoria_id:
                cur.execute("SELECT nombre FROM categorias WHERE id = %s", (categoria_id,))
                row = cur.fetchone()
                prefix = row[0][:3].upper() if row else "GEN"
                if subcategoria_id:
                    cur.execute("SELECT nombre FROM subcategorias WHERE id = %s", (subcategoria_id,))
                    sub_row = cur.fetchone()
                    prefix += sub_row[0][:3].upper() if sub_row else "GEN"
                else:
                    prefix += "GEN"
            else:
                prefix = "GENGEN"
            cur.execute(
                "SELECT codigo FROM productos WHERE codigo LIKE %s ORDER BY codigo DESC LIMIT 1",
                (f"{prefix}%",)
            )
            ultimo = cur.fetchone()
            try:
                num = int(ultimo[0][len(prefix):]) + 1 if ultimo else 1
            except Exception:
                num = 1
            codigo = f"{prefix}{num:04d}"

        cur.execute(
            """INSERT INTO productos (nombre, codigo, precio_base, stock_actual, aplica_iva,
                                      precio_base_fecha, categoria_id, subcategoria_id)
               VALUES (%s, %s, %s, 0, %s, CURRENT_DATE::TEXT, %s, %s)
               RETURNING id""",
            (nombre, codigo, precio_base, aplica_iva, categoria_id, subcategoria_id),
        )
        new_id = cur.fetchone()[0]
        conn.commit()

    return JSONResponse({
        "id": new_id, "nombre": nombre, "codigo": codigo,
        "precio": precio_base, "aplica_iva": bool(aplica_iva),
        "costo_promedio": precio_base,
        "precio_desactualizado": False,
        "tiene_historial_compras": False,
        "dias_sin_actualizar": None,
    }, status_code=201)


@router.post("/productos", status_code=201)
async def crear_producto(request: Request, user: dict = Depends(get_usuario_api)):
    body = await request.json()
    nombre = (body.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="nombre requerido")

    codigo = (body.get("codigo") or "").strip()
    if not codigo:
        raise HTTPException(status_code=422, detail="codigo requerido")

    descripcion = (body.get("descripcion") or "").strip() or None
    categoria_id = body.get("categoria_id")
    subcategoria_id = body.get("subcategoria_id")
    unidad_medida = (body.get("unidad_medida") or "").strip() or None
    clave_sat = (body.get("clave_sat") or "").strip() or None
    clave_unidad_sat = (body.get("clave_unidad_sat") or "").strip() or None
    aplica_iva = 1 if body.get("aplica_iva") else 0

    try:
        precio_base = float(body.get("precio_base", 0) or 0)
        if precio_base < 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="precio_base debe ser número >= 0")

    try:
        stock_minimo = float(body.get("stock_minimo", 0) or 0)
        if stock_minimo < 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="stock_minimo debe ser número >= 0")

    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        cur.execute("SELECT id FROM productos WHERE codigo = %s LIMIT 1", (codigo,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="codigo ya existe")

        if subcategoria_id and categoria_id:
            cur.execute(
                "SELECT id FROM subcategorias WHERE id = %s AND categoria_id = %s",
                (subcategoria_id, categoria_id)
            )
            if not cur.fetchone():
                raise HTTPException(status_code=422, detail="subcategoria no pertenece a categoria")

        cur.execute("""
            INSERT INTO productos
            (nombre, codigo, descripcion, categoria_id, subcategoria_id,
             unidad_medida, precio_base, aplica_iva, stock_minimo,
             clave_sat, clave_unidad_sat, stock_actual)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            RETURNING id, nombre, codigo, descripcion, categoria_id, subcategoria_id,
                      unidad_medida, precio_base, aplica_iva, stock_minimo,
                      clave_sat, clave_unidad_sat, stock_actual
        """, (
            nombre, codigo, descripcion, categoria_id, subcategoria_id,
            unidad_medida, precio_base, aplica_iva, stock_minimo,
            clave_sat, clave_unidad_sat
        ))
        row = cur.fetchone()
        new_id = row[0]
        cols = [d[0] for d in cur.description]
        producto = {k: _serial(v) for k, v in zip(cols, row)}
        conn.commit()

    return JSONResponse(producto, status_code=201)
