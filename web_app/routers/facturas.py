# -*- coding: utf-8 -*-
"""
web_app/routers/facturas.py
Módulo de Facturas: lista, detalle, importar XML, vincular cotización.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa, get_empresas
from web_app.dependencies import get_usuario_actual
from web_app.cfdi import parsear_cfdi_bytes

router = APIRouter(prefix="/facturas")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Directorio donde se guardan los XMLs (relativo al proyecto)
_BASE = Path(__file__).parent.parent.parent
XML_DIR = _BASE / "facturas_xml"
XML_DIR.mkdir(exist_ok=True)

TIPO_LABEL = {"I": "Ingreso", "E": "Egreso", "T": "Traslado", "N": "Nómina", "P": "Pago"}
METODO_LABEL = {"PUE": "Pago en una sola exhibición", "PPD": "Pago en parcialidades"}


def _floats(d: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


# ─────────────────────────────────────────────────────────────────────────────
# LISTA
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def lista_facturas(
    request: Request,
    buscar: str = "",
    tipo: str = "",
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso a facturas")

    where, params = [], []
    if buscar:
        where.append(
            "(f.folio_factura ILIKE %s OR f.rfc_receptor ILIKE %s "
            "OR f.nombre_receptor ILIKE %s OR f.uuid ILIKE %s)"
        )
        params += [f"%{buscar}%"] * 4
    if tipo:
        where.append("f.tipo = %s"); params.append(tipo)

    w = ("WHERE " + " AND ".join(where)) if where else ""

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT f.id, f.serie, f.folio_factura, f.fecha, f.fecha_timbrado,
                   f.rfc_receptor, f.nombre_receptor,
                   f.subtotal, f.descuento, f.iva, f.total,
                   f.tipo, f.metodo_pago, f.forma_pago, f.moneda, f.uuid,
                   COUNT(fc.cotizacion_id) AS num_cotizaciones,
                   (SELECT id FROM compras WHERE factura_xml_id = f.id LIMIT 1) AS compra_id
            FROM facturas f
            LEFT JOIN factura_cotizaciones fc ON fc.factura_id = f.id
            {w}
            GROUP BY f.id
            ORDER BY f.fecha_timbrado DESC, f.id DESC
        """, params or None)
        cols     = [d[0] for d in cur.description]
        facturas = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

        cur.execute("SELECT DISTINCT tipo FROM facturas WHERE tipo IS NOT NULL ORDER BY tipo")
        tipos = [r[0] for r in cur.fetchall()]

    ctx = {
        "user": user,
        "facturas": facturas,
        "tipos": tipos,
        "tipo_sel": tipo,
        "buscar": buscar,
        "tipo_label": TIPO_LABEL,
        "metodo_label": METODO_LABEL,
        "seccion": "facturas",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="facturas/_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="facturas/lista.html", context=ctx
    )


