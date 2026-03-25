# -*- coding: utf-8 -*-
"""
web_app/routers/cotizaciones.py
Seccion de Cotizaciones: lista, detalle y cambio de estado.
"""

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web_app.database import pool_empresa
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


def _cargar_lista(estado: str, buscar: str, pagina: int) -> dict:
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

    with pool_empresa.conexion() as (_, cur):
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

    data       = _cargar_lista(estado, buscar, pagina)
    total_pags = max(1, (data["total"] + POR_PAGINA - 1) // POR_PAGINA)

    # Totales por estado para los chips del encabezado
    with pool_empresa.conexion() as (_, cur):
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


@router.get("/{cot_id}", response_class=HTMLResponse)
async def detalle(request: Request, cot_id: int):
    user = get_usuario_actual(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/")

    with pool_empresa.conexion() as (_, cur):
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
                   p.codigo, p.nombre, p.unidad_medida,
                   cd.cantidad, cd.precio_unitario,
                   cd.subtotal, cd.iva, cd.total,
                   p.aplica_iva
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
        """, (cot_id,))
        dcols    = [d[0] for d in cur.description]
        productos = [_dec_to_float(dict(zip(dcols, r))) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="cotizaciones/detalle.html",
        context={
            "user":         user,
            "cot":          cot,
            "productos":    productos,
            "estados":      ESTADOS,
            "estado_color": ESTADO_COLOR,
        },
    )


@router.post("/{cot_id}/estado", response_class=HTMLResponse)
async def cambiar_estado(
    request: Request,
    cot_id: int,
    nuevo_estado: str = Form(...),
):
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(status_code=401)
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso para cambiar estado")
    if nuevo_estado not in ESTADOS:
        raise HTTPException(status_code=400, detail="Estado no valido")

    with pool_empresa.conexion() as (_, cur):
        cur.execute(
            "UPDATE cotizaciones SET estado = %s WHERE id = %s",
            (nuevo_estado, cot_id),
        )

    # HTMX: devuelve solo el badge actualizado
    bg, fg = ESTADO_COLOR.get(nuevo_estado, ("bg-gray-100", "text-gray-600"))
    return HTMLResponse(
        f'<span class="px-2.5 py-1 rounded-full text-xs font-bold {bg} {fg}">'
        f'{nuevo_estado}</span>'
    )
