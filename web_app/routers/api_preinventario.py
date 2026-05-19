# -*- coding: utf-8 -*-
"""
web_app/routers/api_preinventario.py
/api/preinventario — endpoints JSON para el SPA React.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/preinventario", tags=["api"])

# Empresas con tablas ya inicializadas en esta ejecución
_tablas_ok: set[str] = set()

_DDL = """
CREATE TABLE IF NOT EXISTS sucursales (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL,
    descripcion TEXT
);
CREATE TABLE IF NOT EXISTS areas (
    id          SERIAL PRIMARY KEY,
    sucursal_id INTEGER NOT NULL REFERENCES sucursales(id) ON DELETE CASCADE,
    nombre      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_ubicaciones (
    producto_id INTEGER PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
    area_id     INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS preinventario_sesiones (
    id               SERIAL PRIMARY KEY,
    nombre           TEXT NOT NULL,
    creado_por       TEXT NOT NULL,
    estado           TEXT NOT NULL DEFAULT 'abierta',
    tipo             TEXT NOT NULL DEFAULT 'parcial',
    fecha_creacion   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_cierre     TIMESTAMPTZ,
    aprobado_por     TEXT,
    fecha_aprobacion TIMESTAMPTZ,
    notas_aprobacion TEXT
);
CREATE TABLE IF NOT EXISTS preinventario_items (
    id                SERIAL PRIMARY KEY,
    sesion_id         INTEGER NOT NULL REFERENCES preinventario_sesiones(id) ON DELETE CASCADE,
    producto_id       INTEGER NOT NULL REFERENCES productos(id),
    cantidad_teorica  REAL,
    cantidad_fisica   REAL NOT NULL,
    capturado_por     TEXT NOT NULL,
    fecha_captura     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ajustado_por      TEXT,
    cantidad_ajustada REAL,
    notas             TEXT
);
CREATE TABLE IF NOT EXISTS sesion_areas (
    sesion_id INTEGER NOT NULL REFERENCES preinventario_sesiones(id) ON DELETE CASCADE,
    area_id   INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    PRIMARY KEY (sesion_id, area_id)
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
        cur.execute(
            "ALTER TABLE preinventario_sesiones ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'parcial'"
        )
    _tablas_ok.add(empresa_db)


def _s(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _s(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


# ── Pydantic models ───────────────────────────────────────────────────────────

class SesionIn(BaseModel):
    nombre: str
    tipo: str = "parcial"
    sucursal_id: Optional[int] = None
    area_ids: list[int] = []


class ItemIn(BaseModel):
    producto_id: int
    cantidad_contada: float
    observaciones: Optional[str] = None


class RechazarIn(BaseModel):
    motivo: str = ""


class AprobarIn(BaseModel):
    clave: str
    notas: str = ""


# ── GET /api/preinventario/sesiones ──────────────────────────────────────────

@router.get("/sesiones")
async def listar_sesiones(
    estado: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    _asegurar_tablas(user["empresa_db"])

    where = ["1=1"]
    params: list = []
    if estado:
        where.append("s.estado = %s")
        params.append(estado)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT s.id, s.nombre, s.estado, s.tipo, s.creado_por,
                   s.fecha_creacion, s.fecha_cierre, s.aprobado_por,
                   COUNT(i.id) AS total_items
            FROM preinventario_sesiones s
            LEFT JOIN preinventario_items i ON i.sesion_id = s.id
            WHERE {" AND ".join(where)}
            GROUP BY s.id
            ORDER BY
                CASE s.estado WHEN 'abierta' THEN 0 WHEN 'cerrada' THEN 1 ELSE 2 END,
                s.fecha_creacion DESC
            LIMIT 100
        """, params)
        sesiones = _rows(cur)

        # KPIs
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE estado = 'abierta')    AS abiertas,
                COUNT(*) FILTER (WHERE estado = 'cerrada')    AS pendientes_aprobacion,
                COUNT(*) FILTER (
                    WHERE estado = 'aprobada'
                      AND DATE_TRUNC('month', fecha_aprobacion) = DATE_TRUNC('month', NOW())
                )                                             AS aprobadas_mes
            FROM preinventario_sesiones
        """)
        r = cur.fetchone()
        kpis = {"abiertas": r[0], "pendientes_aprobacion": r[1], "aprobadas_mes": r[2]}

        # Sucursales para el formulario de nueva sesión
        cur.execute("""
            SELECT a.id, a.nombre, s.id AS sucursal_id, s.nombre AS sucursal_nombre
            FROM areas a
            JOIN sucursales s ON s.id = a.sucursal_id
            ORDER BY s.nombre, a.nombre
        """)
        areas_raw = cur.fetchall()

    sucursales_map: dict = {}
    for area_id, area_nombre, suc_id, suc_nombre in areas_raw:
        if suc_id not in sucursales_map:
            sucursales_map[suc_id] = {"id": suc_id, "nombre": suc_nombre, "areas": []}
        sucursales_map[suc_id]["areas"].append({"id": area_id, "nombre": area_nombre})

    return {
        "sesiones": sesiones,
        "kpis": kpis,
        "sucursales": list(sucursales_map.values()),
    }


# ── POST /api/preinventario/sesiones ─────────────────────────────────────────

@router.post("/sesiones")
async def crear_sesion(body: SesionIn, user: dict = Depends(get_usuario_api)):
    nombre = body.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="Nombre requerido")
    tipo = body.tipo if body.tipo in ("parcial", "completo") else "parcial"

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO preinventario_sesiones (nombre, creado_por, tipo)
            VALUES (%s, %s, %s) RETURNING id
        """, (nombre, user["nombre"], tipo))
        sesion_id = cur.fetchone()[0]

        for area_id in body.area_ids:
            cur.execute(
                "INSERT INTO sesion_areas (sesion_id, area_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (sesion_id, area_id),
            )

    return {"id": sesion_id, "nombre": nombre, "tipo": tipo, "estado": "abierta"}


# ── GET /api/preinventario/sesiones/{id} ─────────────────────────────────────

@router.get("/sesiones/{sesion_id}")
async def detalle_sesion(sesion_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, nombre, estado, creado_por, fecha_creacion, tipo,
                   fecha_cierre, aprobado_por, notas_aprobacion
            FROM preinventario_sesiones WHERE id = %s
        """, (sesion_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        cols = ["id", "nombre", "estado", "creado_por", "fecha_creacion", "tipo",
                "fecha_cierre", "aprobado_por", "notas_aprobacion"]
        sesion = {k: _s(v) for k, v in zip(cols, row)}

        cur.execute("""
            SELECT a.id, a.nombre, s.nombre AS sucursal
            FROM sesion_areas sa
            JOIN areas a ON a.id = sa.area_id
            JOIN sucursales s ON s.id = a.sucursal_id
            WHERE sa.sesion_id = %s ORDER BY s.nombre, a.nombre
        """, (sesion_id,))
        sesion["areas"] = _rows(cur)

        cur.execute("""
            SELECT i.id, p.codigo, p.nombre AS producto, p.unidad_medida,
                   i.cantidad_teorica AS cantidad_sistema,
                   i.cantidad_fisica  AS cantidad_contada,
                   i.notas,
                   COALESCE(i.cantidad_fisica, 0) - COALESCE(i.cantidad_teorica, 0) AS diferencia
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY i.fecha_captura DESC
        """, (sesion_id,))
        items = _rows(cur)

        skus_contados = len(items)
        sesion["skus_contados"] = skus_contados
        sesion["total_skus"] = skus_contados

    return {"sesion": sesion, "items": items}


# ── POST /api/preinventario/sesiones/{id}/items ───────────────────────────────

@router.post("/sesiones/{sesion_id}/items")
async def guardar_item(
    sesion_id: int,
    body: ItemIn,
    user: dict = Depends(get_usuario_api),
):
    if body.cantidad_contada < 0:
        raise HTTPException(status_code=422, detail="La cantidad no puede ser negativa")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT estado FROM preinventario_sesiones WHERE id = %s", (sesion_id,)
        )
        row = cur.fetchone()
        if not row or row[0] != "abierta":
            raise HTTPException(status_code=409, detail="La sesión no está abierta para captura")

        cur.execute(
            "SELECT stock_actual FROM productos WHERE id = %s", (body.producto_id,)
        )
        p_row = cur.fetchone()
        if not p_row:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        cantidad_teorica = float(p_row[0] or 0)

        cur.execute(
            "SELECT id FROM preinventario_items WHERE sesion_id = %s AND producto_id = %s",
            (sesion_id, body.producto_id),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE preinventario_items
                SET cantidad_fisica = %s, cantidad_teorica = %s,
                    notas = %s, capturado_por = %s, fecha_captura = NOW()
                WHERE id = %s RETURNING id
            """, (body.cantidad_contada, cantidad_teorica,
                  body.observaciones, user["nombre"], existing[0]))
        else:
            cur.execute("""
                INSERT INTO preinventario_items
                    (sesion_id, producto_id, cantidad_teorica, cantidad_fisica,
                     capturado_por, notas)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (sesion_id, body.producto_id, cantidad_teorica,
                  body.cantidad_contada, user["nombre"], body.observaciones))
        item_id = cur.fetchone()[0]

    return {
        "id": item_id,
        "producto_id": body.producto_id,
        "cantidad_sistema": cantidad_teorica,
        "cantidad_contada": body.cantidad_contada,
        "diferencia": round(body.cantidad_contada - cantidad_teorica, 4),
    }


# ── DELETE /api/preinventario/items/{item_id} ─────────────────────────────────

@router.delete("/items/{item_id}")
async def eliminar_item(item_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT i.sesion_id, s.estado
            FROM preinventario_items i
            JOIN preinventario_sesiones s ON s.id = i.sesion_id
            WHERE i.id = %s
        """, (item_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ítem no encontrado")
        if row[1] != "abierta":
            raise HTTPException(status_code=409, detail="La sesión no está abierta")
        cur.execute("DELETE FROM preinventario_items WHERE id = %s", (item_id,))
    return {"ok": True}


# ── GET /api/preinventario/buscar ────────────────────────────────────────────

@router.get("/buscar")
async def buscar_producto(
    q: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    if len(q.strip()) < 2:
        return {"resultados": []}

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS codigo_barras TEXT")
        cur.execute("""
            SELECT id, codigo, nombre, stock_actual, unidad_medida
            FROM productos
            WHERE nombre ILIKE %s OR codigo ILIKE %s OR codigo_barras ILIKE %s
            ORDER BY nombre LIMIT 10
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        resultados = _rows(cur)

    return {"resultados": resultados}


# ── POST /api/preinventario/sesiones/{id}/cerrar ─────────────────────────────

@router.post("/sesiones/{sesion_id}/cerrar")
async def cerrar_sesion(sesion_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE preinventario_sesiones
            SET estado = 'cerrada', fecha_cierre = NOW()
            WHERE id = %s AND estado = 'abierta'
            RETURNING id
        """, (sesion_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=409, detail="La sesión no está abierta")
    return {"ok": True, "estado": "cerrada"}


# ── GET /api/preinventario/sesiones/{id}/preaprobacion ───────────────────────

@router.get("/sesiones/{sesion_id}/preaprobacion")
async def preaprobacion(
    sesion_id: int,
    user: dict = Depends(get_usuario_api),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre, estado, tipo FROM preinventario_sesiones WHERE id = %s",
            (sesion_id,),
        )
        row = cur.fetchone()
        if not row or row[2] != "cerrada":
            raise HTTPException(status_code=400, detail="La sesión debe estar cerrada para pre-aprobar")
        sesion = {"id": row[0], "nombre": row[1], "tipo": row[3]}

        cur.execute("""
            SELECT i.id, p.id AS producto_id, p.codigo, p.nombre AS producto,
                   p.unidad_medida, p.stock_actual AS stock_ahora,
                   i.cantidad_teorica, i.cantidad_fisica, i.cantidad_ajustada,
                   COALESCE(i.cantidad_ajustada, i.cantidad_fisica) AS cantidad_final
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
            ORDER BY ABS(COALESCE(i.cantidad_ajustada, i.cantidad_fisica) - p.stock_actual) DESC
        """, (sesion_id,))
        items_raw = _rows(cur)

    items = []
    for i in items_raw:
        stock_ahora   = float(i["stock_ahora"] or 0)
        teorica       = float(i["cantidad_teorica"] or 0)
        final         = float(i["cantidad_final"])
        items.append({
            **i,
            "stock_ahora": stock_ahora,
            "delta_conteo": round(final - teorica, 4),
            "ajuste_real":  round(final - stock_ahora, 4),
            "discrepancia": abs(final - stock_ahora) > 0.01,
        })

    return {"sesion": sesion, "items": items}


# ── POST /api/preinventario/sesiones/{id}/aprobar ────────────────────────────

@router.post("/sesiones/{sesion_id}/aprobar")
async def aprobar_sesion(
    sesion_id: int,
    body: AprobarIn,
    user: dict = Depends(get_usuario_api),
):
    from web_app.auth import verificar_password
    from web_app.database import pool_usuarios

    # Verificar contraseña del admin
    with pool_usuarios.conexion() as (_, cur):
        cur.execute(
            "SELECT password_hash FROM usuarios WHERE username = %s AND activo = 1",
            (user["username"],),
        )
        row = cur.fetchone()
    if not row or not verificar_password(body.clave, row[0]):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT estado, nombre FROM preinventario_sesiones WHERE id = %s FOR UPDATE",
            (sesion_id,),
        )
        row = cur.fetchone()
        if not row or row[0] != "cerrada":
            raise HTTPException(status_code=409, detail="La sesión debe estar cerrada para aprobar")

        cur.execute("""
            SELECT i.producto_id, p.stock_actual,
                   COALESCE(i.cantidad_ajustada, i.cantidad_fisica) AS cantidad_final
            FROM preinventario_items i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.sesion_id = %s
        """, (sesion_id,))
        items = cur.fetchall()

        for producto_id, stock_antes, cantidad_final in items:
            stock_antes    = float(stock_antes or 0)
            cantidad_final = float(cantidad_final)
            diferencia     = cantidad_final - stock_antes
            if abs(diferencia) < 0.001:
                continue
            tipo_mov = "entrada" if diferencia > 0 else "salida"
            cur.execute(
                "UPDATE productos SET stock_actual = %s WHERE id = %s",
                (cantidad_final, producto_id),
            )
            cur.execute("""
                INSERT INTO movimientos_stock
                    (producto_id, tipo, motivo, cantidad,
                     stock_antes, stock_despues, referencia, notas, usuario)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (producto_id, tipo_mov, "Ajuste por inventario físico",
                  abs(diferencia), stock_antes, cantidad_final,
                  f"PREINV-{sesion_id}", body.notas or None, user["nombre"]))

        cur.execute("""
            UPDATE preinventario_sesiones
            SET estado = 'aprobada', aprobado_por = %s,
                fecha_aprobacion = NOW(), notas_aprobacion = %s
            WHERE id = %s
        """, (user["nombre"], body.notas or None, sesion_id))

    return {"ok": True, "estado": "aprobada"}


# ── POST /api/preinventario/sesiones/{id}/rechazar ───────────────────────────

@router.post("/sesiones/{sesion_id}/rechazar")
async def rechazar_sesion(
    sesion_id: int,
    body: RechazarIn,
    user: dict = Depends(get_usuario_api),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE preinventario_sesiones
            SET estado = 'rechazada', aprobado_por = %s,
                fecha_aprobacion = NOW(), notas_aprobacion = %s
            WHERE id = %s AND estado = 'cerrada'
            RETURNING id
        """, (user["nombre"], body.motivo or None, sesion_id))
        if not cur.fetchone():
            raise HTTPException(status_code=409, detail="La sesión debe estar cerrada para rechazar")
    return {"ok": True, "estado": "rechazada"}
