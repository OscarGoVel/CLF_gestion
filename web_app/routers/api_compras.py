# -*- coding: utf-8 -*-
"""
web_app/routers/api_compras.py
/api/compras — endpoints JSON para el SPA React.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/compras", tags=["api"])

POR_PAGINA = 25


class LineaIn(BaseModel):
    producto_id: int
    cantidad: float
    costo_unitario: float
    aplica_iva: bool = False
    cotizacion_id: Optional[int] = None


class CompraIn(BaseModel):
    proveedor_id: Optional[int] = None
    fecha_compra: str
    ticket_referencia: Optional[str] = None
    notas: Optional[str] = None
    factura_xml_id: Optional[int] = None
    lineas: List[LineaIn]


class InsumoIn(BaseModel):
    nombre: str
    unidad: str = "pza"
    cantidad: float
    costo: float


class PresupuestoIn(BaseModel):
    cotizacion_ids: List[int]
    insumos: List[InsumoIn] = []


def _generar_folio(cur, año: int) -> str:
    cur.execute("SELECT COUNT(*) FROM compras WHERE folio LIKE %s", (f"CMP-{año}-%",))
    n = cur.fetchone()[0] + 1
    return f"CMP-{año}-{n:04d}"


def _serial(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v

def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


@router.get("")
async def listar(
    q: str = Query(""),
    pagina: int = Query(1, ge=1),
    user: dict = Depends(get_usuario_api),
):
    from fastapi import HTTPException
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso")

    empresa_db = user["empresa_db"]
    where, params = [], []
    if q:
        where.append("(c.folio ILIKE %s OR p.nombre ILIKE %s OR c.ticket_referencia ILIKE %s)")
        like = f"%{q}%"
        params += [like, like, like]

    filtro = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (pagina - 1) * POR_PAGINA

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(f"""
            SELECT COUNT(DISTINCT c.id)
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            {filtro}
        """, params or None)
        total = cur.fetchone()[0]

        cur.execute(f"""
            SELECT c.id, c.folio, c.fecha_compra, c.total,
                   c.ticket_referencia,
                   COALESCE(p.nombre, '— sin proveedor —') AS proveedor,
                   COUNT(DISTINCT cd.id)  AS num_lineas,
                   COUNT(DISTINCT cdc.cotizacion_id) AS num_cotizaciones
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            LEFT JOIN compra_detalle cd ON cd.compra_id = c.id
            LEFT JOIN compra_detalle_cotizacion cdc ON cdc.compra_detalle_id = cd.id
            {filtro}
            GROUP BY c.id, p.nombre
            ORDER BY c.id DESC
            LIMIT {POR_PAGINA} OFFSET {offset}
        """, params or None)
        compras = _rows(cur)

    total_pags = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)
    return JSONResponse({"compras": compras, "total": total,
                         "pagina": pagina, "total_pags": total_pags})


@router.get("/presupuesto/faltantes")
async def presupuesto_faltantes(user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            """
            SELECT c.id, c.folio,
                   COALESCE(cl.nombre_comercial, '— sin cliente —') AS cliente,
                   c.fecha_entrega,
                   COUNT(cd.id) AS productos_faltantes
            FROM cotizaciones c
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            JOIN productos p ON p.id = cd.producto_id
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.estado = 'Programada'
              AND COALESCE(p.stock_actual, 0) < cd.cantidad
            GROUP BY c.id, c.folio, cl.nombre_comercial, c.fecha_entrega
            ORDER BY c.fecha_entrega ASC NULLS LAST
            """
        )
        cols = [d[0] for d in cur.description]
        pedidos = [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]
    return JSONResponse({"pedidos": pedidos})


@router.post("/presupuesto/pdf")
async def presupuesto_pdf(body: PresupuestoIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if not body.cotizacion_ids:
        raise HTTPException(status_code=400, detail="Seleccione al menos un pedido")
    from web_app.pdf_presupuesto_compra import generar_pdf_presupuesto_compra
    try:
        pdf_bytes = generar_pdf_presupuesto_compra(
            user["empresa_db"],
            body.cotizacion_ids,
            insumos=[i.model_dump() for i in body.insumos],
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    filename = f"PresupuestoCompra_{date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{compra_id}")
async def detalle(compra_id: int, user: dict = Depends(get_usuario_api)):
    from fastapi import HTTPException
    empresa_db = user["empresa_db"]

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT c.id, c.folio, c.fecha_compra, c.total, c.ticket_referencia,
                   c.notas, COALESCE(c.estado, 'Creada') AS estado,
                   COALESCE(p.nombre, '—') AS proveedor,
                   p.rfc AS proveedor_rfc,
                   f.serie, f.folio_factura, f.uuid, f.fecha AS fecha_factura
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            LEFT JOIN facturas f ON f.id = c.factura_xml_id
            WHERE c.id = %s
        """, (compra_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404)
        cols = [d[0] for d in cur.description]
        compra = {k: _serial(v) for k, v in zip(cols, row)}

        # Líneas de la compra
        cur.execute("""
            SELECT cd.id, p.codigo, p.nombre, p.unidad_medida,
                   cd.cantidad, cd.costo_unitario,
                   cd.cantidad * cd.costo_unitario AS importe,
                   COALESCE(cd.cantidad_recibida, 0) AS cantidad_recibida
            FROM compra_detalle cd
            LEFT JOIN productos p ON p.id = cd.producto_id
            WHERE cd.compra_id = %s
            ORDER BY cd.id
        """, (compra_id,))
        lineas = _rows(cur)

        # Asignaciones por línea: qué cotización recibe cuántas unidades
        if lineas:
            cur.execute("""
                SELECT cdc.compra_detalle_id,
                       cot.id   AS cot_id,
                       cot.folio,
                       cot.estado,
                       COALESCE(cl.nombre_comercial, '—') AS cliente,
                       cdc.cantidad
                FROM compra_detalle_cotizacion cdc
                JOIN cotizaciones cot ON cot.id = cdc.cotizacion_id
                LEFT JOIN clientes cl ON cl.id = cot.cliente_id
                WHERE cdc.compra_detalle_id = ANY(%s)
                ORDER BY cdc.compra_detalle_id, cot.id
            """, ([l["id"] for l in lineas],))
            asig_rows = _rows(cur)
        else:
            asig_rows = []

        asig_by_linea: dict = {}
        for a in asig_rows:
            asig_by_linea.setdefault(a["compra_detalle_id"], []).append({
                "cot_id":  a["cot_id"],
                "folio":   a["folio"],
                "estado":  a["estado"],
                "cliente": a["cliente"],
                "cantidad": _serial(a["cantidad"]),
            })

        for l in lineas:
            l["asignaciones"] = asig_by_linea.get(l["id"], [])

    return JSONResponse({"compra": compra, "lineas": lineas})


