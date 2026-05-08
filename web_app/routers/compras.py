# -*- coding: utf-8 -*-
"""
web_app/routers/compras.py
Módulo de Compras: registro de facturas de proveedores (con o sin XML),
asignación de costos a cotizaciones y actualización de stock.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual

router = APIRouter(prefix="/compras")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

POR_PAGINA = 25


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dec(d: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


def _generar_folio(cur, año: int) -> str:
    cur.execute(
        "SELECT COUNT(*) FROM compras WHERE folio LIKE %s",
        (f"CMP-{año}-%",),
    )
    n = cur.fetchone()[0] + 1
    return f"CMP-{año}-{n:04d}"


def _cargar_proveedores(empresa_db: str) -> list:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre, rfc FROM proveedores ORDER BY nombre"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _cargar_cotizaciones_activas(empresa_db: str) -> list:
    """Cotizaciones no cerradas disponibles para vincular costos de compra."""
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            """
            SELECT c.id, c.folio,
                   COALESCE(cl.nombre_comercial, '—') AS cliente
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.estado NOT IN ('Pagada', 'Cancelada')
            ORDER BY c.id DESC
            LIMIT 200
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ── Sugerencias de cotizaciones para un producto ─────────────────────────────

@router.get("/cotizaciones-por-producto", response_class=HTMLResponse)
async def cotizaciones_por_producto(
    request: Request,
    producto_id: int = 0,
):
    """HTMX: devuelve chips de cotizaciones en Programada que esperan este producto."""
    user = get_usuario_actual(request)
    if not user or producto_id <= 0:
        return HTMLResponse("")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT c.id, c.folio,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cd.cantidad AS cant_pedida,
                   COALESCE(
                       (SELECT SUM(cdc2.cantidad)
                        FROM compra_detalle_cotizacion cdc2
                        JOIN compra_detalle comp2 ON comp2.id = cdc2.compra_detalle_id
                        WHERE cdc2.cotizacion_id = c.id AND comp2.producto_id = cd.producto_id),
                       0
                   ) AS cant_ya_comprada
            FROM cotizacion_detalle cd
            JOIN cotizaciones c ON c.id = cd.cotizacion_id
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE cd.producto_id = %s
              AND c.estado IN ('Programada', 'Parcialmente Entregada')
            ORDER BY c.fecha ASC
            LIMIT 10
        """, (producto_id,))
        cols = [d[0] for d in cur.description]
        sugerencias = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            d["cant_pedida"]    = float(d["cant_pedida"] or 0)
            d["cant_ya_comprada"] = float(d["cant_ya_comprada"] or 0)
            d["cant_pendiente"] = max(0, d["cant_pedida"] - d["cant_ya_comprada"])
            sugerencias.append(d)

    if not sugerencias:
        return HTMLResponse("")

    html_parts = ['<div class="mt-1 flex flex-wrap gap-1">',
                  '<span class="text-[10px] text-gray-400 w-full">Cotizaciones esperando:</span>']
    for s in sugerencias:
        pendiente_txt = f"{s['cant_pendiente']:g} pendientes" if s['cant_pendiente'] > 0 else "ya cubierta"
        color = "bg-amber-50 border-amber-300 text-amber-700" if s['cant_pendiente'] > 0 else "bg-gray-50 border-gray-200 text-gray-400"
        html_parts.append(
            f'<button type="button" '
            f'class="text-[10px] border rounded px-2 py-0.5 {color} sugerencia-cot" '
            f'data-cot-id="{s["id"]}" data-cantidad="{s["cant_pendiente"]}">'
            f'{s["folio"]} · {s["cliente"][:18]} · {pendiente_txt}'
            f'</button>'
        )
    html_parts.append('</div>')
    return HTMLResponse("".join(html_parts))


# ── Lista ─────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def lista(
    request: Request,
    buscar: str = "",
    page: int = 1,
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso")

    offset = (page - 1) * POR_PAGINA
    where, params = [], []

    if buscar:
        where.append(
            "(c.folio ILIKE %s OR p.nombre ILIKE %s OR c.ticket_referencia ILIKE %s)"
        )
        like = f"%{buscar}%"
        params += [like, like, like]

    filtro = ("WHERE " + " AND ".join(where)) if where else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT c.id)
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            {filtro}
            """,
            params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT c.id, c.folio, c.fecha_compra, c.total,
                   c.ticket_referencia,
                   COALESCE(p.nombre, '— sin proveedor —') AS proveedor
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            {filtro}
            ORDER BY c.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [POR_PAGINA, offset],
        )
        cols = [d[0] for d in cur.description]
        compras = [_dec(dict(zip(cols, r))) for r in cur.fetchall()]

    paginas = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)

    return templates.TemplateResponse(
        request=request,
        name="compras/lista.html",
        context={
            "user":    user,
            "compras": compras,
            "buscar":  buscar,
            "page":    page,
            "paginas": paginas,
            "total":   total,
        },
    )


