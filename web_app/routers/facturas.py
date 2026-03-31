# -*- coding: utf-8 -*-
"""
web_app/routers/facturas.py
Módulo de Facturas: lista, detalle, importar XML, vincular cotización.
"""

import os
import shutil
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
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
                   COUNT(fc.cotizacion_id) AS num_cotizaciones
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

    from web_app.routers.cotizaciones import ESTADO_COLOR
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

    from web_app.routers.cotizaciones import ESTADO_COLOR
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

    from web_app.routers.cotizaciones import ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="facturas/_vinculadas.html",
        context={"vinculadas": vinculadas, "estado_color": ESTADO_COLOR,
                 "factura_id": factura_id, "user": user},
    )
