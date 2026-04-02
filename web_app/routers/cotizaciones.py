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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual

router = APIRouter(prefix="/cotizaciones")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# ── Constantes ────────────────────────────────────────────────────────────────
ESTADOS = ["Pendiente", "Programada", "Entregada", "Pagada", "Cancelada"]

ESTADO_COLOR = {
    "Pendiente":  ("bg-amber-100",  "text-amber-800"),
    "Programada": ("bg-purple-100", "text-purple-800"),
    "Entregada":  ("bg-green-100",  "text-green-800"),
    "Pagada":     ("bg-blue-100",   "text-blue-800"),
    "Cancelada":  ("bg-red-100",    "text-red-700"),
}

POR_PAGINA = 25


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generar_folio(empresa_db: str) -> str:
    """Genera el siguiente folio disponible para el año actual: COT-YYYY-NNNN."""
    año = date.today().year
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
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
        consecutivo = cur.fetchone()[0]
    return f"COT-{año}-{consecutivo:04d}"


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
            SELECT id, codigo, nombre, unidad_medida,
                   COALESCE(precio_venta, precio_base, 0) AS precio, stock_actual
            FROM productos
            WHERE nombre ILIKE %s OR codigo ILIKE %s
            ORDER BY nombre LIMIT 8
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
    fecha:          str = Form(...),
    orden_compra:   str = Form(""),
    notas:          str = Form(""),
    aplica_iva:     str = Form(""),
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

    iva_pct  = Decimal("0.16") if aplica_iva == "1" else Decimal("0")
    subtotal = sum(
        Decimal(str(p["cantidad"])) * Decimal(str(p["precio_unitario"])) for p in prods
    )
    iva      = (subtotal * iva_pct).quantize(Decimal("0.01"))
    total    = (subtotal + iva).quantize(Decimal("0.01"))
    subtotal = subtotal.quantize(Decimal("0.01"))

    folio = _generar_folio(user["empresa_db"])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            """
            INSERT INTO cotizaciones
              (folio, fecha, cliente_id, subtotal, iva, total,
               notas, estado, aplica_iva, orden_compra)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendiente', %s, %s)
            """,
            (folio, fecha, cliente_id,
             float(subtotal), float(iva), float(total),
             notas or None, 1 if aplica_iva == "1" else 0,
             orden_compra or None),
        )
        cot_id = cur.lastrowid

        for p in prods:
            cant  = Decimal(str(p["cantidad"]))
            precio = Decimal(str(p["precio_unitario"]))
            sub   = (cant * precio).quantize(Decimal("0.01"))
            p_iva = (sub * iva_pct).quantize(Decimal("0.01"))
            p_tot = (sub + p_iva).quantize(Decimal("0.01"))

            cur.execute(
                "SELECT precio_base FROM productos WHERE id = %s", (p["producto_id"],)
            )
            pb  = cur.fetchone()
            costo_snap = float(pb[0]) if pb else 0.0

            cur.execute(
                "SELECT COALESCE(stock_actual, 0) >= %s FROM productos WHERE id = %s",
                (float(cant), p["producto_id"]),
            )
            ts_row     = cur.fetchone()
            tiene_stock = bool(ts_row[0]) if ts_row else False

            cur.execute(
                """
                INSERT INTO cotizacion_detalle
                  (cotizacion_id, producto_id, cantidad, precio_unitario,
                   subtotal, iva, total, tiene_stock, costo_snapshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (cot_id, p["producto_id"],
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
                   cl.telefono  AS cliente_tel
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = %s
        """, (cot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
        cot = _dec_to_float(dict(zip([d[0] for d in cur.description], row)))

        cur.execute("""
            SELECT cd.id,
                   p.id AS producto_id,
                   p.codigo, p.nombre, p.unidad_medida,
                   cd.cantidad, cd.precio_unitario,
                   cd.subtotal, cd.iva, cd.total,
                   p.aplica_iva
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
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
            "estados":            ESTADOS,
            "estado_color":       ESTADO_COLOR,
            "hoy":                date.today().isoformat(),
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
            SELECT cd.producto_id, p.codigo, p.nombre, p.unidad_medida,
                   cd.cantidad, cd.precio_unitario,
                   p.aplica_iva, p.stock_actual
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
            """,
            (cot_id,),
        )
        dcols = [d[0] for d in cur.description]
        productos_existentes = [
            _dec_to_float(dict(zip(dcols, r))) for r in cur.fetchall()
        ]

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
        },
    )


