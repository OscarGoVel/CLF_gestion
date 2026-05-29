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

router = APIRouter(prefix="/api/abastecimiento/estudios", tags=["api"])

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
        cur.execute("ALTER TABLE estudio_mercado_cotizaciones ADD COLUMN IF NOT EXISTS ganador BOOLEAN NOT NULL DEFAULT FALSE")
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
        por_prov: dict = {p: None for p in proveedores}
        cot_ids_por_prov: dict = {p: None for p in proveedores}
        ganador_prov: Optional[str] = None

        for cot in item.get("cotizaciones", []):
            p = cot["nombre_proveedor"]
            por_prov[p] = cot["precio_unitario"]
            cot_ids_por_prov[p] = cot["id"]
            if cot.get("ganador"):
                ganador_prov = p

        validos = [v for v in por_prov.values() if v is not None]
        min_precio = min(validos) if validos else None
        item["precios_por_prov"]  = por_prov
        item["cot_ids_por_prov"]  = cot_ids_por_prov
        item["min_precio"]        = min_precio
        item["precio_estimado"]   = round(min_precio * (1 + margen_pct), 4) if min_precio else None
        item["mejor_proveedor"]   = next(
            (c["nombre_proveedor"] for c in item["cotizaciones"] if c["precio_unitario"] == min_precio),
            None,
        ) if min_precio else None
        item["ganador_proveedor"] = ganador_prov

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
                SELECT id, nombre_proveedor, precio_unitario, notas, proveedor_id, ganador
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


# ── PATCH /api/estudios/cotizaciones/{cot_id}/ganador ────────────────────────

