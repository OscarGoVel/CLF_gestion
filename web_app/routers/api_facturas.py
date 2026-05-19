# -*- coding: utf-8 -*-
"""
web_app/routers/api_facturas.py
/api/facturas — endpoints JSON para el SPA React.
"""

from decimal import Decimal
from pathlib import Path

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from web_app.cfdi import parsear_cfdi_bytes
from web_app.database import get_pool_empresa, get_empresas
from web_app.dependencies import get_usuario_api

_BASE = Path(__file__).parent.parent.parent
XML_DIR = _BASE / "facturas_xml"
XML_DIR.mkdir(exist_ok=True)

router = APIRouter(prefix="/api/facturas", tags=["api"])

POR_PAGINA = 30

TIPO_LABEL = {"I": "Ingreso", "E": "Egreso", "T": "Traslado", "N": "Nómina", "P": "Pago"}


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
    tipo: List[str] = Query([]),
    sin_vincular: bool = Query(False),
    pagina: int = Query(1, ge=1),
    user: dict = Depends(get_usuario_api),
):
    from fastapi import HTTPException
    if user.get("rol") == "Almacenista":
        raise HTTPException(status_code=403, detail="Sin acceso")

    empresa_db = user["empresa_db"]
    where, params = [], []
    if q:
        where.append("(f.folio_factura ILIKE %s OR f.rfc_receptor ILIKE %s "
                     "OR f.nombre_receptor ILIKE %s OR f.nombre_emisor ILIKE %s "
                     "OR f.uuid ILIKE %s)")
        params += [f"%{q}%"] * 5
    if tipo:
        placeholders = ",".join(["%s"] * len(tipo))
        where.append(f"f.tipo IN ({placeholders})")
        params.extend(tipo)
    if sin_vincular:
        where.append("f.tipo = 'I' AND (SELECT COUNT(*) FROM factura_cotizaciones fc2 WHERE fc2.factura_id = f.id) = 0")
    filtro = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (pagina - 1) * POR_PAGINA

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(f"""
            SELECT COUNT(*) FROM facturas f {filtro}
        """, params or None)
        total = cur.fetchone()[0]

        cur.execute(f"""
            SELECT f.id,
                   COALESCE(f.serie,'') || COALESCE(f.folio_factura,'') AS folio,
                   f.fecha, f.fecha_timbrado,
                   f.rfc_emisor, f.nombre_emisor,
                   f.rfc_receptor, f.nombre_receptor,
                   f.subtotal, f.iva, f.total, f.tipo,
                   f.metodo_pago, f.moneda, f.uuid,
                   COUNT(fc.cotizacion_id)  AS num_cotizaciones,
                   (SELECT id FROM compras WHERE factura_xml_id = f.id LIMIT 1) AS compra_id
            FROM facturas f
            LEFT JOIN factura_cotizaciones fc ON fc.factura_id = f.id
            {filtro}
            GROUP BY f.id
            ORDER BY f.fecha_timbrado DESC NULLS LAST, f.id DESC
            LIMIT {POR_PAGINA} OFFSET {offset}
        """, params or None)
        facturas = _rows(cur)

        cur.execute("SELECT DISTINCT tipo FROM facturas WHERE tipo IS NOT NULL ORDER BY tipo")
        tipos = [{"value": r[0], "label": TIPO_LABEL.get(r[0], r[0])} for r in cur.fetchall()]

    for f in facturas:
        f["tipo_label"] = TIPO_LABEL.get(f.get("tipo"), f.get("tipo", ""))

    total_pags = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)
    return JSONResponse({"facturas": facturas, "total": total,
                         "pagina": pagina, "total_pags": total_pags,
                         "tipos": tipos})