@router.post("/{cot_id}/editar", response_class=HTMLResponse)
async def editar(
    request:        Request,
    cot_id:         int,
    cliente_id:     int = Form(...),
    fecha:          str = Form(...),
    orden_compra:   str = Form(""),
    notas:          str = Form(""),
    aplica_iva:     str = Form(""),
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

    iva_pct  = Decimal("0.16") if aplica_iva == "1" else Decimal("0")
    subtotal = sum(
        Decimal(str(p["cantidad"])) * Decimal(str(p["precio_unitario"])) for p in prods
    )
    iva      = (subtotal * iva_pct).quantize(Decimal("0.01"))
    total    = (subtotal + iva).quantize(Decimal("0.01"))
    subtotal = subtotal.quantize(Decimal("0.01"))

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

        cur.execute(
            """
            UPDATE cotizaciones
            SET cliente_id = %s, fecha = %s, orden_compra = %s, notas = %s,
                aplica_iva = %s, subtotal = %s, iva = %s, total = %s
            WHERE id = %s
            """,
            (cliente_id, fecha, orden_compra or None, notas or None,
             1 if aplica_iva == "1" else 0,
             float(subtotal), float(iva), float(total), cot_id),
        )

        cur.execute(
            "DELETE FROM cotizacion_detalle WHERE cotizacion_id = %s", (cot_id,)
        )

        for p in prods:
            cant  = Decimal(str(p["cantidad"]))
            precio = Decimal(str(p["precio_unitario"]))
            sub   = (cant * precio).quantize(Decimal("0.01"))
            p_iva = (sub * iva_pct).quantize(Decimal("0.01"))
            p_tot = (sub + p_iva).quantize(Decimal("0.01"))

            cur.execute(
                "SELECT precio_base FROM productos WHERE id = %s", (p["producto_id"],)
            )
            pb = cur.fetchone()
            costo_snap = float(pb[0]) if pb else 0.0

            cur.execute(
                "SELECT COALESCE(stock_actual, 0) >= %s FROM productos WHERE id = %s",
                (float(cant), p["producto_id"]),
            )
            ts_row      = cur.fetchone()
            tiene_stock = bool(ts_row[0]) if ts_row else False

            cur.execute(
                """
                INSERT INTO cotizacion_detalle
                  (cotizacion_id, producto_id, cantidad, precio_unitario,
                   subtotal, iva, total, tiene_stock, costo_snapshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (cot_id, p["producto_id"],
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
    r = _Resp(status_code=204)
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

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Verificar que la cotización y el producto existen
        cur.execute(
            "SELECT id FROM cotizaciones WHERE id = %s", (cot_id,)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Cotización no encontrada")

        cur.execute("""
            INSERT INTO entregas_parciales
                (cotizacion_id, producto_id, cantidad_entregada, fecha_entrega, notas, usuario)
            VALUES (%s, %s, %s, %s::date, %s, %s)
        """, (
            cot_id, producto_id, cantidad,
            fecha_entrega, notas.strip() or None,
            user.get("username"),
        ))

    from web_app import audit as _audit
    _audit.registrar(
        "entrega_parcial",
        username=user.get("username"),
        detalle=f"cotizacion_id={cot_id} producto_id={producto_id} cantidad={cantidad}",
        ip=request.client.host if request.client else None,
    )

    from fastapi.responses import Response as _Resp
    r = _Resp(status_code=204)
    r.headers["HX-Redirect"] = f"/cotizaciones/{cot_id}"
    return r
