# -*- coding: utf-8 -*-
"""
web_app/routers/api_estudio_mercado.py
/api/estudio-mercado — endpoints JSON para el SPA React.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/estudio-mercado", tags=["api"])

_tablas_ok: set[str] = set()

_DDL = """
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


def _asegurar_tablas(empresa_db: str) -> None:
    if empresa_db in _tablas_ok:
        return
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        for stmt in _DDL.strip().split(";"):
            s = stmt.strip()
            if s:
                cur.execute(s)
        cur.execute("ALTER TABLE estudios_mercado ADD COLUMN IF NOT EXISTS margen_pct NUMERIC(5,4) DEFAULT 0.35")
        cur.execute("ALTER TABLE estudios_mercado ADD COLUMN IF NOT EXISTS cotizacion_id INTEGER REFERENCES cotizaciones(id)")
    _tablas_ok.add(empresa_db)


def _s(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _s(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


def _pivotear(items_raw: list, margen_pct: float) -> tuple[list, list]:
    proveedores: list[str] = []
    for item in items_raw:
        for cot in item.get("cotizaciones", []):
            n = cot["nombre_proveedor"]
            if n not in proveedores:
                proveedores.append(n)

    for item in items_raw:
        por_prov = {p: None for p in proveedores}
        for cot in item.get("cotizaciones", []):
            por_prov[cot["nombre_proveedor"]] = cot["precio_unitario"]

        validos = [v for v in por_prov.values() if v is not None]
        min_precio = min(validos) if validos else None
        item["precios_por_prov"] = por_prov
        item["min_precio"]       = min_precio
        item["precio_estimado"]  = round(min_precio * (1 + margen_pct), 4) if min_precio else None
        item["mejor_proveedor"]  = next(
            (c["nombre_proveedor"] for c in item["cotizaciones"] if c["precio_unitario"] == min_precio),
            None,
        ) if min_precio else None

    return items_raw, proveedores


# ── Pydantic models ───────────────────────────────────────────────────────────

class EstudioIn(BaseModel):
    nombre: str
    descripcion: str = ""
    cotizacion_id: Optional[int] = None
    margen_pct: float = 0.35


class ItemIn(BaseModel):
    nombre_articulo: str
    cantidad: float = 1
    unidad: str = ""
    producto_id: Optional[int] = None


class CotizacionProvIn(BaseModel):
    proveedor_id: Optional[int] = None
    nombre_proveedor: str
    precio_unitario: float
    notas: str = ""


class MargenIn(BaseModel):
    margen_pct: float


# ── GET /api/estudio-mercado ──────────────────────────────────────────────────

@router.get("")
async def listar(
    estado: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    _asegurar_tablas(user["empresa_db"])

    where = ["1=1"]
    params: list = []
    if estado:
        where.append("e.estado = %s")
        params.append(estado)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT e.id, e.nombre, e.fecha, e.estado, e.descripcion,
                   e.margen_pct, e.cotizacion_id,
                   COUNT(DISTINCT i.id)  AS total_items,
                   COUNT(DISTINCT c2.id) AS total_cotizaciones
            FROM estudios_mercado e
            LEFT JOIN estudio_mercado_items i  ON i.estudio_id = e.id
            LEFT JOIN estudio_mercado_cotizaciones c2 ON c2.item_id = i.id
            WHERE {" AND ".join(where)}
            GROUP BY e.id
            ORDER BY e.fecha_registro DESC
        """, params)
        estudios = _rows(cur)

    return {"estudios": estudios}


# ── POST /api/estudio-mercado ─────────────────────────────────────────────────

@router.post("")
async def crear(body: EstudioIn, user: dict = Depends(get_usuario_api)):
    from datetime import date
    nombre = body.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="Nombre requerido")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO estudios_mercado (nombre, fecha, descripcion, margen_pct, cotizacion_id)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (nombre, date.today().isoformat(), body.descripcion,
              body.margen_pct, body.cotizacion_id))
        estudio_id = cur.fetchone()[0]

        # Si viene de una cotización, pre-llenar ítems
        if body.cotizacion_id:
            cur.execute("""
                SELECT cd.cantidad, cd.descripcion_libre,
                       p.nombre, p.id AS producto_id, p.unidad_medida
                FROM cotizacion_detalle cd
                LEFT JOIN productos p ON p.id = cd.producto_id
                WHERE cd.cotizacion_id = %s
            """, (body.cotizacion_id,))
            for row in cur.fetchall():
                cantidad, desc_libre, pnom, prod_id, unidad = row
                nombre_art = pnom or desc_libre or "Sin nombre"
                cur.execute("""
                    INSERT INTO estudio_mercado_items
                        (estudio_id, producto_id, nombre_articulo, cantidad, unidad)
                    VALUES (%s, %s, %s, %s, %s)
                """, (estudio_id, prod_id, nombre_art, float(cantidad or 1), unidad or ""))

    return {"id": estudio_id}


# ── GET /api/estudio-mercado/{id} ─────────────────────────────────────────────

@router.get("/{estudio_id}")
async def detalle(estudio_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, nombre, fecha, estado, descripcion, margen_pct, cotizacion_id
            FROM estudios_mercado WHERE id = %s
        """, (estudio_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Estudio no encontrado")
        cols = ["id", "nombre", "fecha", "estado", "descripcion", "margen_pct", "cotizacion_id"]
        estudio = {k: _s(v) for k, v in zip(cols, row)}

        cur.execute("""
            SELECT i.id, i.nombre_articulo, i.cantidad, i.unidad, i.producto_id
            FROM estudio_mercado_items i WHERE i.estudio_id = %s ORDER BY i.id
        """, (estudio_id,))
        items_raw = _rows(cur)

        for item in items_raw:
            cur.execute("""
                SELECT id, nombre_proveedor, precio_unitario, notas, proveedor_id
                FROM estudio_mercado_cotizaciones WHERE item_id = %s
                ORDER BY precio_unitario
            """, (item["id"],))
            item["cotizaciones"] = _rows(cur)

        margen = float(estudio.get("margen_pct") or 0.35)
        items, proveedores = _pivotear(items_raw, margen)

    return {"estudio": estudio, "items": items, "proveedores": proveedores}


# ── PUT /api/estudio-mercado/{id}/margen ─────────────────────────────────────

@router.put("/{estudio_id}/margen")
async def actualizar_margen(
    estudio_id: int,
    body: MargenIn,
    user: dict = Depends(get_usuario_api),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE estudios_mercado SET margen_pct = %s WHERE id = %s RETURNING id",
            (body.margen_pct, estudio_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Estudio no encontrado")
    return {"ok": True}


# ── POST /api/estudio-mercado/{id}/items ─────────────────────────────────────

@router.post("/{estudio_id}/items")
async def agregar_item(
    estudio_id: int,
    body: ItemIn,
    user: dict = Depends(get_usuario_api),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO estudio_mercado_items
                (estudio_id, nombre_articulo, cantidad, unidad, producto_id)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (estudio_id, body.nombre_articulo.strip(), body.cantidad,
              body.unidad, body.producto_id))
        item_id = cur.fetchone()[0]
    return {"id": item_id}


# ── DELETE /api/estudio-mercado/items/{item_id} ───────────────────────────────

@router.delete("/items/{item_id}")
async def eliminar_item(item_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "DELETE FROM estudio_mercado_items WHERE id = %s RETURNING id", (item_id,)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Ítem no encontrado")
    return {"ok": True}


# ── POST /api/estudio-mercado/items/{item_id}/cotizaciones ───────────────────

@router.post("/items/{item_id}/cotizaciones")
async def agregar_cotizacion_prov(
    item_id: int,
    body: CotizacionProvIn,
    user: dict = Depends(get_usuario_api),
):
    if not body.nombre_proveedor.strip():
        raise HTTPException(status_code=422, detail="Nombre de proveedor requerido")
    if body.precio_unitario <= 0:
        raise HTTPException(status_code=422, detail="El precio debe ser positivo")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO estudio_mercado_cotizaciones
                (item_id, proveedor_id, nombre_proveedor, precio_unitario, notas)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (item_id, body.proveedor_id, body.nombre_proveedor.strip(),
              body.precio_unitario, body.notas or None))
        cot_id = cur.fetchone()[0]
    return {"id": cot_id}


# ── DELETE /api/estudio-mercado/cotizaciones/{cot_id} ────────────────────────

@router.delete("/cotizaciones/{cot_id}")
async def eliminar_cotizacion_prov(cot_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "DELETE FROM estudio_mercado_cotizaciones WHERE id = %s RETURNING id", (cot_id,)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return {"ok": True}


# ── GET /api/estudio-mercado/proveedores ─────────────────────────────────────

@router.get("/proveedores/lista")
async def listar_proveedores(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
        provs = _rows(cur)
    return {"proveedores": provs}