# ── Parsear XML (AJAX) ────────────────────────────────────────────────────────

@router.post("/parsear-xml")
async def parsear_xml(
    request: Request,
    archivo: UploadFile = File(...),
):
    """Recibe un XML CFDI y devuelve sus datos en JSON para pre-rellenar el form."""
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)

    contenido = await archivo.read()
    try:
        from core.cfdi import parsear_cfdi_bytes
        datos = parsear_cfdi_bytes(contenido)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Buscar proveedor por RFC
    proveedor_id = None
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT id, nombre FROM proveedores WHERE UPPER(rfc) = UPPER(%s) LIMIT 1",
            (datos["rfc_emisor"],),
        )
        row = cur.fetchone()
        if row:
            proveedor_id = row[0]

        # Buscar productos por NoIdentificacion / descripcion
        conceptos_enriquecidos = []
        for c in datos["conceptos"]:
            producto_id = None
            producto_nombre = c["descripcion"]
            producto_unidad = c["unidad"]
            precio_base = 0.0

            # Intentar por código (no_identificacion)
            if c["no_identificacion"]:
                cur.execute(
                    "SELECT id, nombre, unidad_medida, precio_base FROM productos "
                    "WHERE codigo = %s LIMIT 1",
                    (c["no_identificacion"],),
                )
                row = cur.fetchone()
                if row:
                    producto_id = row[0]
                    producto_nombre = row[1]
                    producto_unidad = row[2]
                    precio_base = float(row[3])

            conceptos_enriquecidos.append({
                **c,
                "producto_id":     producto_id,
                "producto_nombre": producto_nombre,
                "producto_unidad": producto_unidad,
                "precio_base":     precio_base,
            })

    fecha_str = datos["fecha"][:10] if datos["fecha"] else date.today().isoformat()

    return JSONResponse({
        "proveedor_id":       proveedor_id,
        "rfc_emisor":         datos["rfc_emisor"],
        "nombre_emisor":      datos["nombre_emisor"],
        "fecha":              fecha_str,
        "folio_proveedor":    f"{datos['serie']}{datos['folio']}".strip(),
        "subtotal":           datos["subtotal"],
        "iva":                datos["iva"],
        "total":              datos["total"],
        "conceptos":          conceptos_enriquecidos,
    })


# ── Buscar producto (AJAX) ────────────────────────────────────────────────────

@router.get("/buscar-producto", response_class=HTMLResponse)
async def buscar_producto(request: Request, q: str = ""):
    user = get_usuario_actual(request)
    if not user or len(q) < 2:
        return HTMLResponse("")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            """
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   p.precio_base AS costo_base, p.stock_actual, p.aplica_iva
            FROM productos p
            WHERE p.nombre ILIKE %s OR p.codigo ILIKE %s
            ORDER BY p.nombre LIMIT 8
            """,
            (f"%{q}%", f"%{q}%"),
        )
        cols = [d[0] for d in cur.description]
        resultados = [
            {k: float(v) if isinstance(v, Decimal) else v
             for k, v in dict(zip(cols, r)).items()}
            for r in cur.fetchall()
        ]

    return templates.TemplateResponse(
        request=request,
        name="compras/_prod_sugerencias.html",
        context={"resultados": resultados, "user": user},
    )


