# -*- coding: utf-8 -*-
"""
web_app/routers/api_stock.py
/api/stock — inventario y movimientos para el SPA React.
"""

from datetime import date as _date
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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


# ── GET /api/stock/lotes/alertas ─────────────────────────────────────────────

@router.get("/lotes/alertas")
async def lotes_alertas(user: dict = Depends(get_usuario_api)):
    hoy = _date.today()
    prox = hoy.replace(day=min(hoy.day + 30, 28)) if hoy.day <= 28 else \
        _date(hoy.year + (hoy.month // 12), (hoy.month % 12) + 1, hoy.day - 28)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT l.id, p.nombre AS producto, p.codigo, l.numero_lote,
                   l.fecha_vencimiento, l.cantidad,
                   CASE
                       WHEN l.fecha_vencimiento < %s THEN 'vencido'
                       WHEN l.fecha_vencimiento <= %s THEN 'proximo'
                       ELSE 'ok'
                   END AS alerta
            FROM lotes l
            JOIN productos p ON p.id = l.producto_id
            WHERE l.cantidad > 0
              AND l.fecha_vencimiento IS NOT NULL
              AND l.fecha_vencimiento <= %s
            ORDER BY l.fecha_vencimiento ASC
        """, (hoy, prox, prox))
        alertas = _rows(cur)
    return JSONResponse({"alertas": alertas})


# ── GET /api/stock/{producto_id}/lotes ───────────────────────────────────────

@router.get("/{producto_id}/lotes")
async def listar_lotes(producto_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id FROM productos WHERE id = %s", (producto_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        cur.execute("""
            SELECT id, numero_lote, fecha_vencimiento, cantidad, fecha_entrada, notas, created_at
            FROM lotes WHERE producto_id = %s
            ORDER BY fecha_vencimiento ASC NULLS LAST, id DESC
        """, (producto_id,))
        lotes = _rows(cur)
    hoy = _date.today()
    prox = hoy.replace(day=min(hoy.day + 30, 28)) if hoy.day <= 28 else \
        _date(hoy.year + (hoy.month // 12), (hoy.month % 12) + 1, hoy.day - 28)
    for lt in lotes:
        fv = lt.get("fecha_vencimiento")
        if fv is None:
            lt["alerta"] = "ok"
        else:
            fv_d = _date.fromisoformat(str(fv)[:10])
            lt["alerta"] = "vencido" if fv_d < hoy else ("proximo" if fv_d <= prox else "ok")
    return JSONResponse({"lotes": lotes})


# ── POST /api/stock/{producto_id}/lotes ──────────────────────────────────────

class LoteIn(BaseModel):
    numero_lote: str
    fecha_vencimiento: Optional[str] = None
    cantidad: float
    fecha_entrada: Optional[str] = None
    notas: Optional[str] = None


@router.post("/{producto_id}/lotes", status_code=201)
async def crear_lote(producto_id: int, body: LoteIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if body.cantidad <= 0:
        raise HTTPException(status_code=422, detail="Cantidad debe ser mayor a 0")
    if not body.numero_lote.strip():
        raise HTTPException(status_code=422, detail="Número de lote requerido")
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id FROM productos WHERE id = %s", (producto_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        cur.execute("""
            INSERT INTO lotes (producto_id, numero_lote, fecha_vencimiento, cantidad, fecha_entrada, notas)
            VALUES (%s, %s, %s::date, %s, %s::date, %s)
        """, (producto_id, body.numero_lote.strip(),
              body.fecha_vencimiento or None, body.cantidad,
              body.fecha_entrada or None, body.notas or None))
        new_id = cur.lastrowid
    return JSONResponse({"id": new_id}, status_code=201)


# ── GET /api/stock ────────────────────────────────────────────────────────────

@router.get("")
async def inventario(
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
                   p.precio_base_fecha,
                   cat.nombre  AS categoria,
                   sub.nombre  AS subcategoria,
                   COALESCE(AVG(cd.costo_unitario), p.precio_base, 0) AS costo_prom,
                   prov.nombre AS proveedor_principal,
                   p.maneja_lotes,
                   (SELECT COUNT(*) FROM lotes lt WHERE lt.producto_id = p.id AND lt.cantidad > 0) AS lote_count,
                   (SELECT MIN(lt.fecha_vencimiento) FROM lotes lt
                    WHERE lt.producto_id = p.id AND lt.cantidad > 0
                      AND lt.fecha_vencimiento IS NOT NULL) AS proximo_vencimiento
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

        # Ventas últimos 30 días por producto (para días de inventario)
        cur.execute("""
            SELECT cd.producto_id, SUM(cd.cantidad) AS vendido_30d
            FROM cotizacion_detalle cd
            JOIN cotizaciones cot ON cot.id = cd.cotizacion_id
            WHERE cot.estado IN ('Entregada','Facturada','Pagada')
              AND cot.fecha_entrega >= CURRENT_DATE - INTERVAL '30 days'
              AND cd.producto_id IS NOT NULL
            GROUP BY cd.producto_id
        """)
        ventas_30d = {r[0]: float(r[1]) for r in cur.fetchall()}

        cur.execute("SELECT nombre FROM categorias ORDER BY nombre")
        categorias = [r[0] for r in cur.fetchall()]

    hoy = _date.today()
    prox_30 = hoy.replace(day=min(hoy.day + 30, 28)) if hoy.day <= 28 else \
        _date(hoy.year + (hoy.month // 12), (hoy.month % 12) + 1, hoy.day - 28)

    for p in productos:
        # Días de inventario
        v30 = ventas_30d.get(p["id"], 0)
        tasa_diaria = v30 / 30.0
        stock = p.get("stock_actual") or 0
        if tasa_diaria > 0 and stock > 0:
            p["dias_inventario"] = round(stock / tasa_diaria)
        elif stock <= 0:
            p["dias_inventario"] = 0
        else:
            p["dias_inventario"] = None

        # Edad del precio_base en días
        pbf = p.get("precio_base_fecha")
        if pbf:
            try:
                fecha_pb = _date.fromisoformat(str(pbf)[:10])
                p["precio_base_dias"] = (hoy - fecha_pb).days
            except (ValueError, TypeError):
                p["precio_base_dias"] = None
        else:
            p["precio_base_dias"] = None

        # Alerta de lote vencimiento
        pv = p.get("proximo_vencimiento")
        if p.get("maneja_lotes") and pv:
            try:
                pv_d = _date.fromisoformat(str(pv)[:10])
                p["lote_alerta"] = "vencido" if pv_d < hoy else ("proximo" if pv_d <= prox_30 else "ok")
            except (ValueError, TypeError):
                p["lote_alerta"] = "ok"
        else:
            p["lote_alerta"] = None

    # Clasificación ABC por valor de inventario (acumulado: A=0-80%, B=80-95%, C=95-100%)
    total_valor = sum((p["stock_actual"] or 0) * (p["costo_prom"] or p["precio_base"] or 0) for p in productos)
    if total_valor > 0:
        sorted_by_valor = sorted(
            productos,
            key=lambda p: (p["stock_actual"] or 0) * (p["costo_prom"] or p["precio_base"] or 0),
            reverse=True,
        )
        acum = 0.0
        for p in sorted_by_valor:
            v = (p["stock_actual"] or 0) * (p["costo_prom"] or p["precio_base"] or 0)
            acum += v
            pct = acum / total_valor * 100
            p["abc"] = "A" if pct <= 80 else ("B" if pct <= 95 else "C")
    else:
        for p in productos:
            p["abc"] = "C"
    bajo_min_cnt  = sum(1 for p in productos if (p["stock_minimo"] or 0) > 0 and (p["stock_actual"] or 0) < (p["stock_minimo"] or 0))
    precio_stale_cnt = sum(1 for p in productos if (p.get("precio_base_dias") or 0) > 30)
    negativo_cnt  = sum(1 for p in productos if (p["stock_actual"] or 0) < 0)
    sin_stock_cnt = sum(1 for p in productos if (p["stock_actual"] or 0) == 0)

    return JSONResponse({
        "productos": productos,
        "categorias": categorias,
        "stats": {
            "total_valor":    round(total_valor, 2),
            "bajo_minimo":    bajo_min_cnt,
            "negativo":       negativo_cnt,
            "sin_stock":      sin_stock_cnt,
            "total_productos": len(productos),
            "precio_stale":   precio_stale_cnt,
        },
    })


MOTIVOS_AJUSTE = ("Conteo físico", "Merma", "Corrección sistema", "Donación", "Robo/pérdida", "Otro")


class AjusteBody(BaseModel):
    producto_id: int
    stock_nuevo: float
    motivo: str
    notas: Optional[str] = None
    referencia: Optional[str] = None


@router.post("/ajuste")
async def ajustar_stock(
    body: AjusteBody,
    user: dict = Depends(get_usuario_api),
):
    if user.get("rol") != "Administrador":
        raise HTTPException(403, "Solo el Administrador puede registrar ajustes de stock")
    if body.motivo not in MOTIVOS_AJUSTE:
        raise HTTPException(422, f"Motivo inválido. Opciones: {', '.join(MOTIVOS_AJUSTE)}")
    if body.motivo == "Otro" and not body.notas:
        raise HTTPException(422, "Las notas son obligatorias cuando el motivo es 'Otro'")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre, stock_actual FROM productos WHERE id = %s",
            (body.producto_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
        pid, nombre, stock_antes = row[0], row[1], float(row[2] or 0)

        stock_despues = body.stock_nuevo
        diferencia = stock_despues - stock_antes

        cur.execute(
            "UPDATE productos SET stock_actual = %s WHERE id = %s",
            (stock_despues, pid),
        )
        cur.execute("""
            INSERT INTO movimientos_stock
                (producto_id, tipo, motivo, cantidad,
                 stock_antes, stock_despues, referencia, notas, usuario)
            VALUES (%s, 'ajuste', %s, %s, %s, %s, %s, %s, %s)
        """, (
            pid, body.motivo, abs(diferencia),
            stock_antes, stock_despues,
            body.referencia or None,
            body.notas or None,
            user["nombre"],
        ))

    return {
        "ok": True,
        "producto": nombre,
        "stock_antes": stock_antes,
        "stock_despues": stock_despues,
        "diferencia": diferencia,
    }


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
