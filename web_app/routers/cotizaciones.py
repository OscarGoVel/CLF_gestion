# -*- coding: utf-8 -*-
"""
web_app/routers/cotizaciones.py
Seccion de Cotizaciones: lista, detalle, cambio de estado, crear y editar.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual
from core.constants import ESTADOS_COTIZACION as ESTADOS, ESTADO_COLOR_CSS as ESTADO_COLOR, formato_folio

router = APIRouter(prefix="/cotizaciones")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

POR_PAGINA = 25


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generar_folio_en_tx(cur, año: int) -> str:
    """
    Genera el siguiente folio dentro de una transacción ya abierta.
    Usa pg_advisory_xact_lock para serializar generaciones concurrentes:
    el lock se libera automáticamente al hacer commit/rollback.
    """
    cur.execute("SELECT pg_advisory_xact_lock(hashtext('folio_cotizacion'))")
    cur.execute(
        """
        SELECT COALESCE(
            MAX(CAST(SPLIT_PART(folio, '-', 3) AS INTEGER)), 0
        ) + 1
        FROM cotizaciones
        WHERE folio LIKE %s
        """,
        (f"COT-{año}-%",),
    )
    return formato_folio(año, cur.fetchone()[0])


def _cargar_clientes(empresa_db: str) -> list:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre_comercial, tipo FROM clientes ORDER BY nombre_comercial"
        )
        return [{"id": r[0], "nombre": r[1], "tipo": r[2]} for r in cur.fetchall()]

def _dec_to_float(d: dict) -> dict:
    """Convierte Decimal → float para que Jinja2 pueda formatearlo."""
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


def _build_where(estado: str, buscar: str) -> tuple[str, list]:
    clauses, params = [], []
    if estado:
        clauses.append("c.estado = %s")
        params.append(estado)
    if buscar:
        clauses.append("(c.folio ILIKE %s OR COALESCE(cl.nombre_comercial,'') ILIKE %s)")
        params += [f"%{buscar}%", f"%{buscar}%"]
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _cargar_lista(empresa_db: str, estado: str, buscar: str, pagina: int) -> dict:
    where, params = _build_where(estado, buscar)
    offset = (pagina - 1) * POR_PAGINA

    sql = f"""
        SELECT c.id, c.folio, c.fecha,
               COALESCE(cl.nombre_comercial, '—') AS cliente,
               cl.tipo                             AS tipo_cliente,
               c.total, c.estado,
               c.orden_compra, c.numero_factura,
               COUNT(cd.id)                        AS num_productos
        FROM cotizaciones c
        LEFT JOIN clientes          cl ON cl.id = c.cliente_id
        LEFT JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
        {where}
        GROUP BY c.id, cl.nombre_comercial, cl.tipo
        ORDER BY c.fecha DESC, c.id DESC
        LIMIT {POR_PAGINA} OFFSET {offset}
    """
    count_sql = f"""
        SELECT COUNT(DISTINCT c.id)
        FROM cotizaciones c
        LEFT JOIN clientes cl ON cl.id = c.cliente_id
        {where}
    """

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(sql, params or None)
        cols = [d[0] for d in cur.description]
        rows = [_dec_to_float(dict(zip(cols, r))) for r in cur.fetchall()]

        cur.execute(count_sql, params or None)
        total = cur.fetchone()[0]

    return {"rows": rows, "total": total}


# ── Rutas ─────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def lista(
    request: Request,
    estado: str = "",
    buscar: str = "",
    pagina: int = 1,
):
    user = get_usuario_actual(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/")
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso a cotizaciones")

    data       = _cargar_lista(user["empresa_db"], estado, buscar, pagina)
    total_pags = max(1, (data["total"] + POR_PAGINA - 1) // POR_PAGINA)

    # Totales por estado para los chips del encabezado
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT estado, COUNT(*) FROM cotizaciones GROUP BY estado")
        conteo_estado = dict(cur.fetchall())

    ctx = {
        "user":          user,
        "cotizaciones":  data["rows"],
        "total":         data["total"],
        "estados":       ESTADOS,
        "estado_sel":    estado,
        "buscar":        buscar,
        "pagina":        pagina,
        "total_pags":    total_pags,
        "estado_color":  ESTADO_COLOR,
        "conteo_estado": conteo_estado,
    }

    # HTMX: devuelve solo el fragmento de la tabla
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="cotizaciones/_tabla.html", context=ctx
        )

    return templates.TemplateResponse(
        request=request, name="cotizaciones/lista.html", context=ctx
    )


# ── Rutas específicas (deben ir ANTES de /{cot_id}) ──────────────────────────

@router.get("/buscar-producto", response_class=HTMLResponse)
async def buscar_producto(request: Request, q: str = ""):
    user = get_usuario_actual(request)
    if not user or len(q) < 2:
        return HTMLResponse("")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            """
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   p.precio_base AS costo_base,
                   COALESCE(
                       (SELECT MAX(h.precio)
                        FROM producto_precio_historial h
                        WHERE h.producto_id = p.id),
                       p.precio_base, 0
                   ) AS precio,
                   p.stock_actual, p.aplica_iva
            FROM productos p
            WHERE p.nombre ILIKE %s OR p.codigo ILIKE %s
            ORDER BY p.nombre LIMIT 8
            """,
            (f"%{q}%", f"%{q}%"),
        )
        cols = [d[0] for d in cur.description]
        resultados = [
            {k: float(v) if isinstance(v, Decimal) else v for k, v in dict(zip(cols, r)).items()}
            for r in cur.fetchall()
        ]

    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/_prod_sugerencias.html",
        context={"resultados": resultados, "user": user},
    )


@router.get("/{cot_id}/preview", response_class=HTMLResponse)
async def preview(request: Request, cot_id: int):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT c.*,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cl.tipo AS tipo_cliente
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = %s
        """, (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404)
        cot = _dec_to_float(dict(zip([d[0] for d in cur.description], row)))

        cur.execute("""
            SELECT p.nombre, p.unidad_medida, cd.cantidad, cd.precio_unitario, cd.total
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
        """, (cot_id,))
        dcols     = [d[0] for d in cur.description]
        productos = [_dec_to_float(dict(zip(dcols, r))) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/_preview.html",
        context={
            "user": user,
            "cot": cot,
            "productos": productos,
            "estado_color": ESTADO_COLOR,
        },
    )