# ── Cotizaciones de un producto (AJAX) ────────────────────────────────────────

@router.get("/cotizaciones-producto")
async def cotizaciones_producto(request: Request, producto_id: int = 0):
    """Retorna cotizaciones activas que tienen este producto, con cantidad pendiente."""
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)

    if not producto_id:
        return JSONResponse([])

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            """
            SELECT c.id, c.folio,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cd.cantidad AS cant_cotizada,
                   COALESCE(
                       (SELECT SUM(cdc.cantidad)
                        FROM compra_detalle_cotizacion cdc
                        JOIN compra_detalle comp ON comp.id = cdc.compra_detalle_id
                        WHERE cdc.cotizacion_id = c.id
                          AND comp.producto_id = cd.producto_id),
                       0
                   ) AS cant_asignada
            FROM cotizacion_detalle cd
            JOIN cotizaciones c ON c.id = cd.cotizacion_id
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE cd.producto_id = %s
              AND c.estado IN ('Pendiente', 'Programada')
            ORDER BY c.id DESC
            LIMIT 50
            """,
            (producto_id,),
        )
        cols = [d[0] for d in cur.description]
        rows = [
            {k: float(v) if isinstance(v, Decimal) else v
             for k, v in dict(zip(cols, r)).items()}
            for r in cur.fetchall()
        ]

    # Calcular cantidad pendiente de asignar
    for r in rows:
        r["cant_pendiente"] = max(0, r["cant_cotizada"] - r["cant_asignada"])

    return JSONResponse(rows)


# ── Nueva compra (formulario) ─────────────────────────────────────────────────

