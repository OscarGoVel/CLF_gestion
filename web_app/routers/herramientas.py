# -*- coding: utf-8 -*-
"""
web_app/routers/herramientas.py
Herramientas de mantenimiento de datos — solo Administrador.
"""

from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual

router = APIRouter(prefix="/herramientas")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _solo_admin(user):
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo Administrador")


# ─────────────────────────────────────────────────────────────────────────────
# PÁGINA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    _solo_admin(user)
    return templates.TemplateResponse(
        request=request,
        name="herramientas/index.html",
        context={"user": user, "seccion": "herramientas"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# HERRAMIENTA 1: PREVIEW — cuántas entradas faltan en historial de precios
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/preview-backfill-precios", response_class=JSONResponse)
async def preview_backfill_precios(request: Request):
    user = get_usuario_actual(request)
    _solo_admin(user)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT COUNT(*) FROM compra_detalle cd
            JOIN compras c ON c.id = cd.compra_id
            WHERE cd.costo_unitario IS NOT NULL AND cd.costo_unitario > 0
              AND NOT EXISTS (
                  SELECT 1 FROM producto_precio_historial h
                  WHERE h.producto_id = cd.producto_id
                    AND h.fuente = 'compra'
                    AND h.motivo = 'Compra ' || c.folio
              )
        """)
        faltantes = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT cd.producto_id) FROM compra_detalle cd
            JOIN compras c ON c.id = cd.compra_id
            WHERE cd.costo_unitario IS NOT NULL AND cd.costo_unitario > 0
              AND NOT EXISTS (
                  SELECT 1 FROM producto_precio_historial h
                  WHERE h.producto_id = cd.producto_id
                    AND h.fuente = 'compra'
                    AND h.motivo = 'Compra ' || c.folio
              )
        """)
        productos_afectados = cur.fetchone()[0]

    return JSONResponse({"faltantes": faltantes, "productos": productos_afectados})


# ─────────────────────────────────────────────────────────────────────────────
# HERRAMIENTA 1: EJECUTAR — backfill historial de precios
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/backfill-precios", response_class=JSONResponse)
async def backfill_precios(request: Request):
    user = get_usuario_actual(request)
    _solo_admin(user)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO producto_precio_historial
                (producto_id, precio, fecha, motivo, fuente, proveedor_id)
            SELECT
                cd.producto_id,
                cd.costo_unitario,
                COALESCE(c.fecha_compra, CURRENT_DATE),
                'Compra ' || c.folio,
                'compra',
                c.proveedor_id
            FROM compra_detalle cd
            JOIN compras c ON c.id = cd.compra_id
            WHERE cd.costo_unitario IS NOT NULL AND cd.costo_unitario > 0
              AND NOT EXISTS (
                  SELECT 1 FROM producto_precio_historial h
                  WHERE h.producto_id = cd.producto_id
                    AND h.fuente = 'compra'
                    AND h.motivo = 'Compra ' || c.folio
              )
        """)
        insertados = cur.rowcount
    return JSONResponse({"ok": True, "insertados": insertados})


# ─────────────────────────────────────────────────────────────────────────────
# HERRAMIENTA 2: VERIFICAR STOCK
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/verificar-stock", response_class=JSONResponse)
async def verificar_stock(request: Request):
    user = get_usuario_actual(request)
    _solo_admin(user)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT p.id, p.codigo, p.nombre,
                   p.stock_actual AS registrado,
                   COALESCE(SUM(
                       CASE WHEN m.tipo = 'entrada' THEN m.cantidad
                            WHEN m.tipo = 'salida'  THEN -m.cantidad
                            ELSE 0 END
                   ), 0) AS calculado
            FROM productos p
            LEFT JOIN movimientos_stock m ON m.producto_id = p.id
            GROUP BY p.id, p.codigo, p.nombre, p.stock_actual
            HAVING ABS(p.stock_actual - COALESCE(SUM(
                CASE WHEN m.tipo = 'entrada' THEN m.cantidad
                     WHEN m.tipo = 'salida'  THEN -m.cantidad
                     ELSE 0 END
            ), 0)) > 0.01
            ORDER BY ABS(p.stock_actual - COALESCE(SUM(
                CASE WHEN m.tipo = 'entrada' THEN m.cantidad
                     WHEN m.tipo = 'salida'  THEN -m.cantidad
                     ELSE 0 END
            ), 0)) DESC
            LIMIT 50
        """)
        cols = [d[0] for d in cur.description]
        discrepancias = [dict(zip(cols, r)) for r in cur.fetchall()]
        for d in discrepancias:
            d["registrado"] = float(d["registrado"])
            d["calculado"]  = float(d["calculado"])
            d["diferencia"] = round(d["registrado"] - d["calculado"], 4)
    return JSONResponse({"discrepancias": discrepancias})


# ─────────────────────────────────────────────────────────────────────────────
# HERRAMIENTA 3: PREVIEW — costo promedio a recalcular
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/preview-costo-promedio", response_class=JSONResponse)
async def preview_costo_promedio(request: Request):
    user = get_usuario_actual(request)
    _solo_admin(user)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT p.id, p.codigo, p.nombre,
                   COALESCE(p.costo_promedio, 0) AS actual,
                   SUM(cd.cantidad * cd.costo_unitario) / NULLIF(SUM(cd.cantidad), 0) AS calculado,
                   COUNT(*) AS num_compras
            FROM productos p
            JOIN compra_detalle cd ON cd.producto_id = p.id
            WHERE cd.costo_unitario IS NOT NULL AND cd.costo_unitario > 0
            GROUP BY p.id, p.codigo, p.nombre, p.costo_promedio
            HAVING ABS(COALESCE(p.costo_promedio, 0) -
                       SUM(cd.cantidad * cd.costo_unitario) / NULLIF(SUM(cd.cantidad), 0)) > 0.01
            ORDER BY p.nombre
            LIMIT 50
        """)
        cols = [d[0] for d in cur.description]
        diferencias = [dict(zip(cols, r)) for r in cur.fetchall()]
        for d in diferencias:
            d["actual"]     = float(d["actual"])
            d["calculado"]  = round(float(d["calculado"]), 4)
            d["num_compras"] = int(d["num_compras"])
    return JSONResponse({"diferencias": diferencias})


# ─────────────────────────────────────────────────────────────────────────────
# HERRAMIENTA 3: EJECUTAR — recalcular costo promedio ponderado histórico
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/recalcular-costo-promedio", response_class=JSONResponse)
async def recalcular_costo_promedio(request: Request):
    user = get_usuario_actual(request)
    _solo_admin(user)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE productos p
            SET costo_promedio = sub.nuevo_prom
            FROM (
                SELECT cd.producto_id,
                       SUM(cd.cantidad * cd.costo_unitario) / NULLIF(SUM(cd.cantidad), 0) AS nuevo_prom
                FROM compra_detalle cd
                WHERE cd.costo_unitario IS NOT NULL AND cd.costo_unitario > 0
                GROUP BY cd.producto_id
            ) sub
            WHERE p.id = sub.producto_id
              AND ABS(COALESCE(p.costo_promedio, 0) - sub.nuevo_prom) > 0.01
        """)
        actualizados = cur.rowcount
    return JSONResponse({"ok": True, "actualizados": actualizados})