# ─────────────────────────────────────────────────────────────────────────────
# BÚSQUEDA DE PRODUCTOS JSON (debe ir ANTES de /{factura_id})
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/buscar-producto", response_class=JSONResponse)
async def buscar_producto_json(request: Request, q: str = ""):
    user = get_usuario_actual(request)
    if not user or len(q) < 2:
        return JSONResponse([])
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, codigo, nombre, unidad_medida
            FROM productos
            WHERE nombre ILIKE %s OR codigo ILIKE %s
            ORDER BY nombre LIMIT 10
        """, (f"%{q}%", f"%{q}%"))
        rows = cur.fetchall()
    return JSONResponse([{"id": r[0], "codigo": r[1], "nombre": r[2], "unidad": r[3]} for r in rows])


# ─────────────────────────────────────────────────────────────────────────────
# DETALLE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{factura_id}", response_class=HTMLResponse)
async def detalle_factura(request: Request, factura_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM facturas WHERE id = %s", (factura_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Factura no encontrada")
        factura = _floats(dict(zip([d[0] for d in cur.description], row)))

        cur.execute("""
            SELECT clave_prod_serv, no_identificacion, cantidad,
                   clave_unidad, unidad, descripcion,
                   valor_unitario, importe, descuento
            FROM factura_conceptos
            WHERE factura_id = %s
            ORDER BY id
        """, (factura_id,))
        ccols    = [d[0] for d in cur.description]
        conceptos = [_floats(dict(zip(ccols, r))) for r in cur.fetchall()]

        cur.execute("""
            SELECT cot.id, cot.folio, cot.fecha, cot.total, cot.estado,
                   fc.fecha_vinculo, fc.notas
            FROM factura_cotizaciones fc
            JOIN cotizaciones cot ON cot.id = fc.cotizacion_id
            WHERE fc.factura_id = %s
            ORDER BY cot.fecha DESC
        """, (factura_id,))
        vcols      = [d[0] for d in cur.description]
        vinculadas = [_floats(dict(zip(vcols, r))) for r in cur.fetchall()]

        cur.execute(
            "SELECT id, folio FROM compras WHERE factura_xml_id = %s LIMIT 1",
            (factura_id,),
        )
        _row = cur.fetchone()
        compra_vinculada = {"id": _row[0], "folio": _row[1]} if _row else None

    from core.constants import ESTADO_COLOR_CSS as ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="facturas/detalle.html",
        context={
            "user": user,
            "factura": factura,
            "conceptos": conceptos,
            "vinculadas": vinculadas,
            "factura_id": factura_id,
            "tipo_label": TIPO_LABEL,
            "metodo_label": METODO_LABEL,
            "estado_color": ESTADO_COLOR,
            "seccion": "facturas",
            "compra_vinculada": compra_vinculada,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# DESCARGAR XML
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{factura_id}/xml")
async def descargar_xml(request: Request, factura_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT ruta_xml, folio_factura, serie FROM facturas WHERE id = %s", (factura_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            raise HTTPException(404, "Archivo XML no disponible")
        ruta_xml, folio, serie = row

    # ruta puede ser absoluta o relativa al proyecto
    path = Path(ruta_xml)
    if not path.is_absolute():
        path = _BASE / path
    if not path.exists():
        raise HTTPException(404, "Archivo XML no encontrado en disco")

    nombre = f"{serie}{folio}.xml" if serie else f"factura_{factura_id}.xml"
    return FileResponse(str(path), media_type="text/xml", filename=nombre)


# ─────────────────────────────────────────────────────────────────────────────
# IMPORTAR XML
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/importar", response_class=HTMLResponse)
async def importar_xml(request: Request, archivo: UploadFile = File(...)):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso para importar facturas")

    contenido = await archivo.read()

    try:
        datos = parsear_cfdi_bytes(contenido)
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="facturas/_import_result.html",
            context={"error": str(e), "user": user},
        )

    uuid = datos["uuid"]

    # Detectar tipo automáticamente: si la empresa activa es el receptor → Egreso
    empresa_cfg = next((e for e in get_empresas() if e["id"] == user.get("empresa_id")), None)
    rfc_empresa = (empresa_cfg.get("rfc") or "").upper().strip() if empresa_cfg else ""
    rfc_receptor = (datos.get("rfc_receptor") or "").upper().strip()
    if rfc_empresa and rfc_receptor == rfc_empresa:
        datos["tipo"] = "E"

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Verificar duplicado
        cur.execute("SELECT id FROM facturas WHERE uuid = %s", (uuid,))
        existing = cur.fetchone()
        if existing:
            return templates.TemplateResponse(
                request=request,
                name="facturas/_import_result.html",
                context={
                    "error": f"Esta factura ya está registrada (UUID: {uuid[:8]}…)",
                    "user": user,
                },
            )

        # Guardar archivo XML
        nombre_archivo = archivo.filename or f"{uuid[:8]}.xml"
        ruta_destino = XML_DIR / nombre_archivo
        # Evitar sobreescribir
        if ruta_destino.exists():
            stem = ruta_destino.stem
            ruta_destino = XML_DIR / f"{stem}_{uuid[:8]}.xml"
        ruta_destino.write_bytes(contenido)
        ruta_relativa = f"facturas_xml/{ruta_destino.name}"

        # Insertar factura
        cur.execute("""
            INSERT INTO facturas (
                uuid, serie, folio_factura, fecha, fecha_timbrado, no_cert_sat,
                rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor, uso_cfdi,
                tipo, metodo_pago, forma_pago, moneda,
                subtotal, descuento, iva, total, ruta_xml
            ) VALUES (
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,%s,%s
            ) RETURNING id
        """, (
            uuid, datos["serie"], datos["folio"], datos["fecha"],
            datos["fecha_timbrado"], datos["no_cert_sat"],
            datos["rfc_emisor"], datos["nombre_emisor"],
            datos["rfc_receptor"], datos["nombre_receptor"], datos["uso_cfdi"],
            datos["tipo"], datos["metodo_pago"], datos["forma_pago"], datos["moneda"],
            datos["subtotal"], datos["descuento"], datos["iva"], datos["total"],
            ruta_relativa,
        ))
        factura_id = cur.fetchone()[0]

        # Insertar conceptos
        for c in datos["conceptos"]:
            cur.execute("""
                INSERT INTO factura_conceptos (
                    factura_id, clave_prod_serv, no_identificacion,
                    cantidad, clave_unidad, unidad, descripcion,
                    valor_unitario, importe, descuento
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                factura_id, c["clave_prod_serv"], c["no_identificacion"],
                c["cantidad"], c["clave_unidad"], c["unidad"], c["descripcion"],
                c["valor_unitario"], c["importe"], c["descuento"],
            ))

    return templates.TemplateResponse(
        request=request,
        name="facturas/_import_result.html",
        context={
            "ok": True,
            "folio": f"{datos['serie']}{datos['folio']}",
            "receptor": datos["nombre_receptor"],
            "total": datos["total"],
            "factura_id": factura_id,
            "user": user,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# SELECTOR DE COTIZACIONES (panel HTMX para vincular)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{factura_id}/selector-cotizaciones", response_class=HTMLResponse)
async def selector_cotizaciones(
    request: Request,
    factura_id: int,
    q: str = "",
):
    """Retorna el panel de búsqueda/selección de cotizaciones para vincular a esta factura."""
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)

    q = q.strip()
    params: list = [factura_id]
    buscar_clause = ""
    if q:
        buscar_clause = "AND (c.folio ILIKE %s OR COALESCE(cl.nombre_comercial,'') ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT c.id, c.folio, c.fecha, c.total, c.estado,
                   COALESCE(cl.nombre_comercial, '—') AS cliente,
                   cl.rfc
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.estado NOT IN ('Cancelada')
              AND c.id NOT IN (
                  SELECT fc.cotizacion_id
                  FROM factura_cotizaciones fc
                  WHERE fc.factura_id = %s
              )
              {buscar_clause}
            ORDER BY c.fecha DESC, c.id DESC
            LIMIT 50
        """, params)
        ccols = [d[0] for d in cur.description]
        cotizaciones = [_floats(dict(zip(ccols, r))) for r in cur.fetchall()]

        # Productos de todas las cotizaciones en una sola consulta
        if cotizaciones:
            cot_ids = [c["id"] for c in cotizaciones]
            cur.execute("""
                SELECT cd.cotizacion_id, p.codigo, p.nombre, p.unidad_medida,
                       cd.cantidad, cd.precio_unitario, cd.tiene_stock
                FROM cotizacion_detalle cd
                JOIN productos p ON p.id = cd.producto_id
                WHERE cd.cotizacion_id = ANY(%s)
                ORDER BY cd.cotizacion_id, cd.id
            """, (cot_ids,))
            pcols = [d[0] for d in cur.description]
            prods_raw = [_floats(dict(zip(pcols, r))) for r in cur.fetchall()]
        else:
            prods_raw = []

    # Agrupar productos por cotizacion_id
    from collections import defaultdict
    prods_por_cot: dict = defaultdict(list)
    for p in prods_raw:
        prods_por_cot[p["cotizacion_id"]].append(p)

    from core.constants import ESTADO_COLOR_CSS as ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="facturas/_selector_cotizaciones.html",
        context={
            "user":          user,
            "factura_id":    factura_id,
            "cotizaciones":  cotizaciones,
            "prods_por_cot": dict(prods_por_cot),
            "estado_color":  ESTADO_COLOR,
            "q":             q,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# VINCULAR COTIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{factura_id}/vincular", response_class=HTMLResponse)
async def vincular_cotizacion(
    request: Request,
    factura_id: int,
    cotizacion_id: int = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso para vincular facturas")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Verificar que existe la cotización
        cur.execute("SELECT folio FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        cot = cur.fetchone()
        if not cot:
            raise HTTPException(404, "Cotización no encontrada")

        # Insertar vínculo (ignorar si ya existe)
        cur.execute("""
            INSERT INTO factura_cotizaciones (factura_id, cotizacion_id)
            VALUES (%s, %s)
            ON CONFLICT (factura_id, cotizacion_id) DO NOTHING
        """, (factura_id, cotizacion_id))

        # Recargar vinculadas para HTMX swap
        cur.execute("""
            SELECT cot.id, cot.folio, cot.fecha, cot.total, cot.estado,
                   fc.fecha_vinculo, fc.notas
            FROM factura_cotizaciones fc
            JOIN cotizaciones cot ON cot.id = fc.cotizacion_id
            WHERE fc.factura_id = %s
            ORDER BY cot.fecha DESC
        """, (factura_id,))
        vcols      = [d[0] for d in cur.description]
        vinculadas = [_floats(dict(zip(vcols, r))) for r in cur.fetchall()]

    from core.constants import ESTADO_COLOR_CSS as ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="facturas/_vinculadas.html",
        context={"vinculadas": vinculadas, "estado_color": ESTADO_COLOR,
                 "factura_id": factura_id, "user": user},
    )


# ─────────────────────────────────────────────────────────────────────────────
# DESVINCULAR COTIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# SELECTOR DE COMPRAS (panel HTMX para vincular compra existente)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{factura_id}/selector-compras", response_class=HTMLResponse)
async def selector_compras(
    request: Request,
    factura_id: int,
    q: str = "",
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403)

    q = q.strip()
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Obtener RFC del emisor de la factura para pre-filtrar
        cur.execute("SELECT rfc_emisor FROM facturas WHERE id = %s", (factura_id,))
        frow = cur.fetchone()
        rfc_emisor = frow[0] if frow else None

        params: list = []
        where_parts = ["c.factura_xml_id IS NULL"]

        if q:
            where_parts.append(
                "(c.folio ILIKE %s OR COALESCE(p.nombre,'') ILIKE %s OR c.ticket_referencia ILIKE %s)"
            )
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]

        where_sql = " AND ".join(where_parts)

        cur.execute(f"""
            SELECT c.id, c.folio, c.fecha_compra, c.total, c.ticket_referencia,
                   COALESCE(p.nombre, '—') AS proveedor,
                   COALESCE(p.rfc, '') AS proveedor_rfc
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            WHERE {where_sql}
            ORDER BY c.fecha_compra DESC, c.id DESC
            LIMIT 50
        """, params)
        ccols  = [d[0] for d in cur.description]
        compras = [_floats(dict(zip(ccols, r))) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="facturas/_selector_compras.html",
        context={
            "user":       user,
            "factura_id": factura_id,
            "compras":    compras,
            "rfc_emisor": rfc_emisor,
            "q":          q,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAPEO DE CONCEPTOS A PRODUCTOS DEL CATÁLOGO
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{factura_id}/mapeo-conceptos", response_class=JSONResponse)
async def mapeo_conceptos(request: Request, factura_id: int):
    """Retorna los conceptos del XML con el producto detectado por no_identificacion."""
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, clave_prod_serv, no_identificacion, cantidad,
                   clave_unidad, unidad, descripcion, valor_unitario, importe
            FROM factura_conceptos
            WHERE factura_id = %s
            ORDER BY id
        """, (factura_id,))
        cols      = [d[0] for d in cur.description]
        conceptos = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

        resultado = []
        for idx, c in enumerate(conceptos):
            producto_id, producto_nombre, producto_codigo = None, None, None
            if c.get("no_identificacion"):
                cur.execute("""
                    SELECT id, nombre, codigo
                    FROM productos
                    WHERE codigo = %s
                    LIMIT 1
                """, (c["no_identificacion"],))
                p = cur.fetchone()
                if p:
                    producto_id, producto_nombre, producto_codigo = p[0], p[1], p[2]
            resultado.append({
                "idx":             idx,
                "concepto_id":     c["id"],
                "descripcion":     c["descripcion"],
                "cantidad":        c["cantidad"],
                "valor_unitario":  c["valor_unitario"],
                "importe":         c["importe"],
                "unidad":          c["unidad"] or c.get("clave_unidad", ""),
                "producto_id":     producto_id,
                "producto_nombre": producto_nombre,
                "producto_codigo": producto_codigo,
            })

    return JSONResponse(resultado)