@router.patch("/cotizaciones/{cot_id}/ganador")
async def marcar_ganador(cot_id: int, user: dict = Depends(get_usuario_api)):
    """Alterna el ganador para una cotización de proveedor.
    Desmarca los demás del mismo ítem antes de marcar ésta.
    Si ya era ganador, la desmarca (toggle off)."""
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT item_id, ganador FROM estudio_mercado_cotizaciones WHERE id = %s",
            (cot_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización de proveedor no encontrada")
        item_id, era_ganador = row

        # Desmarcar todos los del mismo ítem
        cur.execute(
            "UPDATE estudio_mercado_cotizaciones SET ganador = FALSE WHERE item_id = %s",
            (item_id,),
        )
        # Si no era ganador, marcar éste
        nuevo_ganador = not era_ganador
        if nuevo_ganador:
            cur.execute(
                "UPDATE estudio_mercado_cotizaciones SET ganador = TRUE WHERE id = %s",
                (cot_id,),
            )
    return {"ganador": nuevo_ganador}


# ── POST /api/estudios/{estudio_id}/aplicar-costos ───────────────────────────

@router.post("/{estudio_id}/aplicar-costos")
async def aplicar_costos(estudio_id: int, user: dict = Depends(get_usuario_api)):
    """Toma el precio del ganador por ítem y lo escribe en:
    - productos.precio_base
    - producto_precio_historial (fuente: estudio_mercado)
    - cotizacion_detalle.costo_snapshot (si el estudio tiene cotizacion_id)"""
    from datetime import date as _date

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT cotizacion_id FROM estudios_mercado WHERE id = %s", (estudio_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Estudio no encontrado")
        cotizacion_id = row[0]

        cur.execute("""
            SELECT i.producto_id, i.nombre_articulo,
                   c.precio_unitario, c.nombre_proveedor, c.proveedor_id
            FROM estudio_mercado_items i
            JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id AND c.ganador = TRUE
            WHERE i.estudio_id = %s AND i.producto_id IS NOT NULL
        """, (estudio_id,))
        ganadores = _rows(cur)

        if not ganadores:
            raise HTTPException(
                status_code=422,
                detail="No hay ganadores con producto del catálogo. Marca al menos un ganador.",
            )

        hoy = _date.today().isoformat()
        actualizados = 0
        for g in ganadores:
            prod_id = g["producto_id"]
            precio  = g["precio_unitario"]

            cur.execute(
                "SELECT COALESCE(precio_base, 0) FROM productos WHERE id = %s", (prod_id,)
            )
            old_precio = float((cur.fetchone() or [0])[0])

            cur.execute(
                "UPDATE productos SET precio_base = %s WHERE id = %s", (precio, prod_id)
            )

            cur.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente, proveedor_id)
                VALUES (%s, %s, %s, %s, 'estudio_mercado', %s)
            """, (prod_id, precio, hoy,
                  f"Estudio de mercado #{estudio_id} — ganador: {g['nombre_proveedor']}",
                  g.get("proveedor_id")))

            if cotizacion_id:
                cur.execute("""
                    UPDATE cotizacion_detalle
                    SET costo_snapshot = %s
                    WHERE cotizacion_id = %s AND producto_id = %s
                """, (precio, cotizacion_id, prod_id))

            actualizados += 1

    return {"actualizados": actualizados}


# ── POST /api/estudios/{estudio_id}/generar-compra ───────────────────────────

@router.post("/{estudio_id}/generar-compra")
async def generar_compra(estudio_id: int, user: dict = Depends(get_usuario_api)):
    """Crea una Orden de Compra por cada proveedor ganador distinto.
    Las líneas se vinculan a la cotización del estudio si existe."""
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    from datetime import date as _date
    from decimal import Decimal

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT cotizacion_id FROM estudios_mercado WHERE id = %s", (estudio_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Estudio no encontrado")
        cotizacion_id = row[0]

        cur.execute("""
            SELECT i.producto_id, i.cantidad, i.nombre_articulo,
                   c.precio_unitario, c.proveedor_id, c.nombre_proveedor
            FROM estudio_mercado_items i
            JOIN estudio_mercado_cotizaciones c ON c.item_id = i.id AND c.ganador = TRUE
            WHERE i.estudio_id = %s AND i.producto_id IS NOT NULL
        """, (estudio_id,))
        ganadores = _rows(cur)

        if not ganadores:
            raise HTTPException(
                status_code=422,
                detail="No hay ganadores con producto del catálogo.",
            )

        # Agrupar por proveedor (prov_id puede ser NULL si se capturó manual)
        por_proveedor: dict = {}
        for g in ganadores:
            key = (g["proveedor_id"], g["nombre_proveedor"])
            por_proveedor.setdefault(key, []).append(g)

        hoy = _date.today().isoformat()
        año = _date.today().year
        compra_ids: list[int] = []

        for (prov_id, prov_nombre), items in por_proveedor.items():
            # Folio único dentro de la transacción
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtext('folio_compra'))"
            )
            cur.execute(
                "SELECT COUNT(*) FROM compras WHERE folio LIKE %s", (f"CMP-{año}-%",)
            )
            n = cur.fetchone()[0] + 1
            folio = f"CMP-{año}-{n:04d}"

            subtotal = sum(
                Decimal(str(it["precio_unitario"])) * Decimal(str(it["cantidad"]))
                for it in items
            )

            cur.execute("""
                INSERT INTO compras
                  (folio, proveedor_id, fecha_compra, subtotal, iva, total, notas)
                VALUES (%s, %s, %s, %s, 0, %s, %s)
                RETURNING id
            """, (
                folio, prov_id, hoy,
                float(subtotal), float(subtotal),
                f"Generada desde Estudio de Mercado #{estudio_id}",
            ))
            compra_id = cur.fetchone()[0]

            for it in items:
                importe = Decimal(str(it["precio_unitario"])) * Decimal(str(it["cantidad"]))
                cur.execute("""
                    INSERT INTO compra_detalle
                      (compra_id, producto_id, cantidad, costo_unitario, costo_total)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    compra_id, it["producto_id"],
                    float(it["cantidad"]), float(it["precio_unitario"]), float(importe),
                ))
                detalle_id = cur.fetchone()[0]

                if cotizacion_id:
                    cur.execute("""
                        INSERT INTO compra_detalle_cotizacion
                          (compra_detalle_id, cotizacion_id, cantidad)
                        VALUES (%s, %s, %s)
                    """, (detalle_id, cotizacion_id, float(it["cantidad"])))

            compra_ids.append(compra_id)

    return {"compra_ids": compra_ids, "compra_id": compra_ids[0]}
