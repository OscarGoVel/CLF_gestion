# -*- coding: utf-8 -*-
"""
web_app/routers/estado_cuenta.py
Estado de Cuenta de Pedidos — módulo web.
Solo accesible para rol Administrador.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.rbac import require_rol

router = APIRouter(prefix="/estado-cuenta")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

_NAV_LINK = "px-4 h-full flex items-center text-xs text-navy-400 hover:bg-navy-500 hover:text-white transition-colors shrink-0"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(v) -> float:
    if isinstance(v, Decimal):
        return float(v)
    return float(v) if v is not None else 0.0


def _dec_row(row: dict) -> dict:
    return {k: _f(v) if isinstance(v, Decimal) else v for k, v in row.items()}


def _cols(cur) -> list:
    return [d[0] for d in cur.description]


def _estado_label(estado: str) -> str:
    mapa = {
        "Pendiente":              "⏳ Pendiente",
        "Programada":             "📅 Programada",
        "Parcialmente Entregada": "📦 Parcialmente Entregada",
        "Entregada":              "✅ Entregada",
        "Facturada":              "🧾 Facturada",
        "Pagada":                 "💰 Pagada",
        "Cancelada":              "❌ Cancelada",
    }
    return mapa.get(estado, estado)


def _estado_color(estado: str) -> str:
    mapa = {
        "Pendiente":              "bg-yellow-50",
        "Programada":             "bg-blue-50",
        "Parcialmente Entregada": "bg-purple-50",
        "Entregada":              "bg-green-50",
        "Facturada":              "bg-cyan-50",
        "Pagada":                 "bg-emerald-100",
        "Cancelada":              "bg-gray-50 opacity-70",
    }
    return mapa.get(estado, "")


def _cargar_corporativos(empresa_db: str) -> list:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT id, nombre FROM corporativos ORDER BY nombre")
        return [dict(zip(_cols(cur), r)) for r in cur.fetchall()]


def _cargar_clientes(empresa_db: str, corporativo_id: int | None = None) -> list:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        if corporativo_id:
            cur.execute(
                "SELECT id, nombre_comercial FROM clientes "
                "WHERE corporativo_id = %s AND activo = TRUE ORDER BY nombre_comercial",
                (corporativo_id,),
            )
        else:
            cur.execute(
                "SELECT id, nombre_comercial FROM clientes "
                "WHERE activo = TRUE ORDER BY nombre_comercial"
            )
        return [dict(zip(_cols(cur), r)) for r in cur.fetchall()]


def _build_query(filtros: dict) -> tuple[str, list]:
    """Construye la cláusula WHERE y params para la consulta principal."""
    where, params = ["1=1"], []

    if filtros.get("corporativo_id"):
        where.append("cl.corporativo_id = %s")
        params.append(int(filtros["corporativo_id"]))
    elif filtros.get("cliente_nombre"):
        where.append("cl.nombre_comercial = %s")
        params.append(filtros["cliente_nombre"])

    if filtros.get("estado") and filtros["estado"] != "Todos":
        where.append("c.estado = %s")
        params.append(filtros["estado"])

    if filtros.get("desde"):
        where.append("c.fecha >= %s")
        params.append(filtros["desde"])

    if filtros.get("hasta"):
        where.append("c.fecha <= %s")
        params.append(filtros["hasta"])

    return " AND ".join(where), params


def _enriquecer_seguimiento(empresa_db: str, filas: list) -> list:
    """Sobreescribe OC/Factura con datos de seguimiento_etapas si los hay."""
    if not filas:
        return filas
    ids = [f["id"] for f in filas]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            """
            SELECT cotizacion_id, etapa, referencia, fecha_etapa
            FROM seguimiento_etapas
            WHERE cotizacion_id = ANY(%s)
              AND etapa IN ('Orden de Compra', 'Facturada')
            """,
            (ids,),
        )
        seg = {}
        for row in cur.fetchall():
            cid, etapa, ref, fecha = row
            seg.setdefault(cid, {})[etapa] = (ref, fecha)

    for f in filas:
        oc = seg.get(f["id"], {}).get("Orden de Compra")
        if oc:
            f["orden_compra"] = oc[0]
            f["fecha_orden_compra"] = oc[1]
        fact = seg.get(f["id"], {}).get("Facturada")
        if fact:
            f["numero_factura"] = fact[0]
            f["fecha_factura"] = fact[1]

    return filas


# ── Página principal ──────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def index(
    request: Request,
    user: dict = Depends(require_rol("Administrador")),
    corporativo_id: int = 0,
    cliente_nombre: str = "",
    desde: str = "",
    hasta: str = "",
    estado: str = "Todos",
):
    hoy = date.today()
    desde = desde or f"{hoy.year}-01-01"
    hasta = hasta or hoy.isoformat()

    corporativos = _cargar_corporativos(user["empresa_db"])
    clientes = _cargar_clientes(user["empresa_db"], corporativo_id or None)

    filtros = dict(
        corporativo_id=corporativo_id or None,
        cliente_nombre=cliente_nombre,
        desde=desde,
        hasta=hasta,
        estado=estado,
    )

    filas, totales = _consultar_datos(user["empresa_db"], filtros)

    return templates.TemplateResponse(
        request=request,
        name="estado_cuenta/index.html",
        context={
            "user":           user,
            "corporativos":   corporativos,
            "clientes":       clientes,
            "filas":          filas,
            "totales":        totales,
            "filtros":        filtros,
            "corporativo_id": corporativo_id,
            "cliente_nombre": cliente_nombre,
            "desde":          desde,
            "hasta":          hasta,
            "estado":         estado,
            "estado_color":   _estado_color,
            "estado_label":   _estado_label,
            "ESTADOS":        ["Todos", "Pendiente", "Programada",
                               "Parcialmente Entregada", "Entregada",
                               "Facturada", "Pagada", "Cancelada"],
        },
    )


def _consultar_datos(empresa_db: str, filtros: dict) -> tuple[list, dict]:
    where, params = _build_query(filtros)
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            f"""
            SELECT c.id, c.folio, c.fecha,
                   cl.nombre_comercial AS cliente,
                   c.total, c.estado, c.fecha_entrega,
                   c.monto_entregado, c.orden_compra, c.fecha_orden_compra,
                   c.numero_factura, c.fecha_factura, c.monto_facturado,
                   c.fecha_pago, c.monto_pagado
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE {where}
            ORDER BY c.fecha DESC, c.folio DESC
            """,
            params,
        )
        cols = _cols(cur)
        filas = [_dec_row(dict(zip(cols, r))) for r in cur.fetchall()]

    filas = _enriquecer_seguimiento(empresa_db, filas)

    _ESTADOS_ACTIVOS    = {'Programada', 'Parcialmente Entregada', 'Entregada', 'Facturada', 'Pagada'}
    _ESTADOS_SOLICITADO = _ESTADOS_ACTIVOS | {'Pendiente'}  # todo excepto Cancelada

    # Calcular saldo y añadir helpers de visualización
    for f in filas:
        f["saldo"] = round(f["total"] - (f["monto_pagado"] or 0.0), 2)
        f["estado_label"] = _estado_label(f["estado"])
        f["color_cls"]    = _estado_color(f["estado"])

    # Sección 1 — Monto solicitado: todas las no canceladas
    sol_filas = [f for f in filas if f["estado"] in _ESTADOS_SOLICITADO]
    sol_n     = len(sol_filas)
    sol_total = sum(f["total"] for f in sol_filas)

    # Sección 2 — Balance: solo estados activos (cliente autorizó)
    act_filas  = [f for f in filas if f["estado"] in _ESTADOS_ACTIVOS]
    comprometido = sum(f["total"]            for f in act_filas)
    cobrado      = sum(f["monto_pagado"] or 0 for f in act_filas)
    saldo_tot    = sum(f["saldo"]            for f in act_filas)

    totales = {
        "n":              len(filas),
        # Sección 1
        "sol_n":          sol_n,
        "sol_total":      round(sol_total,    2),
        # Sección 2
        "comprometido":   round(comprometido, 2),
        "cobrado":        round(cobrado,      2),
        "saldo":          round(saldo_tot,    2),
        # Compat. legacy
        "total":          round(sol_total,    2),
    }
    return filas, totales


# ── HTMX: recargar solo tabla ─────────────────────────────────────────────────

@router.get("/tabla", response_class=HTMLResponse)
async def tabla_parcial(
    request: Request,
    user: dict = Depends(require_rol("Administrador")),
    corporativo_id: int = 0,
    cliente_nombre: str = "",
    desde: str = "",
    hasta: str = "",
    estado: str = "Todos",
):
    hoy = date.today()
    desde = desde or f"{hoy.year}-01-01"
    hasta = hasta or hoy.isoformat()

    filtros = dict(
        corporativo_id=corporativo_id or None,
        cliente_nombre=cliente_nombre,
        desde=desde, hasta=hasta, estado=estado,
    )
    filas, totales = _consultar_datos(user["empresa_db"], filtros)

    return templates.TemplateResponse(
        request=request,
        name="estado_cuenta/_tabla.html",
        context={
            "user": user, "filas": filas, "totales": totales,
            "estado_color": _estado_color, "estado_label": _estado_label,
        },
    )


# ── PDF ───────────────────────────────────────────────────────────────────────

@router.post("/pdf")
async def generar_pdf(
    request: Request,
    user: dict = Depends(require_rol("Administrador")),
    corporativo_id: int = Form(0),
    cliente_nombre: str = Form(""),
    desde: str = Form(""),
    hasta: str = Form(""),
    estado: str = Form("Todos"),
):
    hoy = date.today()
    desde = desde or f"{hoy.year}-01-01"
    hasta = hasta or hoy.isoformat()

    filtros = dict(
        corporativo_id=corporativo_id or None,
        cliente_nombre=cliente_nombre,
        desde=desde, hasta=hasta, estado=estado,
    )

    from web_app.pdf_estado_cuenta import generar_pdf_estado_cuenta
    try:
        pdf_bytes = generar_pdf_estado_cuenta(user["empresa_db"], filtros)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    nombre = cliente_nombre or "Consolidado"
    filename = f"EstadoCuenta_{nombre}_{hoy.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Corporativos: AJAX — clientes filtrados ───────────────────────────────────

@router.get("/clientes-por-corporativo", response_class=HTMLResponse)
async def clientes_por_corp(
    request: Request,
    user: dict = Depends(require_rol("Administrador")),
    corporativo_id: int = 0,
):
    clientes = _cargar_clientes(user["empresa_db"], corporativo_id or None)
    opts = '<option value="">Todos</option>'
    for c in clientes:
        opts += f'<option value="{c["nombre_comercial"]}">{c["nombre_comercial"]}</option>'
    return HTMLResponse(opts)


# ── Corporativos: CRUD ────────────────────────────────────────────────────────

@router.get("/corporativos/datos")
async def corporativos_datos(
    request: Request,
    user: dict = Depends(require_rol("Administrador")),
):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT id, nombre FROM corporativos ORDER BY nombre")
        corps = [dict(zip(_cols(cur), r)) for r in cur.fetchall()]

        cur.execute(
            "SELECT id, nombre_comercial, corporativo_id "
            "FROM clientes WHERE activo = TRUE ORDER BY nombre_comercial"
        )
        clientes = [dict(zip(_cols(cur), r)) for r in cur.fetchall()]

    return JSONResponse({"corporativos": corps, "clientes": clientes})


@router.post("/corporativos")
async def crear_corporativo(
    request: Request,
    user: dict = Depends(require_rol("Administrador")),
    nombre: str = Form(...),
):
    nombre = nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre requerido")
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "INSERT INTO corporativos (nombre) VALUES (%s) "
            "ON CONFLICT (nombre) DO NOTHING RETURNING id",
            (nombre,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Ya existe un corporativo con ese nombre")
        new_id = row[0]
    return JSONResponse({"id": new_id, "nombre": nombre})


@router.delete("/corporativos/{corp_id}")
async def eliminar_corporativo(
    request: Request,
    corp_id: int,
    user: dict = Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE clientes SET corporativo_id = NULL WHERE corporativo_id = %s",
            (corp_id,),
        )
        cur.execute("DELETE FROM corporativos WHERE id = %s", (corp_id,))
    return JSONResponse({"ok": True})


@router.post("/corporativos/{corp_id}/clientes/{cliente_id}")
async def asignar_cliente(
    request: Request,
    corp_id: int,
    cliente_id: int,
    user: dict = Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE clientes SET corporativo_id = %s WHERE id = %s",
            (corp_id, cliente_id),
        )
    return JSONResponse({"ok": True})


@router.delete("/corporativos/{corp_id}/clientes/{cliente_id}")
async def quitar_cliente(
    request: Request,
    corp_id: int,
    cliente_id: int,
    user: dict = Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE clientes SET corporativo_id = NULL "
            "WHERE id = %s AND corporativo_id = %s",
            (cliente_id, corp_id),
        )
    return JSONResponse({"ok": True})