@router.get("/nueva", response_class=HTMLResponse)
async def nueva(request: Request, factura_id: int = Query(0)):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    proveedores  = _cargar_proveedores(user["empresa_db"])
    cotizaciones = _cargar_cotizaciones_activas(user["empresa_db"])

    factura_prefill = None
    if factura_id:
        with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
            cur.execute(
                """SELECT id, tipo, rfc_emisor, nombre_emisor,
                          fecha, subtotal, iva, total, folio_factura, serie
                   FROM facturas WHERE id = %s""",
                (factura_id,),
            )
            frow = cur.fetchone()
            if frow:
                fcols = [d[0] for d in cur.description]
                fdata = dict(zip(fcols, frow))

                # Match proveedor by RFC
                prov_id = None
                if fdata.get("rfc_emisor"):
                    cur.execute(
                        "SELECT id FROM proveedores WHERE rfc = %s LIMIT 1",
                        (fdata["rfc_emisor"],),
                    )
                    prow = cur.fetchone()
                    if prow:
                        prov_id = prow[0]

                # Load conceptos and match to productos
                cur.execute(
                    """SELECT descripcion, cantidad, valor_unitario,
                              clave_prod_serv, clave_unidad, unidad, no_identificacion
                       FROM factura_conceptos WHERE factura_id = %s ORDER BY id""",
                    (factura_id,),
                )
                ccols = [d[0] for d in cur.description]
                conceptos = []
                for raw in cur.fetchall():
                    c = dict(zip(ccols, raw))
                    c["cantidad"]       = float(c["cantidad"] or 0)
                    c["valor_unitario"] = float(c["valor_unitario"] or 0)
                    c["producto_id"]    = None
                    c["producto_nombre"] = c["descripcion"]
                    c["producto_unidad"] = c["unidad"] or ""
                    c["aplica_iva"]     = True
                    codigo = (c.get("no_identificacion") or "").strip()
                    c["codigo"] = codigo
                    if codigo:
                        cur.execute(
                            "SELECT id, nombre, unidad_medida, aplica_iva "
                            "FROM productos WHERE codigo = %s LIMIT 1",
                            (codigo,),
                        )
                        prow = cur.fetchone()
                        if prow:
                            c["producto_id"]    = prow[0]
                            c["producto_nombre"] = prow[1]
                            c["producto_unidad"] = prow[2] or ""
                            c["aplica_iva"]     = bool(prow[3])
                    conceptos.append(c)

                fecha_str = ""
                if fdata.get("fecha"):
                    try:
                        fecha_str = str(fdata["fecha"])[:10]
                    except Exception:
                        pass

                folio_str = ((fdata.get("serie") or "") + (fdata.get("folio_factura") or "")).strip()

                # Cotizaciones ya vinculadas a esta factura (para auto-asignar)
                cur.execute("""
                    SELECT c.id, c.folio,
                           COALESCE(cl.nombre_comercial, '—') AS cliente
                    FROM factura_cotizaciones fc
                    JOIN cotizaciones c ON c.id = fc.cotizacion_id
                    LEFT JOIN clientes cl ON cl.id = c.cliente_id
                    WHERE fc.factura_id = %s
                    ORDER BY c.id
                """, (factura_id,))
                ccots = [d[0] for d in cur.description]
                cots_vinculadas = [dict(zip(ccots, r)) for r in cur.fetchall()]

                factura_prefill = {
                    "factura_id":       factura_id,
                    "proveedor_id":     prov_id,
                    "nombre_emisor":    fdata.get("nombre_emisor") or fdata.get("rfc_emisor", ""),
                    "fecha":            fecha_str,
                    "folio":            folio_str,
                    "conceptos":        conceptos,
                    "cots_vinculadas":  cots_vinculadas,
                }

    return templates.TemplateResponse(
        request=request,
        name="compras/form.html",
        context={
            "user":            user,
            "proveedores":     proveedores,
            "cotizaciones":    cotizaciones,
            "hoy":             date.today().isoformat(),
            "factura_prefill": factura_prefill,
        },
    )


# ── Crear compra (POST) ───────────────────────────────────────────────────────