# ── POST /api/compras ─────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def crear_compra(body: CompraIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    if not body.lineas:
        raise HTTPException(status_code=400, detail="Debe incluir al menos una línea")

    empresa_db = user["empresa_db"]
    año = date.today().year

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        folio = _generar_folio(cur, año)

        subtotal_g = Decimal("0")
        iva_g = Decimal("0")
        detalle_rows = []

        for ln in body.lineas:
            cant = Decimal(str(ln.cantidad))
            costo_u = Decimal(str(ln.costo_unitario))
            sub = (cant * costo_u).quantize(Decimal("0.01"))
            iva = (sub * Decimal("0.16")).quantize(Decimal("0.01")) if ln.aplica_iva else Decimal("0")
            subtotal_g += sub
            iva_g += iva
            detalle_rows.append({
                "producto_id": ln.producto_id,
                "cantidad": cant,
                "costo_u": costo_u,
                "total": sub + iva,
                "cotizacion_id": ln.cotizacion_id,
            })

        total_g = subtotal_g + iva_g

        cur.execute("""
            INSERT INTO compras
              (folio, proveedor_id, fecha_compra, subtotal, iva, total,
               ticket_referencia, notas, factura_xml_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            folio, body.proveedor_id, body.fecha_compra,
            float(subtotal_g), float(iva_g), float(total_g),
            body.ticket_referencia or None, body.notas or None,
            body.factura_xml_id or None,
        ))
        compra_id = cur.lastrowid

        for row in detalle_rows:
            cur.execute("""
                INSERT INTO compra_detalle
                  (compra_id, producto_id, cantidad, costo_unitario, costo_total)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                compra_id, row["producto_id"],
                float(row["cantidad"]), float(row["costo_u"]), float(row["total"]),
            ))
            detalle_id = cur.lastrowid

            # Vincular a cotización si se proporcionó
            if row["cotizacion_id"] is not None:
                cur.execute("""
                    INSERT INTO compra_detalle_cotizacion
                      (compra_detalle_id, cotizacion_id, cantidad)
                    VALUES (%s, %s, %s)
                """, (detalle_id, row["cotizacion_id"], float(row["cantidad"])))

            # Stock y costo promedio ponderado — actualización atómica (sin lectura previa)
            cant  = float(row["cantidad"])
            costo = float(row["costo_u"])
            cur.execute(
                "SELECT COALESCE(stock_actual, 0) FROM productos WHERE id = %s",
                (row["producto_id"],),
            )
            stock_antes = float(cur.fetchone()[0])
            cur.execute("""
                UPDATE productos
                SET stock_actual   = COALESCE(stock_actual, 0) + %s,
                    costo_promedio = CASE
                        WHEN COALESCE(stock_actual, 0) + %s > 0
                        THEN (COALESCE(stock_actual, 0) * COALESCE(costo_promedio, 0) + %s * %s)
                             / (COALESCE(stock_actual, 0) + %s)
                        ELSE %s
                    END
                WHERE id = %s
                RETURNING stock_actual, costo_promedio
            """, (cant, cant, cant, costo, cant, costo, row["producto_id"]))
            stock_despues, nuevo_prom_raw = cur.fetchone()
            nuevo_prom = Decimal(str(nuevo_prom_raw or 0))

            # Verificar si precio_venta cubre el nuevo costo con margen mínimo (35%)
            _MARGEN_MIN = Decimal("0.35")
            cur.execute(
                "SELECT COALESCE(precio_venta, 0) FROM productos WHERE id = %s",
                (row["producto_id"],),
            )
            precio_venta_actual = Decimal(str(cur.fetchone()[0]))
            if precio_venta_actual < nuevo_prom * (1 + _MARGEN_MIN):
                cur.execute(
                    "UPDATE productos SET precio_desactualizado = TRUE WHERE id = %s",
                    (row["producto_id"],),
                )

            # Historial de costos de compra
            cur.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente, proveedor_id)
                VALUES (%s, %s, %s, %s, 'compra', %s)
            """, (
                row["producto_id"], float(row["costo_u"]),
                body.fecha_compra, f"Compra {folio}", body.proveedor_id,
            ))

            # Movimiento de stock
            cur.execute("""
                INSERT INTO movimientos_stock
                  (producto_id, tipo, motivo, cantidad,
                   stock_antes, stock_despues, referencia, usuario)
                VALUES (%s, 'entrada', 'compra', %s, %s, %s, %s, %s)
            """, (
                row["producto_id"], float(row["cantidad"]),
                stock_antes, stock_despues,
                folio, user.get("username", ""),
            ))

    return JSONResponse({"id": compra_id, "folio": folio}, status_code=201)


# ── PATCH /api/compras/{id}/recibir ──────────────────────────────────────────

class RecepcionLineaIn(BaseModel):
    linea_id: int
    cantidad_recibida: float


class RecepcionIn(BaseModel):
    lineas: List[RecepcionLineaIn]


@router.patch("/{compra_id}/recibir")
async def recibir(compra_id: int, body: RecepcionIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador", "Almacenista"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT folio, COALESCE(estado,'Creada') FROM compras WHERE id = %s", (compra_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Compra no encontrada")
        folio_compra, estado_actual = row
        if estado_actual == 'Recibida Completa':
            raise HTTPException(status_code=422, detail="La compra ya fue completamente recibida")

        for linea in body.lineas:
            if linea.cantidad_recibida <= 0:
                continue
            cur.execute("""
                SELECT cd.producto_id, cd.cantidad, cd.costo_unitario,
                       COALESCE(cd.cantidad_recibida, 0)
                FROM compra_detalle cd
                WHERE cd.id = %s AND cd.compra_id = %s
            """, (linea.linea_id, compra_id))
            det = cur.fetchone()
            if not det:
                continue
            prod_id, cant_ordenada, costo_unit, ya_recibido = det
            max_recibir = float(cant_ordenada) - float(ya_recibido)
            a_recibir = min(float(linea.cantidad_recibida), max_recibir)
            if a_recibir <= 0:
                continue

            cur.execute("""
                UPDATE compra_detalle
                   SET cantidad_recibida = COALESCE(cantidad_recibida, 0) + %s
                 WHERE id = %s
            """, (a_recibir, linea.linea_id))

            cur.execute("SELECT COALESCE(stock_actual, 0) FROM productos WHERE id = %s", (prod_id,))
            stock_antes = float(cur.fetchone()[0])
            costo = float(costo_unit)

            cur.execute("""
                UPDATE productos
                   SET stock_actual   = COALESCE(stock_actual, 0) + %s,
                       costo_promedio = CASE
                           WHEN COALESCE(stock_actual, 0) + %s > 0
                           THEN (COALESCE(stock_actual, 0) * COALESCE(costo_promedio, 0) + %s * %s)
                                / (COALESCE(stock_actual, 0) + %s)
                           ELSE %s
                       END
                 WHERE id = %s
                RETURNING stock_actual
            """, (a_recibir, a_recibir, a_recibir, costo, a_recibir, costo, prod_id))
            stock_despues = float(cur.fetchone()[0])

            cur.execute("""
                INSERT INTO movimientos_stock
                    (producto_id, tipo, motivo, cantidad,
                     stock_antes, stock_despues, referencia, usuario)
                VALUES (%s, 'entrada', 'recepcion_compra', %s, %s, %s, %s, %s)
            """, (prod_id, a_recibir, stock_antes, stock_despues,
                  folio_compra, user.get("username", "")))

        # Determinar nuevo estado de la compra
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE COALESCE(cantidad_recibida,0) < cantidad) AS pendientes
            FROM compra_detalle WHERE compra_id = %s
        """, (compra_id,))
        pendientes = cur.fetchone()[0]
        nuevo_estado = 'Recibida Completa' if pendientes == 0 else 'Recibida Parcial'
        cur.execute("UPDATE compras SET estado = %s WHERE id = %s", (nuevo_estado, compra_id))

    return JSONResponse({"ok": True, "estado": nuevo_estado})
