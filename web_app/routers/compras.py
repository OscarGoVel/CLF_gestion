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

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, File
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
    """Cotizaciones Pendiente/Programada disponibles para vincular costos."""
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            """
            SELECT c.id, c.folio,
                   COALESCE(cl.nombre_comercial, '—') AS cliente
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.estado IN ('Pendiente', 'Programada')
            ORDER BY c.id DESC
            LIMIT 200
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


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
async def nueva(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    proveedores = _cargar_proveedores(user["empresa_db"])
    cotizaciones = _cargar_cotizaciones_activas(user["empresa_db"])

    return templates.TemplateResponse(
        request=request,
        name="compras/form.html",
        context={
            "user":         user,
            "proveedores":  proveedores,
            "cotizaciones": cotizaciones,
            "hoy":          date.today().isoformat(),
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
        cur.execute(
            """
            INSERT INTO compras
              (folio, proveedor_id, fecha_compra, subtotal, iva, total,
               ticket_referencia, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                folio, prov_id, fecha_compra,
                float(subtotal_global), float(iva_global), float(total_global),
                ticket_referencia or None, notas or None,
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

            # Stock general = cantidad no asignada (si la hay)
            remanente = row["cantidad"] - asignado_total
            if remanente > 0 and not row["asignaciones"]:
                # Sin asignaciones explícitas → todo va a stock general
                cur.execute(
                    """
                    INSERT INTO compra_detalle_cotizacion
                      (compra_detalle_id, cotizacion_id, cantidad)
                    VALUES (%s, NULL, %s)
                    """,
                    (detalle_id, float(row["cantidad"])),
                )

            # Obtener stock actual para el movimiento
            cur.execute(
                "SELECT COALESCE(stock_actual, 0) FROM productos WHERE id = %s",
                (row["producto_id"],),
            )
            stock_antes = float(cur.fetchone()[0])
            stock_despues = stock_antes + float(row["cantidad"])

            # Actualizar stock
            cur.execute(
                "UPDATE productos SET stock_actual = %s WHERE id = %s",
                (stock_despues, row["producto_id"]),
            )

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

    from web_app.pdf_presupuesto_compra import generar_pdf_presupuesto_compra
    try:
        pdf_bytes = generar_pdf_presupuesto_compra(user["empresa_db"], cotizacion_ids)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    from datetime import date as _date
    filename = f"PresupuestoCompra_{_date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