@router.post("", response_class=HTMLResponse)
async def crear(
    request:           Request,
    proveedor_id:      str  = Form(""),
    fecha_compra:      str  = Form(...),
    ticket_referencia: str  = Form(""),
    notas:             str  = Form(""),
    lineas_json:       str  = Form(...),
    factura_id:        str  = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403)

    try:
        lineas = json.loads(lineas_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Datos de líneas inválidos")
    if not lineas:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un producto")

    prov_id = int(proveedor_id) if proveedor_id.strip().isdigit() else None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        folio = _generar_folio(cur, date.today().year)

        subtotal_global = Decimal("0")
        iva_global      = Decimal("0")

        # ── Calcular totales ──────────────────────────────────────────────────
        detalle_rows = []
        for ln in lineas:
            cant       = Decimal(str(ln["cantidad"]))
            costo_u    = Decimal(str(ln["costo_unitario"]))
            aplica_iva = bool(ln.get("aplica_iva", False))
            sub        = (cant * costo_u).quantize(Decimal("0.01"))
            iva        = (sub * Decimal("0.16")).quantize(Decimal("0.01")) if aplica_iva else Decimal("0")
            tot        = sub + iva

            subtotal_global += sub
            iva_global      += iva
            detalle_rows.append({
                "producto_id":  int(ln["producto_id"]),
                "cantidad":     cant,
                "costo_u":      costo_u,
                "subtotal":     sub,
                "iva":          iva,
                "total":        tot,
                "asignaciones": ln.get("asignaciones", []),
            })

        total_global = subtotal_global + iva_global

        # ── Insertar compra ───────────────────────────────────────────────────
        _factura_xml_id = int(factura_id) if factura_id.strip().isdigit() else None
        cur.execute(
            """
            INSERT INTO compras
              (folio, proveedor_id, fecha_compra, subtotal, iva, total,
               ticket_referencia, notas, factura_xml_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                folio, prov_id, fecha_compra,
                float(subtotal_global), float(iva_global), float(total_global),
                ticket_referencia or None, notas or None, _factura_xml_id,
            ),
        )
        compra_id = cur.lastrowid

        # ── Insertar detalle, asignaciones y actualizar stock ─────────────────
        for row in detalle_rows:
            cur.execute(
                """
                INSERT INTO compra_detalle
                  (compra_id, producto_id, cantidad, costo_unitario, costo_total)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    compra_id, row["producto_id"],
                    float(row["cantidad"]), float(row["costo_u"]),
                    float(row["total"]),
                ),
            )
            detalle_id = cur.lastrowid

            # Asignaciones a cotizaciones
            asignado_total = Decimal("0")
            for asig in row["asignaciones"]:
                cant_asig = Decimal(str(asig["cantidad"]))
                if cant_asig <= 0:
                    continue
                cot_id = asig.get("cotizacion_id") or None
                cur.execute(
                    """
                    INSERT INTO compra_detalle_cotizacion
                      (compra_detalle_id, cotizacion_id, cantidad)
                    VALUES (%s, %s, %s)
                    """,
                    (detalle_id, cot_id, float(cant_asig)),
                )
                asignado_total += cant_asig

            # Stock general = cantidad no asignada a ninguna cotización
            remanente = row["cantidad"] - asignado_total
            if remanente > 0:
                cur.execute(
                    """
                    INSERT INTO compra_detalle_cotizacion
                      (compra_detalle_id, cotizacion_id, cantidad)
                    VALUES (%s, NULL, %s)
                    """,
                    (detalle_id, float(remanente)),
                )

            # Obtener stock actual para el movimiento
            cur.execute(
                "SELECT COALESCE(stock_actual, 0) FROM productos WHERE id = %s",
                (row["producto_id"],),
            )
            stock_antes = float(cur.fetchone()[0])
            stock_despues = stock_antes + float(row["cantidad"])

            # Actualizar stock y costo promedio ponderado
            cur.execute(
                "SELECT COALESCE(costo_promedio, 0) FROM productos WHERE id = %s",
                (row["producto_id"],),
            )
            costo_prom_ant = Decimal(str(cur.fetchone()[0]))
            denominador = stock_antes + float(row["cantidad"])
            if denominador > 0:
                nuevo_prom = (
                    Decimal(str(stock_antes)) * costo_prom_ant
                    + row["cantidad"] * row["costo_u"]
                ) / Decimal(str(denominador))
            else:
                nuevo_prom = row["costo_u"]

            cur.execute(
                "UPDATE productos SET stock_actual = %s, costo_promedio = %s WHERE id = %s",
                (stock_despues, float(nuevo_prom.quantize(Decimal("0.0001"))), row["producto_id"]),
            )

            # Registrar precio en historial del producto
            cur.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente, proveedor_id)
                VALUES (%s, %s, %s, %s, 'compra', %s)
            """, (
                row["producto_id"],
                float(row["costo_u"]),
                fecha_compra or date.today().isoformat(),
                f"Compra {folio}",
                prov_id,
            ))

            # Registrar movimiento de stock
            cur.execute(
                """
                INSERT INTO movimientos_stock
                  (producto_id, tipo, motivo, cantidad,
                   stock_antes, stock_despues, referencia, usuario)
                VALUES (%s, 'entrada', 'compra', %s, %s, %s, %s, %s)
                """,
                (
                    row["producto_id"], float(row["cantidad"]),
                    stock_antes, stock_despues,
                    folio, user.get("username", ""),
                ),
            )

    return RedirectResponse(f"/compras/{compra_id}", status_code=303)


# ── Presupuesto de compra: selección de pedidos ───────────────────────────────

@router.get("/presupuesto", response_class=HTMLResponse)
async def presupuesto_seleccion(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
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
            """,
        )
        cols = [d[0] for d in cur.description]
        pedidos = [dict(zip(cols, r)) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="compras/presupuesto.html",
        context={"user": user, "pedidos": pedidos},
    )


