# -*- coding: utf-8 -*-
"""
web_app/routers/api_devoluciones.py
/api/devoluciones — devoluciones de cliente.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/devoluciones", tags=["api"])

POR_PAGINA = 25


def _s(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _s(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


# ── GET /api/devoluciones ─────────────────────────────────────────────────────

@router.get("")
async def listar(
    q: str = Query(""),
    estado: str = Query(""),
    pagina: int = Query(1, ge=1),
    razon_social_id: Optional[int] = Query(None),
    user: dict = Depends(get_usuario_api),
):
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso")

    empresa_db = user["empresa_db"]
    where, params = [], []
    if razon_social_id is not None:
        where.append("d.razon_social_id = %s")
        params.append(razon_social_id)
    if q:
        where.append("(d.folio ILIKE %s OR COALESCE(cl.nombre_comercial,'') ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if estado:
        where.append("d.estado = %s")
        params.append(estado)

    filtro = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (pagina - 1) * POR_PAGINA

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(f"SELECT COUNT(*) FROM devoluciones d LEFT JOIN clientes cl ON cl.id = d.cliente_id {filtro}", params or None)
        total = cur.fetchone()[0]

        cur.execute(f"""
            SELECT d.id, d.folio, d.fecha, d.estado, d.total, d.motivo,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cot.folio AS cot_folio
            FROM devoluciones d
            LEFT JOIN clientes cl ON cl.id = d.cliente_id
            LEFT JOIN cotizaciones cot ON cot.id = d.cotizacion_id
            {filtro}
            ORDER BY d.fecha DESC, d.id DESC
            LIMIT {POR_PAGINA} OFFSET {offset}
        """, params or None)
        rows = _rows(cur)

        cur.execute("SELECT estado, COUNT(*) FROM devoluciones GROUP BY estado")
        conteo = {r[0]: r[1] for r in cur.fetchall()}

    return JSONResponse({
        "devoluciones": rows, "total": total,
        "pagina": pagina, "total_pags": max(1, (total + POR_PAGINA - 1) // POR_PAGINA),
        "conteo": conteo,
    })


# ── GET /api/devoluciones/{id} ────────────────────────────────────────────────

@router.get("/{dev_id}")
async def detalle(dev_id: int, user: dict = Depends(get_usuario_api)):
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso")

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT d.*,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cl.rfc AS cliente_rfc,
                   cot.folio AS cot_folio
            FROM devoluciones d
            LEFT JOIN clientes cl ON cl.id = d.cliente_id
            LEFT JOIN cotizaciones cot ON cot.id = d.cotizacion_id
            WHERE d.id = %s
        """, (dev_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Devolución no encontrada")
        cols = [d[0] for d in cur.description]
        dev = {k: _s(v) for k, v in zip(cols, row)}

        cur.execute("""
            SELECT dd.id, dd.cantidad, dd.precio_unitario, dd.total, dd.retorna_stock,
                   p.nombre, p.codigo, p.unidad_medida
            FROM devolucion_detalle dd
            JOIN productos p ON p.id = dd.producto_id
            WHERE dd.devolucion_id = %s
            ORDER BY dd.id
        """, (dev_id,))
        lineas = _rows(cur)

    return JSONResponse({"devolucion": dev, "lineas": lineas})


# ── POST /api/devoluciones ────────────────────────────────────────────────────

class LineaDevIn(BaseModel):
    producto_id: int
    cantidad: float
    precio_unitario: float
    retorna_stock: bool = True


class DevolucionIn(BaseModel):
    cotizacion_id: Optional[int] = None
    cliente_id: int
    fecha: str
    motivo: Optional[str] = None
    notas: Optional[str] = None
    lineas: List[LineaDevIn]
    razon_social_id: Optional[int] = None


@router.post("", status_code=201)
async def crear(body: DevolucionIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if not body.lineas:
        raise HTTPException(status_code=400, detail="Debe incluir al menos una línea")

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT COUNT(*) FROM devoluciones WHERE folio LIKE %s", (f"DEV-{date.today().year}-%",))
        n = cur.fetchone()[0] + 1
        folio = f"DEV-{date.today().year}-{n:04d}"

        total = sum(l.cantidad * l.precio_unitario for l in body.lineas)

        cur.execute("""
            INSERT INTO devoluciones (folio, cotizacion_id, cliente_id, fecha, motivo, notas, total, razon_social_id)
            VALUES (%s, %s, %s, %s::date, %s, %s, %s, %s)
        """, (folio, body.cotizacion_id, body.cliente_id, body.fecha,
              body.motivo or None, body.notas or None, total, body.razon_social_id))
        dev_id = cur.lastrowid

        for l in body.lineas:
            linea_total = l.cantidad * l.precio_unitario
            cur.execute("""
                INSERT INTO devolucion_detalle
                    (devolucion_id, producto_id, cantidad, precio_unitario, total, retorna_stock)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (dev_id, l.producto_id, l.cantidad, l.precio_unitario, linea_total, l.retorna_stock))

            if l.retorna_stock:
                cur.execute("""
                    UPDATE productos
                       SET stock_actual = COALESCE(stock_actual, 0) + %s
                     WHERE id = %s
                """, (l.cantidad, l.producto_id))
                cur.execute("""
                    INSERT INTO movimientos_stock
                        (producto_id, tipo, motivo, cantidad,
                         stock_antes, stock_despues, referencia)
                    SELECT %s, 'entrada', 'devolucion', %s,
                           stock_actual - %s, stock_actual, %s
                    FROM productos WHERE id = %s
                """, (l.producto_id, l.cantidad, l.cantidad, folio, l.producto_id))

    return JSONResponse({"id": dev_id, "folio": folio}, status_code=201)


# ── PATCH /api/devoluciones/{id}/cerrar ──────────────────────────────────────

@router.patch("/{dev_id}/cerrar")
async def cerrar(dev_id: int, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("UPDATE devoluciones SET estado = 'Cerrada' WHERE id = %s", (dev_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Devolución no encontrada")
    return JSONResponse({"ok": True})