@router.get("/nueva", response_class=HTMLResponse)
async def nueva(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    clientes = _cargar_clientes(user["empresa_db"])
    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/form.html",
        context={
            "user":                user,
            "cot":                 None,
            "productos_existentes": [],
            "clientes":            clientes,
            "hoy":                 date.today().isoformat(),
            "titulo":              "Nueva Cotización",
        },
    )


@router.post("", response_class=HTMLResponse)
async def crear(
    request:        Request,
    cliente_id:     int = Form(...),
    comprador_id:   int = Form(0),
    fecha:          str = Form(...),
    orden_compra:   str = Form(""),
    notas:          str = Form(""),
    utilidad_pct:   float = Form(0.0),
    productos_json: str = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403)

    try:
        prods = json.loads(productos_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Datos de productos inválidos")
    if not prods:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un producto")

    subtotal_global = Decimal("0")
    iva_global      = Decimal("0")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        folio = _generar_folio_en_tx(cur, date.today().year)

        detalle_rows = []
        for p in prods:
            cant   = Decimal(str(p["cantidad"]))
            precio = Decimal(str(p["precio_unitario"]))
            sub    = (cant * precio).quantize(Decimal("0.01"))
            es_libre = not p.get("producto_id")

            if es_libre:
                prod_iva    = bool(p.get("aplica_iva", False))
                costo_snap  = 0.0
                tiene_stock = True
            else:
                cur.execute(
                    "SELECT precio_base, aplica_iva, COALESCE(stock_actual,0) >= %s "
                    "FROM productos WHERE id = %s",
                    (float(cant), p["producto_id"]),
                )
                pb_row = cur.fetchone()
                costo_snap  = float(pb_row[0]) if pb_row else 0.0
                prod_iva    = bool(pb_row[1]) if pb_row else False
                tiene_stock = bool(pb_row[2]) if pb_row else False

            p_iva = (sub * Decimal("0.16")).quantize(Decimal("0.01")) if prod_iva else Decimal("0")
            p_tot = (sub + p_iva).quantize(Decimal("0.01"))

            subtotal_global += sub
            iva_global      += p_iva
            detalle_rows.append((
                p.get("producto_id") or None,
                cant, precio, sub, p_iva, p_tot,
                tiene_stock, costo_snap,
                p.get("descripcion_libre", "") if es_libre else None,
                es_libre,
            ))

        total_global = (subtotal_global + iva_global).quantize(Decimal("0.01"))
        hay_iva      = iva_global > 0

        cur.execute(
            """
            INSERT INTO cotizaciones
              (folio, fecha, cliente_id, comprador_id, subtotal, iva, total,
               notas, estado, aplica_iva, orden_compra, utilidad_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pendiente', %s, %s, %s)
            """,
            (folio, fecha, cliente_id, comprador_id or None,
             float(subtotal_global), float(iva_global), float(total_global),
             notas or None, 1 if hay_iva else 0,
             orden_compra or None, utilidad_pct),
        )
        cot_id = cur.lastrowid

        for (prod_id, cant, precio, sub, p_iva, p_tot,
             tiene_stock, costo_snap, desc_libre, es_libre) in detalle_rows:
            cur.execute(
                """
                INSERT INTO cotizacion_detalle
                  (cotizacion_id, producto_id, descripcion_libre, pendiente_catalogo,
                   cantidad, precio_unitario, subtotal, iva, total, tiene_stock, costo_snapshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (cot_id, prod_id, desc_libre, es_libre,
                 float(cant), float(precio),
                 float(sub), float(p_iva), float(p_tot),
                 1 if tiene_stock else 0, costo_snap),
            )

    return RedirectResponse(f"/cotizaciones/{cot_id}", status_code=303)


# ── Detalle cotización ────────────────────────────────────────────────────────

@router.get("/{cot_id}", response_class=HTMLResponse)
async def detalle(request: Request, cot_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso a cotizaciones")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT c.*,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cl.tipo      AS tipo_cliente,
                   cl.rfc       AS cliente_rfc,
                   cl.direccion AS cliente_dir,
                   cl.contacto  AS cliente_contacto,
                   cl.email     AS cliente_email,
                   cl.telefono  AS cliente_tel,
                   comp.nombre  AS comprador_nombre,
                   comp.cargo   AS comprador_cargo,
                   comp.telefono AS comprador_tel,
                   comp.email   AS comprador_email
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            LEFT JOIN compradores comp ON comp.id = c.comprador_id
            WHERE c.id = %s
        """, (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
        cot = _dec_to_float(dict(zip([d[0] for d in cur.description], row)))

        cur.execute("""
            SELECT cd.id,
                   cd.producto_id,
                   COALESCE(p.codigo, '') AS codigo,
                   COALESCE(p.nombre, cd.descripcion_libre, '') AS nombre,
                   COALESCE(p.unidad_medida, '') AS unidad_medida,
                   cd.cantidad, cd.precio_unitario,
                   cd.subtotal, cd.iva, cd.total,
                   COALESCE(p.aplica_iva, 0) AS aplica_iva,
                   cd.descripcion_libre,
                   COALESCE(cd.pendiente_catalogo, FALSE) AS pendiente_catalogo
            FROM cotizacion_detalle cd
            LEFT JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
        """, (cot_id,))
        dcols     = [d[0] for d in cur.description]
        productos = [_dec_to_float(dict(zip(dcols, r))) for r in cur.fetchall()]

        cur.execute("""
            SELECT ep.id, ep.producto_id, ep.cantidad_entregada,
                   ep.fecha_entrega, ep.notas, ep.usuario,
                   p.nombre AS producto_nombre, p.unidad_medida
            FROM entregas_parciales ep
            JOIN productos p ON p.id = ep.producto_id
            WHERE ep.cotizacion_id = %s
            ORDER BY ep.fecha_entrega, ep.id
        """, (cot_id,))
        ecols    = [d[0] for d in cur.description]
        entregas = [_dec_to_float(dict(zip(ecols, r))) for r in cur.fetchall()]

        # Presupuesto de compra: precio mínimo histórico + proveedor por producto
        cur.execute("""
            SELECT cd.producto_id,
                   p.nombre,
                   p.unidad_medida,
                   cd.cantidad,
                   cd.precio_unitario AS precio_venta,
                   min_h.precio      AS precio_min_compra,
                   prov.id           AS proveedor_id,
                   prov.nombre       AS proveedor_nombre
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            LEFT JOIN LATERAL (
                SELECT h.precio, h.proveedor_id
                FROM producto_precio_historial h
                WHERE h.producto_id = cd.producto_id
                ORDER BY h.precio ASC
                LIMIT 1
            ) min_h ON true
            LEFT JOIN proveedores prov ON prov.id = min_h.proveedor_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
        """, (cot_id,))
        pcols      = [d[0] for d in cur.description]
        presupuesto = [_dec_to_float(dict(zip(pcols, r))) for r in cur.fetchall()]

        # Costo real: promedio ponderado de compras vinculadas por producto
        cur.execute("""
            SELECT cd.producto_id,
                   AVG(comp.costo_unitario) AS costo_real_avg
            FROM compra_detalle_cotizacion cdc
            JOIN compra_detalle comp ON comp.id = cdc.compra_detalle_id
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = cdc.cotizacion_id
                                       AND comp.producto_id = cd.producto_id
            WHERE cdc.cotizacion_id = %s
            GROUP BY cd.producto_id
        """, (cot_id,))
        costos_reales = {r[0]: float(r[1]) for r in cur.fetchall() if r[1] is not None}

    # Calcular cantidad ya entregada por producto
    entregado_por_prod = {}
    for e in entregas:
        pid = e["producto_id"]
        entregado_por_prod[pid] = entregado_por_prod.get(pid, 0) + (e["cantidad_entregada"] or 0)

    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/detalle.html",
        context={
            "user":               user,
            "cot":                cot,
            "productos":          productos,
            "entregas":           entregas,
            "entregado_por_prod": entregado_por_prod,
            "presupuesto":        presupuesto,
            "costos_reales":      costos_reales,
            "estados":            ESTADOS,
            "estado_color":       ESTADO_COLOR,
            "hoy":                date.today().isoformat(),
            "request":            request,
        },
    )


# ── Descargar PDF ────────────────────────────────────────────────────────────

@router.get("/{cot_id}/pdf")
async def descargar_pdf(request: Request, cot_id: int):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)

    try:
        from web_app.pdf_cotizacion import generar_pdf_cotizacion
        pdf_bytes = generar_pdf_cotizacion(user["empresa_db"], cot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {e}")

    # Obtener folio para el nombre del archivo
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT folio FROM cotizaciones WHERE id = %s", (cot_id,))
        row = cur.fetchone()
    folio = row[0] if row else f"COT-{cot_id}"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Cotizacion_{folio}.pdf"'},
    )


# ── Editar cotización ─────────────────────────────────────────────────────────

@router.get("/{cot_id}/editar", response_class=HTMLResponse)
async def editar_form(request: Request, cot_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM cotizaciones WHERE id = %s", (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        cot = _dec_to_float(dict(zip([d[0] for d in cur.description], row)))

        if cot["estado"] in ("Entregada", "Pagada", "Cancelada"):
            raise HTTPException(
                status_code=400,
                detail=f"No se puede editar una cotización en estado '{cot['estado']}'",
            )

        cur.execute(
            """
            SELECT cd.producto_id,
                   COALESCE(p.codigo, '') AS codigo,
                   COALESCE(p.nombre, cd.descripcion_libre, '') AS nombre,
                   COALESCE(p.unidad_medida, '') AS unidad_medida,
                   cd.cantidad, cd.precio_unitario,
                   COALESCE(cd.costo_snapshot, p.precio_base, 0) AS costo_base,
                   COALESCE(p.aplica_iva, 0) AS aplica_iva,
                   COALESCE(p.stock_actual, 0) AS stock_actual,
                   cd.descripcion_libre,
                   COALESCE(cd.pendiente_catalogo, FALSE) AS pendiente_catalogo
            FROM cotizacion_detalle cd
            LEFT JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
            """,
            (cot_id,),
        )
        dcols = [d[0] for d in cur.description]
        productos_existentes = [
            _dec_to_float(dict(zip(dcols, r))) for r in cur.fetchall()
        ]

        # Nombre del comprador actual para pre-poblar el dropdown
        if cot.get("comprador_id"):
            cur.execute("SELECT nombre FROM compradores WHERE id = %s", (cot["comprador_id"],))
            cr = cur.fetchone()
            cot["comprador_nombre"] = cr[0] if cr else None

    clientes = _cargar_clientes(user["empresa_db"])
    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/form.html",
        context={
            "user":                user,
            "cot":                 cot,
            "productos_existentes": productos_existentes,
            "clientes":            clientes,
            "hoy":                 date.today().isoformat(),
            "titulo":              f"Editar {cot['folio']}",
            "utilidad_pct":        cot.get("utilidad_pct") or 0,
        },
    )


@router.post("/{cot_id}/editar", response_class=HTMLResponse)
async def editar(
    request:        Request,
    cot_id:         int,
    cliente_id:     int = Form(...),
    comprador_id:   int = Form(0),
    fecha:          str = Form(...),
    orden_compra:   str = Form(""),
    notas:          str = Form(""),
    utilidad_pct:   float = Form(0.0),
    productos_json: str = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403)

    try:
        prods = json.loads(productos_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Datos de productos inválidos")
    if not prods:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un producto")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT estado FROM cotizaciones WHERE id = %s", (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404)
        if row[0] in ("Entregada", "Pagada", "Cancelada"):
            raise HTTPException(
                status_code=400,
                detail=f"No se puede editar en estado '{row[0]}'",
            )

        subtotal_global = Decimal("0")
        iva_global      = Decimal("0")
        detalle_rows    = []

        for p in prods:
            cant   = Decimal(str(p["cantidad"]))
            precio = Decimal(str(p["precio_unitario"]))
            sub    = (cant * precio).quantize(Decimal("0.01"))
            es_libre = not p.get("producto_id")

            if es_libre:
                prod_iva    = bool(p.get("aplica_iva", False))
                costo_snap  = 0.0
                tiene_stock = True
            else:
                cur.execute(
                    "SELECT precio_base, aplica_iva, COALESCE(stock_actual,0) >= %s "
                    "FROM productos WHERE id = %s",
                    (float(cant), p["producto_id"]),
                )
                pb_row = cur.fetchone()
                costo_snap  = float(pb_row[0]) if pb_row else 0.0
                prod_iva    = bool(pb_row[1]) if pb_row else False
                tiene_stock = bool(pb_row[2]) if pb_row else False

            p_iva = (sub * Decimal("0.16")).quantize(Decimal("0.01")) if prod_iva else Decimal("0")
            p_tot = (sub + p_iva).quantize(Decimal("0.01"))

            subtotal_global += sub
            iva_global      += p_iva
            detalle_rows.append((
                p.get("producto_id") or None,
                cant, precio, sub, p_iva, p_tot,
                tiene_stock, costo_snap,
                p.get("descripcion_libre", "") if es_libre else None,
                es_libre,
            ))

        total_global = (subtotal_global + iva_global).quantize(Decimal("0.01"))
        hay_iva      = iva_global > 0

        cur.execute(
            """
            UPDATE cotizaciones
            SET cliente_id = %s, comprador_id = %s, fecha = %s,
                orden_compra = %s, notas = %s,
                aplica_iva = %s, subtotal = %s, iva = %s, total = %s,
                utilidad_pct = %s
            WHERE id = %s
            """,
            (cliente_id, comprador_id or None, fecha,
             orden_compra or None, notas or None,
             1 if hay_iva else 0,
             float(subtotal_global), float(iva_global), float(total_global),
             utilidad_pct, cot_id),
        )

        cur.execute(
            "DELETE FROM cotizacion_detalle WHERE cotizacion_id = %s", (cot_id,)
        )

        for (prod_id, cant, precio, sub, p_iva, p_tot,
             tiene_stock, costo_snap, desc_libre, es_libre) in detalle_rows:
            cur.execute(
                """
                INSERT INTO cotizacion_detalle
                  (cotizacion_id, producto_id, descripcion_libre, pendiente_catalogo,
                   cantidad, precio_unitario, subtotal, iva, total, tiene_stock, costo_snapshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (cot_id, prod_id, desc_libre, es_libre,
                 float(cant), float(precio),
                 float(sub), float(p_iva), float(p_tot),
                 1 if tiene_stock else 0, costo_snap),
            )

    return RedirectResponse(f"/cotizaciones/{cot_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{cot_id}/estado", response_class=HTMLResponse)
async def cambiar_estado(
    request: Request,
    cot_id: int,
    nuevo_estado: str = Form(...),
    fecha_entrega: str = Form(""),
    fecha_pago: str = Form(""),
    monto_pagado: str = Form(""),
    numero_factura: str = Form(""),
    orden_compra: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso para cambiar estado")
    if nuevo_estado == "Pagada" and user.get("rol") != "Administrador":
        raise HTTPException(
            status_code=403,
            detail="Solo el Administrador puede marcar una cotización como Pagada.",
        )
    if nuevo_estado not in ESTADOS:
        raise HTTPException(status_code=400, detail="Estado no valido")

    def _date(s): return s.strip() or None
    def _float(s):
        try: return float(s.strip()) if s.strip() else None
        except ValueError: return None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE cotizaciones SET
                estado          = %s,
                fecha_entrega   = COALESCE(%s::date,   fecha_entrega),
                fecha_pago      = COALESCE(%s::date,   fecha_pago),
                monto_pagado    = COALESCE(%s::numeric, monto_pagado),
                numero_factura  = COALESCE(NULLIF(%s,''), numero_factura),
                orden_compra    = COALESCE(NULLIF(%s,''), orden_compra)
            WHERE id = %s
        """, (
            nuevo_estado,
            _date(fecha_entrega), _date(fecha_pago),
            _float(monto_pagado),
            numero_factura.strip(), orden_compra.strip(),
            cot_id,
        ))

    # Invalidar caché del dashboard (los KPIs habrán cambiado)
    from web_app.cache import cache as _cache
    _cache.invalidar(f"dashboard:{user['empresa_db']}")

    from fastapi.responses import Response as _Resp
    r = _Resp(status_code=200, content="")
    r.headers["HX-Redirect"] = f"/cotizaciones/{cot_id}"
    return r


@router.post("/{cot_id}/entregas", response_class=HTMLResponse)
async def registrar_entrega(
    request: Request,
    cot_id: int,
    producto_id: int = Form(...),
    cantidad_entregada: str = Form(...),
    fecha_entrega: str = Form(...),
    notas: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    try:
        cantidad = float(cantidad_entregada)
        if cantidad <= 0:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="Cantidad inválida")

    aviso = None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT folio FROM cotizaciones WHERE id = %s", (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        folio = row[0]

        cur.execute("""
            INSERT INTO entregas_parciales
                (cotizacion_id, producto_id, cantidad_entregada, fecha_entrega, notas, usuario)
            VALUES (%s, %s, %s, %s::date, %s, %s)
        """, (
            cot_id, producto_id, cantidad,
            fecha_entrega, notas.strip() or None,
            user.get("username"),
        ))

        # ── Movimiento de stock ───────────────────────────────────────────────
        # Solo descontar del stock general si NO hay compra vinculada específicamente
        cur.execute("""
            SELECT 1 FROM compra_detalle_cotizacion cdc
            JOIN compra_detalle cd ON cd.id = cdc.compra_detalle_id
            WHERE cdc.cotizacion_id = %s AND cd.producto_id = %s
            LIMIT 1
        """, (cot_id, producto_id))
        tiene_compra = cur.fetchone() is not None

        if not tiene_compra:
            cur.execute(
                "SELECT COALESCE(stock_actual, 0) FROM productos WHERE id = %s",
                (producto_id,),
            )
            stock_row = cur.fetchone()
            stock_actual = float(stock_row[0]) if stock_row else 0.0

            if stock_actual <= 0:
                aviso = "sin_stock"
            else:
                a_descontar = min(cantidad, stock_actual)
                stock_nuevo = stock_actual - a_descontar
                cur.execute(
                    "UPDATE productos SET stock_actual = %s WHERE id = %s",
                    (stock_nuevo, producto_id),
                )
                cur.execute("""
                    INSERT INTO movimientos_stock
                        (producto_id, tipo, motivo, cantidad, stock_antes, stock_despues,
                         referencia, notas, fecha)
                    VALUES (%s, 'salida', 'Entrega cotización', %s, %s, %s, %s, %s, %s::date)
                """, (
                    producto_id, a_descontar, stock_actual, stock_nuevo,
                    folio, f"Entrega parcial cotización {folio}",
                    fecha_entrega,
                ))
                if a_descontar < cantidad:
                    aviso = "stock_parcial"

    from web_app import audit as _audit
    _audit.registrar(
        "entrega_parcial",
        username=user.get("username"),
        detalle=f"cotizacion_id={cot_id} producto_id={producto_id} cantidad={cantidad}",
        ip=request.client.host if request.client else None,
    )

    from fastapi.responses import Response as _Resp
    redirect_url = f"/cotizaciones/{cot_id}"
    if aviso:
        redirect_url += f"?aviso={aviso}"
    r = _Resp(status_code=200, content="")
    r.headers["HX-Redirect"] = redirect_url
    return r


# ── Seguimiento de cotización ─────────────────────────────────────────────────

# Etapas del seguimiento (igual que desktop)
_ETAPAS_SEG = [
    ("Orden de Compra",     "📋", "text-blue-800",   "bg-blue-50",   "border-blue-300"),
    ("Entregada",           "🚚", "text-green-800",  "bg-green-50",  "border-green-300"),
    ("Facturada",           "🧾", "text-cyan-800",   "bg-cyan-50",   "border-cyan-300"),
    ("Complemento de Pago", "💳", "text-amber-800",  "bg-amber-50",  "border-amber-300"),
    ("Pagada",              "✅", "text-purple-800", "bg-purple-50", "border-purple-300"),
]


@router.get("/{cot_id}/seguimiento", response_class=HTMLResponse)
async def ver_seguimiento(request: Request, cot_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT c.id, c.folio, c.fecha, c.estado, c.total,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   c.orden_compra, c.numero_factura, c.fecha_pago, c.monto_pagado
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = %s
        """, (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        cols = [d[0] for d in cur.description]
        cot = _dec_to_float(dict(zip(cols, row)))

        # Etapas guardadas
        cur.execute("""
            SELECT etapa, completada, referencia, fecha_etapa, notas
            FROM seguimiento_etapas
            WHERE cotizacion_id = %s
        """, (cot_id,))
        etapas_db = {r[0]: {
            "completada": bool(r[1]),
            "referencia": r[2] or "",
            "fecha_etapa": str(r[3]) if r[3] else "",
            "notas": r[4] or "",
        } for r in cur.fetchall()}

        # Facturas de venta vinculadas
        cur.execute("""
            SELECT f.id, f.uuid, f.serie, f.folio_factura, f.fecha, f.total,
                   f.nombre_receptor
            FROM factura_cotizaciones fc
            JOIN facturas f ON f.id = fc.factura_id
            WHERE fc.cotizacion_id = %s
            ORDER BY f.fecha DESC
        """, (cot_id,))
        fcols = [d[0] for d in cur.description]
        facturas_vinculadas = [_dec_to_float(dict(zip(fcols, r))) for r in cur.fetchall()]

        # Compras vinculadas (facturas de compra)
        cur.execute("""
            SELECT DISTINCT comp.id, f.uuid, f.serie, f.folio_factura, f.fecha,
                            comp.total, f.nombre_emisor
            FROM compra_detalle_cotizacion cdc
            JOIN compra_detalle cd ON cd.id = cdc.compra_detalle_id
            JOIN compras comp ON comp.id = cd.compra_id
            LEFT JOIN facturas f ON f.id = comp.factura_xml_id
            WHERE cdc.cotizacion_id = %s
            ORDER BY f.fecha DESC
        """, (cot_id,))
        ccols = [d[0] for d in cur.description]
        compras_vinculadas = [_dec_to_float(dict(zip(ccols, r))) for r in cur.fetchall()]

    # Construir lista de etapas con datos guardados
    etapas = []
    for nombre, icono, color_txt, color_bg, color_border in _ETAPAS_SEG:
        d = etapas_db.get(nombre, {})
        etapas.append({
            "nombre":       nombre,
            "icono":        icono,
            "color_txt":    color_txt,
            "color_bg":     color_bg,
            "color_border": color_border,
            "completada":   d.get("completada", False),
            "referencia":   d.get("referencia", ""),
            "fecha_etapa":  d.get("fecha_etapa", ""),
            "notas":        d.get("notas", ""),
        })

    completadas = sum(1 for e in etapas if e["completada"])

    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/seguimiento.html",
        context={
            "user":               user,
            "cot":                cot,
            "etapas":             etapas,
            "completadas":        completadas,
            "total_etapas":       len(_ETAPAS_SEG),
            "facturas_vinculadas": facturas_vinculadas,
            "compras_vinculadas": compras_vinculadas,
            "estado_color":       ESTADO_COLOR,
            "hoy":                date.today().isoformat(),
        },
    )


@router.post("/{cot_id}/seguimiento", response_class=HTMLResponse)
async def guardar_etapa_seguimiento(
    request: Request,
    cot_id: int,
    etapa_nombre: str = Form(...),
    completada: str = Form(""),
    referencia: str = Form(""),
    fecha_etapa: str = Form(""),
    notas: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    etapas_validas = [e[0] for e in _ETAPAS_SEG]
    if etapa_nombre not in etapas_validas:
        raise HTTPException(status_code=400, detail="Etapa no válida")

    es_completada = completada.lower() in ("1", "true", "on", "yes")
    ref = referencia.strip() or None
    fecha = fecha_etapa.strip() or None
    nota = notas.strip() or None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id FROM cotizaciones WHERE id = %s", (cot_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404)

        # UPSERT en seguimiento_etapas
        cur.execute("""
            INSERT INTO seguimiento_etapas
                (cotizacion_id, etapa, completada, referencia, fecha_etapa, notas)
            VALUES (%s, %s, %s, %s, %s::date, %s)
            ON CONFLICT (cotizacion_id, etapa) DO UPDATE SET
                completada  = EXCLUDED.completada,
                referencia  = EXCLUDED.referencia,
                fecha_etapa = EXCLUDED.fecha_etapa,
                notas       = EXCLUDED.notas
        """, (cot_id, etapa_nombre, 1 if es_completada else 0, ref, fecha, nota))

        # Sincronizar campos en cotizaciones
        if etapa_nombre == "Orden de Compra" and es_completada:
            update_parts, update_vals = [], []
            if ref:
                update_parts.append("orden_compra = %s"); update_vals.append(ref)
            if fecha:
                update_parts.append("fecha_orden_compra = %s::date"); update_vals.append(fecha)
            if update_parts:
                update_vals.append(cot_id)
                cur.execute(
                    f"UPDATE cotizaciones SET {', '.join(update_parts)} WHERE id = %s",
                    update_vals,
                )
        elif etapa_nombre == "Facturada" and es_completada:
            update_parts, update_vals = [], []
            if ref:
                update_parts.append("numero_factura = %s"); update_vals.append(ref)
            if fecha:
                update_parts.append("fecha_factura = %s::date"); update_vals.append(fecha)
            if update_parts:
                update_vals.append(cot_id)
                cur.execute(
                    f"UPDATE cotizaciones SET {', '.join(update_parts)} WHERE id = %s",
                    update_vals,
                )
        elif etapa_nombre == "Pagada" and es_completada:
            update_parts, update_vals = ["estado = 'Pagada'"], []
            if fecha:
                update_parts.append("fecha_pago = %s::date"); update_vals.append(fecha)
            if ref:
                try:
                    monto = float(ref)
                    update_parts.append("monto_pagado = %s"); update_vals.append(monto)
                except ValueError:
                    pass
            update_vals.append(cot_id)
            cur.execute(
                f"UPDATE cotizaciones SET {', '.join(update_parts)} WHERE id = %s",
                update_vals,
            )
            # Invalidar caché al cambiar estado
            from web_app.cache import cache as _cache
            _cache.invalidar(f"dashboard:{user['empresa_db']}")

    from fastapi.responses import Response as _Resp
    r = _Resp(status_code=200, content="")
    r.headers["HX-Redirect"] = f"/cotizaciones/{cot_id}/seguimiento"
    return r


# ── Selector de facturas disponibles (panel HTMX desde seguimiento) ──────────

@router.get("/{cot_id}/selector-facturas", response_class=HTMLResponse)
async def selector_facturas(
    request: Request,
    cot_id: int,
    q: str = "",
):
    """Retorna panel de búsqueda de facturas disponibles para vincular a esta cotización."""
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)

    q = q.strip()
    params: list = [cot_id]
    buscar_clause = ""
    if q:
        buscar_clause = """
            AND (f.uuid ILIKE %s
              OR CONCAT(COALESCE(f.serie,''), COALESCE(f.folio_factura,'')) ILIKE %s
              OR COALESCE(f.nombre_receptor,'') ILIKE %s
              OR COALESCE(f.nombre_emisor,'') ILIKE %s)
        """
        params += [f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"]

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT f.id,
                   COALESCE(f.serie,'') || COALESCE(f.folio_factura,'') AS folio_fac,
                   f.uuid, f.fecha, f.total, f.tipo,
                   f.nombre_emisor, f.nombre_receptor,
                   f.rfc_emisor, f.rfc_receptor
            FROM facturas f
            WHERE f.id NOT IN (
                SELECT fc.factura_id FROM factura_cotizaciones fc
                WHERE fc.cotizacion_id = %s
            )
            {buscar_clause}
            ORDER BY f.fecha DESC, f.id DESC
            LIMIT 50
        """, params)
        fcols = [d[0] for d in cur.description]
        facturas = [_dec_to_float(dict(zip(fcols, r))) for r in cur.fetchall()]

        # Conceptos de las facturas (líneas del XML)
        if facturas:
            fac_ids = [f["id"] for f in facturas]
            cur.execute("""
                SELECT fc.factura_id, fc.descripcion, fc.no_identificacion,
                       fc.cantidad, fc.unidad AS unidad_medida, fc.valor_unitario, fc.importe
                FROM factura_conceptos fc
                WHERE fc.factura_id = ANY(%s)
                ORDER BY fc.factura_id, fc.id
            """, (fac_ids,))
            ccols = [d[0] for d in cur.description]
            conceptos_raw = [_dec_to_float(dict(zip(ccols, r))) for r in cur.fetchall()]
        else:
            conceptos_raw = []

    from collections import defaultdict
    conceptos_por_fac: dict = defaultdict(list)
    for c in conceptos_raw:
        conceptos_por_fac[c["factura_id"]].append(c)

    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/_selector_facturas.html",
        context={
            "user":               user,
            "cot_id":             cot_id,
            "facturas":           facturas,
            "conceptos_por_fac":  dict(conceptos_por_fac),
            "q":                  q,
        },
    )


# ── Vincular factura de venta a cotización ────────────────────────────────────

@router.post("/{cot_id}/vincular-factura", response_class=HTMLResponse)
async def vincular_factura(
    request: Request,
    cot_id: int,
    factura_ref: str = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    ref = factura_ref.strip()
    if not ref:
        raise HTTPException(status_code=400, detail="Referencia de factura requerida")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id FROM cotizaciones WHERE id = %s", (cot_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404)

        # Buscar factura por UUID o por folio (serie+folio_factura)
        cur.execute("""
            SELECT id FROM facturas
            WHERE uuid ILIKE %s
               OR CONCAT(COALESCE(serie,''), folio_factura::text) ILIKE %s
            LIMIT 1
        """, (ref, ref))
        fac_row = cur.fetchone()
        if not fac_row:
            raise HTTPException(status_code=404, detail="Factura no encontrada")

        factura_id = fac_row[0]
        cur.execute("""
            INSERT INTO factura_cotizaciones (factura_id, cotizacion_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (factura_id, cot_id))

    from fastapi.responses import Response as _Resp
    r = _Resp(status_code=200, content="")
    r.headers["HX-Redirect"] = f"/cotizaciones/{cot_id}/seguimiento"
    return r


# ── Análisis de costos por cotización ────────────────────────────────────────

@router.get("/{cot_id}/costos", response_class=HTMLResponse)
async def ver_costos_cotizacion(request: Request, cot_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT c.id, c.folio, c.fecha, c.estado, c.subtotal, c.iva, c.total,
                   COALESCE(cl.nombre_comercial, '—') AS cliente
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = %s
        """, (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        cols = [d[0] for d in cur.description]
        cot = _dec_to_float(dict(zip(cols, row)))

        cur.execute("""
            SELECT cd.id, cd.producto_id, p.nombre, p.unidad_medida,
                   cd.cantidad, cd.precio_unitario, cd.costo_snapshot
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
        """, (cot_id,))
        dcols = [d[0] for d in cur.description]
        lineas = [_dec_to_float(dict(zip(dcols, r))) for r in cur.fetchall()]

        cur.execute("""
            SELECT comp.producto_id, AVG(comp.costo_unitario) AS costo_real_avg
            FROM compra_detalle_cotizacion cdc
            JOIN compra_detalle comp ON comp.id = cdc.compra_detalle_id
            WHERE cdc.cotizacion_id = %s
            GROUP BY comp.producto_id
        """, (cot_id,))
        costos_reales = {r[0]: float(r[1]) for r in cur.fetchall() if r[1] is not None}

        cur.execute("""
            SELECT DISTINCT comp.id, f.folio_factura, f.serie, comp.total,
                            COALESCE(f.nombre_emisor, '—') AS proveedor,
                            comp.fecha_compra
            FROM compra_detalle_cotizacion cdc
            JOIN compra_detalle cd ON cd.id = cdc.compra_detalle_id
            JOIN compras comp ON comp.id = cd.compra_id
            LEFT JOIN facturas f ON f.id = comp.factura_xml_id
            WHERE cdc.cotizacion_id = %s
            ORDER BY comp.fecha_compra DESC
        """, (cot_id,))
        ccols = [d[0] for d in cur.description]
        compras = []
        for r in cur.fetchall():
            d = _dec_to_float(dict(zip(ccols, r)))
            d["fecha_compra"] = str(d["fecha_compra"]) if d["fecha_compra"] else ""
            compras.append(d)

    venta_sub        = sum(l["precio_unitario"] * l["cantidad"] for l in lineas)
    costo_snap_total = sum((l["costo_snapshot"] or 0) * l["cantidad"] for l in lineas)
    costo_real_total = None
    if costos_reales:
        total_r = sum(
            costos_reales.get(l["producto_id"], 0) * l["cantidad"]
            for l in lineas if l["producto_id"] in costos_reales
        )
        if total_r > 0:
            costo_real_total = total_r

    margen_snap = round((venta_sub - costo_snap_total) / venta_sub * 100, 1) if venta_sub else None
    margen_real = round((venta_sub - costo_real_total) / venta_sub * 100, 1) if (costo_real_total and venta_sub) else None

    for l in lineas:
        cr = costos_reales.get(l["producto_id"])
        l["costo_real_u"]     = cr
        l["costo_real_total"] = round(cr * l["cantidad"], 2) if cr else None
        snap    = l["costo_snapshot"] or 0
        venta_u = l["precio_unitario"]
        l["margen_linea_snap"] = round((venta_u - snap) / venta_u * 100, 1) if venta_u else None
        l["margen_linea_real"] = round((venta_u - cr) / venta_u * 100, 1) if (cr and venta_u) else None

    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/costos.html",
        context={
            "user":             user,
            "cot":              cot,
            "lineas":           lineas,
            "compras":          compras,
            "venta_sub":        venta_sub,
            "costo_snap_total": costo_snap_total,
            "costo_real_total": costo_real_total,
            "margen_snap":      margen_snap,
            "margen_real":      margen_real,
            "ESTADO_COLOR":     ESTADO_COLOR,
        },
    )


@router.get("/{cot_id}/costos/linea/{detalle_id}/editar", response_class=HTMLResponse)
async def form_editar_costo(request: Request, cot_id: int, detalle_id: int):
    """Formulario inline de edición de costo_snapshot (HTMX)."""
    user = get_usuario_actual(request)
    if not user or user.get("rol") != "Administrador":
        raise HTTPException(status_code=403)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT costo_snapshot FROM cotizacion_detalle WHERE id = %s AND cotizacion_id = %s",
            (detalle_id, cot_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404)
        costo_actual = float(row[0]) if row[0] is not None else 0.0

    return HTMLResponse(f"""
<form hx-patch="/cotizaciones/{cot_id}/detalle/{detalle_id}/costo"
      hx-target="#costo-cell-{detalle_id}"
      hx-swap="innerHTML"
      class="flex items-center gap-1">
    <input type="number" name="costo" value="{costo_actual:.2f}" step="0.01" min="0"
           class="w-28 text-right text-sm border border-amber-300 rounded px-2 py-0.5
                  focus:outline-none focus:ring-1 focus:ring-amber-400"
           autofocus>
    <button type="submit"
            class="px-2 py-0.5 text-xs bg-amber-500 text-white rounded hover:bg-amber-600 transition-colors">
        &#10003;
    </button>
    <button type="button"
            hx-get="/cotizaciones/{cot_id}/costos/linea/{detalle_id}/cancelar"
            hx-target="#costo-cell-{detalle_id}"
            hx-swap="innerHTML"
            class="px-2 py-0.5 text-xs bg-gray-200 text-gray-600 rounded hover:bg-gray-300 transition-colors">
        &#10005;
    </button>
</form>
""")


@router.get("/{cot_id}/costos/linea/{detalle_id}/cancelar", response_class=HTMLResponse)
async def cancelar_editar_costo(request: Request, cot_id: int, detalle_id: int):
    """Restaura la celda de costo al modo lectura (HTMX cancel)."""
    user = get_usuario_actual(request)
    if not user or user.get("rol") != "Administrador":
        raise HTTPException(status_code=403)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT costo_snapshot, precio_unitario FROM cotizacion_detalle WHERE id = %s AND cotizacion_id = %s",
            (detalle_id, cot_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404)
        costo  = float(row[0]) if row[0] is not None else 0.0
        precio = float(row[1]) if row[1] is not None else 0.0

    margen = round((precio - costo) / precio * 100, 1) if precio else 0
    margen_class = "text-green-600" if margen >= 0 else "text-red-600"
    return HTMLResponse(f"""
<span class="font-semibold text-amber-700">${costo:,.2f}</span>
<button hx-get="/cotizaciones/{cot_id}/costos/linea/{detalle_id}/editar"
        hx-target="#costo-cell-{detalle_id}" hx-swap="innerHTML"
        class="ml-1 text-gray-300 hover:text-amber-500 transition-colors text-xs"
        title="Editar costo">&#9998;</button>
<span class="block text-[10px] {margen_class} font-semibold mt-0.5">margen est. {margen:.1f}%</span>
""")


@router.patch("/{cot_id}/detalle/{detalle_id}/costo", response_class=HTMLResponse)
async def editar_costo_snapshot(
    request: Request,
    cot_id: int,
    detalle_id: int,
    costo: float = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    if costo < 0:
        raise HTTPException(status_code=422, detail="El costo no puede ser negativo")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE cotizacion_detalle
            SET costo_snapshot = %s
            WHERE id = %s AND cotizacion_id = %s
            RETURNING precio_unitario
        """, (costo, detalle_id, cot_id))
        updated = cur.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Línea no encontrada")
        precio_u = float(updated[0]) if updated[0] else 0

    from web_app import audit as _audit
    _audit.registrar(
        "editar_costo_snapshot",
        username=user.get("username"),
        detalle=f"cotizacion_id={cot_id} detalle_id={detalle_id} nuevo_costo={costo}",
        ip=request.client.host if request.client else None,
    )

    margen = round((precio_u - costo) / precio_u * 100, 1) if precio_u else 0
    margen_class = "text-green-600" if margen >= 0 else "text-red-600"
    return HTMLResponse(f"""
<span class="font-semibold text-amber-700">${costo:,.2f}</span>
<button hx-get="/cotizaciones/{cot_id}/costos/linea/{detalle_id}/editar"
        hx-target="#costo-cell-{detalle_id}" hx-swap="innerHTML"
        class="ml-1 text-gray-300 hover:text-amber-500 transition-colors text-xs"
        title="Editar costo">&#9998;</button>
<span class="block text-[10px] {margen_class} font-semibold mt-0.5">margen est. {margen:.1f}%</span>
""")