@router.post("/presupuesto/generar")
async def presupuesto_generar(request: Request):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    form = await request.form()
    ids_raw = form.getlist("cotizacion_ids")
    if not ids_raw:
        raise HTTPException(status_code=400, detail="Seleccione al menos un pedido")

    try:
        cotizacion_ids = [int(i) for i in ids_raw]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs inválidos")

    insumos_raw = form.get("insumos_json", "[]") or "[]"
    try:
        insumos = json.loads(insumos_raw)
        if not isinstance(insumos, list):
            insumos = []
    except (json.JSONDecodeError, ValueError):
        insumos = []

    from web_app.pdf_presupuesto_compra import generar_pdf_presupuesto_compra
    try:
        pdf_bytes = generar_pdf_presupuesto_compra(
            user["empresa_db"], cotizacion_ids, insumos=insumos
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    from datetime import date as _date
    filename = f"PresupuestoCompra_{_date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Editar línea de compra (costo unitario + asignaciones) ───────────────────

@router.patch("/{compra_id}/detalle/{detalle_id}", response_class=JSONResponse)
async def editar_detalle(request: Request, compra_id: int, detalle_id: int):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin acceso")

    body = await request.json()
    nuevo_costo_u = Decimal(str(body.get("costo_unitario", 0)))
    asignaciones  = body.get("asignaciones", [])

    if nuevo_costo_u <= 0:
        raise HTTPException(status_code=400, detail="Costo unitario debe ser mayor a cero")

    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        # Verificar que el detalle pertenece a esta compra
        cur.execute(
            "SELECT cantidad, costo_unitario FROM compra_detalle WHERE id = %s AND compra_id = %s",
            (detalle_id, compra_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Línea no encontrada")
        cantidad          = Decimal(str(row[0]))
        costo_u_original  = Decimal(str(row[1]))

        # Validar que asignaciones no superen la cantidad comprada
        total_asig = sum(Decimal(str(a["cantidad"])) for a in asignaciones if Decimal(str(a.get("cantidad", 0))) > 0)
        if total_asig > cantidad:
            raise HTTPException(status_code=400, detail=f"Asignaciones ({total_asig}) superan la cantidad comprada ({cantidad})")

        nuevo_total = (nuevo_costo_u * cantidad).quantize(Decimal("0.01"))

        # Actualizar línea
        cur.execute(
            "UPDATE compra_detalle SET costo_unitario = %s, costo_total = %s WHERE id = %s",
            (float(nuevo_costo_u), float(nuevo_total), detalle_id),
        )

        # Reemplazar asignaciones
        cur.execute("DELETE FROM compra_detalle_cotizacion WHERE compra_detalle_id = %s", (detalle_id,))
        asignado_total = Decimal("0")
        for asig in asignaciones:
            cant_asig = Decimal(str(asig.get("cantidad", 0)))
            if cant_asig <= 0:
                continue
            cot_id = asig.get("cotizacion_id") or None
            cur.execute(
                "INSERT INTO compra_detalle_cotizacion (compra_detalle_id, cotizacion_id, cantidad) VALUES (%s, %s, %s)",
                (detalle_id, cot_id, float(cant_asig)),
            )
            asignado_total += cant_asig

        remanente = cantidad - asignado_total
        if remanente > 0:
            cur.execute(
                "INSERT INTO compra_detalle_cotizacion (compra_detalle_id, cotizacion_id, cantidad) VALUES (%s, NULL, %s)",
                (detalle_id, float(remanente)),
            )

        # Recalcular totales de la compra
        cur.execute(
            "SELECT SUM(costo_total) FROM compra_detalle WHERE compra_id = %s",
            (compra_id,),
        )
        nuevo_subtotal = Decimal(str(cur.fetchone()[0] or 0))

        cur.execute("SELECT iva FROM compras WHERE id = %s", (compra_id,))
        iva_actual = Decimal(str(cur.fetchone()[0] or 0))
        aplica_iva  = iva_actual > 0
        nuevo_iva   = (nuevo_subtotal * Decimal("0.16")).quantize(Decimal("0.01")) if aplica_iva else Decimal("0")
        nuevo_total_compra = nuevo_subtotal + nuevo_iva

        cur.execute(
            "UPDATE compras SET subtotal = %s, iva = %s, total = %s WHERE id = %s",
            (float(nuevo_subtotal), float(nuevo_iva), float(nuevo_total_compra), compra_id),
        )

        # Ajustar costo_promedio del producto si cambió el costo unitario
        if nuevo_costo_u != costo_u_original:
            cur.execute(
                "SELECT id, COALESCE(stock_actual, 0), COALESCE(costo_promedio, 0) "
                "FROM productos WHERE id = ("
                "  SELECT producto_id FROM compra_detalle WHERE id = %s"
                ")",
                (detalle_id,),
            )
            p = cur.fetchone()
            if p:
                prod_id, stock_actual, prom_actual = p
                stock_actual = Decimal(str(stock_actual))
                prom_actual  = Decimal(str(prom_actual))
                if stock_actual > 0:
                    diferencia  = (nuevo_costo_u - costo_u_original) * cantidad
                    nuevo_prom  = prom_actual + diferencia / stock_actual
                    nuevo_prom  = max(nuevo_prom, Decimal("0"))
                    cur.execute(
                        "UPDATE productos SET costo_promedio = %s WHERE id = %s",
                        (float(nuevo_prom.quantize(Decimal("0.0001"))), prod_id),
                    )

    return JSONResponse({"ok": True, "nuevo_costo_u": float(nuevo_costo_u), "nuevo_total": float(nuevo_total)})


# ── Detalle compra ────────────────────────────────────────────────────────────

@router.get("/{compra_id}", response_class=HTMLResponse)
async def detalle(request: Request, compra_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Cabecera
        cur.execute(
            """
            SELECT c.*,
                   COALESCE(p.nombre, '— sin proveedor —') AS proveedor_nombre,
                   p.rfc AS proveedor_rfc
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            WHERE c.id = %s
            """,
            (compra_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Compra no encontrada")
        compra = _dec(dict(zip([d[0] for d in cur.description], row)))

        # Líneas con asignaciones
        cur.execute(
            """
            SELECT cd.id, p.codigo, p.nombre, p.unidad_medida,
                   cd.cantidad, cd.costo_unitario, cd.costo_total
            FROM compra_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.compra_id = %s
            ORDER BY cd.id
            """,
            (compra_id,),
        )
        dcols  = [d[0] for d in cur.description]
        lineas = [_dec(dict(zip(dcols, r))) for r in cur.fetchall()]

        # Para cada línea, cargar sus asignaciones
        for ln in lineas:
            cur.execute(
                """
                SELECT cdc.cantidad,
                       COALESCE(c.folio, '— stock general —') AS folio,
                       COALESCE(cl.nombre_comercial, '') AS cliente,
                       cdc.cotizacion_id
                FROM compra_detalle_cotizacion cdc
                LEFT JOIN cotizaciones c ON c.id = cdc.cotizacion_id
                LEFT JOIN clientes cl ON cl.id = c.cliente_id
                WHERE cdc.compra_detalle_id = %s
                ORDER BY cdc.id
                """,
                (ln["id"],),
            )
            acols = [d[0] for d in cur.description]
            ln["asignaciones"] = [
                _dec(dict(zip(acols, r))) for r in cur.fetchall()
            ]

    return templates.TemplateResponse(
        request=request,
        name="compras/detalle.html",
        context={
            "user":   user,
            "compra": compra,
            "lineas": lineas,
        },
    )