# ─────────────────────────────────────────────────────────────────────────────
# CREAR COMPRA DESDE FACTURA (inline, sin salir de la pantalla)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{factura_id}/crear-compra", response_class=JSONResponse)
async def crear_compra_desde_factura(request: Request, factura_id: int):
    """Crea un registro de compra a partir de los conceptos de la factura."""
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    body = await request.json()
    mapeo = body.get("mapeo", [])  # [{concepto_idx, producto_id}, ...]

    if not mapeo:
        raise HTTPException(status_code=400, detail="Mapeo de productos vacío")

    with get_pool_empresa(user["empresa_db"]).conexion() as (conn, cur):
        # Verificar factura
        cur.execute("SELECT tipo, rfc_emisor, fecha, subtotal, iva, total FROM facturas WHERE id = %s", (factura_id,))
        f = cur.fetchone()
        if not f:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        tipo, rfc_emisor, fecha_fac, subtotal_fac, iva_fac, total_fac = f
        if tipo != "E":
            raise HTTPException(status_code=400, detail="Solo facturas de Egreso pueden convertirse en compra")

        # Verificar que no exista ya una compra vinculada
        cur.execute("SELECT id FROM compras WHERE factura_xml_id = %s LIMIT 1", (factura_id,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Esta factura ya tiene una compra registrada")

        # Cargar conceptos indexados
        cur.execute("""
            SELECT id, descripcion, cantidad, valor_unitario, importe, no_identificacion
            FROM factura_conceptos
            WHERE factura_id = %s
            ORDER BY id
        """, (factura_id,))
        conceptos = cur.fetchall()
        conceptos_map = {idx: row for idx, row in enumerate(conceptos)}

        # Validar que todos los productos existan
        for item in mapeo:
            pid = item.get("producto_id")
            if not pid:
                raise HTTPException(status_code=400, detail="Todos los conceptos deben tener producto asignado")
            cur.execute("SELECT id FROM productos WHERE id = %s", (pid,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"Producto {pid} no encontrado")

        # Buscar proveedor por RFC
        proveedor_id = None
        if rfc_emisor:
            cur.execute("SELECT id FROM proveedores WHERE rfc = %s LIMIT 1", (rfc_emisor,))
            p = cur.fetchone()
            if p:
                proveedor_id = p[0]

        # Generar folio CMP
        año = date.today().year
        cur.execute("SELECT COUNT(*) FROM compras WHERE folio LIKE %s", (f"CMP-{año}-%",))
        n = cur.fetchone()[0] + 1
        folio = f"CMP-{año}-{n:04d}"

        # Crear cabecera de la compra
        subtotal_g = Decimal(str(subtotal_fac or 0))
        iva_g      = Decimal(str(iva_fac or 0))
        total_g    = Decimal(str(total_fac or 0))

        cur.execute("""
            INSERT INTO compras (folio, proveedor_id, fecha_compra, subtotal, iva, total,
                                  ticket_referencia, factura_xml_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            folio, proveedor_id,
            fecha_fac or date.today().isoformat(),
            float(subtotal_g), float(iva_g), float(total_g),
            None, factura_id,
        ))
        compra_id = cur.fetchone()[0]

        # Crear detalle por cada concepto mapeado
        for item in mapeo:
            idx        = item["concepto_idx"]
            producto_id = item["producto_id"]
            concepto   = conceptos_map.get(idx)
            if not concepto:
                continue
            _, desc, cantidad, costo_u, costo_total, _ = concepto
            cantidad   = float(cantidad or 0)
            costo_u    = float(costo_u or 0)
            costo_total = float(costo_total or 0)

            cur.execute("""
                INSERT INTO compra_detalle (compra_id, producto_id, cantidad, costo_unitario, costo_total)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (compra_id, producto_id, cantidad, costo_u, costo_total))
            detalle_id = cur.fetchone()[0]

            # Todo va a stock general (el usuario asigna a cotizaciones desde el detalle de compra)
            cur.execute("""
                INSERT INTO compra_detalle_cotizacion (compra_detalle_id, cotizacion_id, cantidad)
                VALUES (%s, NULL, %s)
            """, (detalle_id, cantidad))

            # Actualizar stock y costo promedio ponderado
            cur.execute("SELECT COALESCE(stock_actual, 0), COALESCE(costo_promedio, 0) FROM productos WHERE id = %s", (producto_id,))
            stock_antes, costo_prom_ant = cur.fetchone()
            stock_antes      = float(stock_antes)
            costo_prom_ant   = float(costo_prom_ant)
            stock_despues    = stock_antes + cantidad
            denominador      = stock_antes + cantidad
            if denominador > 0:
                nuevo_prom = (stock_antes * costo_prom_ant + cantidad * costo_u) / denominador
            else:
                nuevo_prom = costo_u

            cur.execute(
                "UPDATE productos SET stock_actual = %s, costo_promedio = %s WHERE id = %s",
                (stock_despues, round(nuevo_prom, 4), producto_id),
            )

            # Registrar precio en historial del producto
            cur.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente, proveedor_id)
                VALUES (%s, %s, %s, %s, 'compra', %s)
            """, (
                producto_id,
                costo_u,
                fecha_fac or date.today().isoformat(),
                f"Compra {folio}",
                proveedor_id,
            ))

            cur.execute("""
                INSERT INTO movimientos_stock
                    (producto_id, tipo, motivo, cantidad, stock_antes, stock_despues, referencia, usuario)
                VALUES (%s, 'entrada', 'compra', %s, %s, %s, %s, %s)
            """, (producto_id, cantidad, stock_antes, stock_despues, folio, user.get("username", "")))

    alerta_proveedor = None
    if not proveedor_id and rfc_emisor:
        alerta_proveedor = f"RFC {rfc_emisor} no encontrado en el catálogo de proveedores. Vincula el proveedor manualmente desde la compra."

    return JSONResponse({
        "ok": True,
        "compra_id": compra_id,
        "folio": folio,
        "alerta_proveedor": alerta_proveedor,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VINCULAR COMPRA EXISTENTE
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{factura_id}/vincular-compra", response_class=HTMLResponse)
async def vincular_compra(
    request:   Request,
    factura_id: int,
    compra_id:  int = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id FROM compras WHERE id = %s", (compra_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Compra no encontrada")
        cur.execute(
            "UPDATE compras SET factura_xml_id = %s WHERE id = %s AND factura_xml_id IS NULL",
            (factura_id, compra_id),
        )

    return RedirectResponse(f"/facturas/{factura_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# CAMBIAR TIPO
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{factura_id}/tipo", response_class=HTMLResponse)
async def cambiar_tipo(
    request: Request,
    factura_id: int,
    tipo: str = Form(""),
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if tipo not in TIPO_LABEL:
        raise HTTPException(status_code=400, detail="Tipo inválido")
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("UPDATE facturas SET tipo=%s WHERE id=%s", (tipo, factura_id))
    return RedirectResponse(f"/facturas/{factura_id}", status_code=303)


@router.delete("/{factura_id}/vincular/{cotizacion_id}", response_class=HTMLResponse)
async def desvincular_cotizacion(
    request: Request,
    factura_id: int,
    cotizacion_id: int,
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso para desvincular facturas")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "DELETE FROM factura_cotizaciones WHERE factura_id=%s AND cotizacion_id=%s",
            (factura_id, cotizacion_id),
        )
        cur.execute("""
            SELECT cot.id, cot.folio, cot.fecha, cot.total, cot.estado,
                   fc.fecha_vinculo, fc.notas
            FROM factura_cotizaciones fc
            JOIN cotizaciones cot ON cot.id = fc.cotizacion_id
            WHERE fc.factura_id = %s
            ORDER BY cot.fecha DESC
        """, (factura_id,))
        vcols      = [d[0] for d in cur.description]
        vinculadas = [_floats(dict(zip(vcols, r))) for r in cur.fetchall()]

    from core.constants import ESTADO_COLOR_CSS as ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="facturas/_vinculadas.html",
        context={"vinculadas": vinculadas, "estado_color": ESTADO_COLOR,
                 "factura_id": factura_id, "user": user},
    )