@router.get("/{factura_id}")
async def detalle(factura_id: int, user: dict = Depends(get_usuario_api)):
    from fastapi import HTTPException
    empresa_db = user["empresa_db"]

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT f.*,
                   (SELECT id FROM compras WHERE factura_xml_id = f.id LIMIT 1) AS compra_id
            FROM facturas f WHERE f.id = %s
        """, (factura_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404)
        cols = [d[0] for d in cur.description]
        factura = {k: _serial(v) for k, v in zip(cols, row)}
        factura["tipo_label"] = TIPO_LABEL.get(factura.get("tipo"), factura.get("tipo", ""))

        cur.execute("""
            SELECT descripcion, no_identificacion, cantidad,
                   unidad, valor_unitario, importe
            FROM factura_conceptos WHERE factura_id = %s ORDER BY id
        """, (factura_id,))
        conceptos = _rows(cur)

        cur.execute("""
            SELECT cot.id, cot.folio, cot.estado, cot.total,
                   COALESCE(cl.nombre_comercial,'—') AS cliente
            FROM factura_cotizaciones fc
            JOIN cotizaciones cot ON cot.id = fc.cotizacion_id
            LEFT JOIN clientes cl ON cl.id = cot.cliente_id
            WHERE fc.factura_id = %s
        """, (factura_id,))
        cotizaciones = _rows(cur)

    return JSONResponse({"factura": factura, "conceptos": conceptos, "cotizaciones": cotizaciones})


# ── POST /api/facturas/importar ───────────────────────────────────────────────

@router.post("/importar")
async def importar_xml(
    archivo: UploadFile = File(...),
    user: dict = Depends(get_usuario_api),
):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")

    contenido = await archivo.read()
    try:
        datos = parsear_cfdi_bytes(contenido)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    uuid = datos["uuid"]

    # Si la empresa es el receptor → tipo Egreso
    empresa_cfg = next((e for e in get_empresas() if e["id"] == user.get("empresa_id")), None)
    rfc_empresa = (empresa_cfg.get("rfc") or "").upper().strip() if empresa_cfg else ""
    rfc_receptor = (datos.get("rfc_receptor") or "").upper().strip()
    if rfc_empresa and rfc_receptor == rfc_empresa:
        datos["tipo"] = "E"

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT id FROM facturas WHERE uuid = %s", (uuid,))
        existing = cur.fetchone()
        if existing:
            existing_id = existing[0]
            cur.execute(
                "SELECT descripcion, cantidad, valor_unitario, importe, descuento FROM factura_conceptos"
                " WHERE factura_id = %s ORDER BY id",
                (existing_id,),
            )
            conceptos_ex = [
                {
                    "descripcion": r[0], "cantidad": float(r[1] or 0),
                    "valor_unitario": float(r[2] or 0),
                    "importe": float(r[3] or 0), "descuento": float(r[4] or 0),
                }
                for r in cur.fetchall()
            ]
            return JSONResponse({
                "id": existing_id,
                "already_exists": True,
                "folio": f"{datos['serie']}{datos['folio']}",
                "emisor": datos["nombre_emisor"],
                "rfc_emisor": datos["rfc_emisor"],
                "fecha": datos["fecha"],
                "total": float(datos["total"]),
                "tipo": datos["tipo"],
                "tipo_label": TIPO_LABEL.get(datos["tipo"], datos["tipo"]),
                "uuid": uuid,
                "conceptos": conceptos_ex,
            })

        nombre_archivo = archivo.filename or f"{uuid[:8]}.xml"
        ruta_destino = XML_DIR / nombre_archivo
        if ruta_destino.exists():
            ruta_destino = XML_DIR / f"{ruta_destino.stem}_{uuid[:8]}.xml"
        ruta_destino.write_bytes(contenido)
        ruta_relativa = f"facturas_xml/{ruta_destino.name}"

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

    return JSONResponse({
        "id": factura_id,
        "already_exists": False,
        "folio": f"{datos['serie']}{datos['folio']}",
        "receptor": datos["nombre_receptor"],
        "emisor": datos["nombre_emisor"],
        "rfc_emisor": datos["rfc_emisor"],
        "fecha": datos["fecha"],
        "total": float(datos["total"]),
        "tipo": datos["tipo"],
        "tipo_label": TIPO_LABEL.get(datos["tipo"], datos["tipo"]),
        "uuid": uuid,
        "conceptos": [
            {
                "descripcion": c["descripcion"],
                "cantidad": float(c["cantidad"] or 0),
                "valor_unitario": float(c["valor_unitario"] or 0),
                "importe": float(c["importe"] or 0),
                "descuento": float(c["descuento"] or 0),
            }
            for c in datos["conceptos"]
        ],
    }, status_code=201)


# ── GET /api/facturas/{id}/sugerencias ────────────────────────────────────────

@router.get("/{factura_id}/sugerencias")
async def sugerencias_fuzzy(factura_id: int, user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT rfc_receptor, total FROM facturas WHERE id = %s", (factura_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        rfc_receptor, total_factura = row
        if not rfc_receptor:
            return JSONResponse({"sugerencias": []})
        total_f = float(total_factura or 0)

        cur.execute("""
            SELECT cot.id, cot.folio, cot.estado, cot.total,
                   COALESCE(cl.nombre_comercial, cl.nombre_fiscal, '—') AS cliente,
                   ABS(cot.total - %s) / NULLIF(%s, 0) * 100 AS diff_pct
            FROM cotizaciones cot
            JOIN clientes cl ON cl.id = cot.cliente_id
            WHERE UPPER(COALESCE(cl.rfc, '')) = UPPER(%s)
              AND cot.estado IN ('Entregada', 'Facturada')
              AND cot.total BETWEEN %s AND %s
              AND cot.id NOT IN (
                  SELECT cotizacion_id FROM factura_cotizaciones WHERE factura_id = %s
              )
            ORDER BY diff_pct ASC
            LIMIT 10
        """, (
            total_f, total_f, rfc_receptor,
            total_f * 0.85, total_f * 1.15,
            factura_id,
        ))
        sugerencias = [
            {
                "cot_id":   r[0],
                "folio":    r[1],
                "estado":   r[2],
                "total":    float(r[3] or 0),
                "cliente":  r[4],
                "diff_pct": round(float(r[5] or 0), 1),
            }
            for r in cur.fetchall()
        ]
    return JSONResponse({"sugerencias": sugerencias})


# ── POST /api/facturas/{id}/vincular ─────────────────────────────────────────

from pydantic import BaseModel as _BM

class VincularIn(_BM):
    cotizacion_id: int

@router.post("/{factura_id}/vincular")
async def vincular(factura_id: int, body: VincularIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT tipo, COALESCE(serie,'') || COALESCE(folio_factura,'') FROM facturas WHERE id = %s", (factura_id,))
        fac_row = cur.fetchone()
        if not fac_row:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        tipo_factura, folio_factura = fac_row

        cur.execute("SELECT estado FROM cotizaciones WHERE id = %s", (body.cotizacion_id,))
        cot_row = cur.fetchone()
        if not cot_row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        estado_cot = cot_row[0]

        cur.execute("""
            INSERT INTO factura_cotizaciones (factura_id, cotizacion_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (factura_id, body.cotizacion_id))

        if tipo_factura == 'I' and estado_cot == 'Entregada':
            cur.execute("""
                UPDATE cotizaciones
                   SET estado = 'Facturada',
                       numero_factura = COALESCE(NULLIF(%s,''), numero_factura)
                 WHERE id = %s
            """, (folio_factura, body.cotizacion_id))
            from web_app.cache import cache as _cache
            _cache.invalidar(f"dashboard:{empresa_db}")

    return JSONResponse({"ok": True})
