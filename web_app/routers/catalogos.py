# -*- coding: utf-8 -*-
"""
web_app/routers/catalogos.py
Seccion Catalogos: Clientes, Productos y Proveedores.
"""

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app import audit
from web_app.cache import cache, TTL_CATALOGOS, TTL_CATEGORIAS
from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual
from web_app.rbac import require_rol

router = APIRouter(prefix="/catalogos")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

POR_PAGINA_PRODUCTOS = 30

TIPOS_CLIENTE = ["Empresa", "Gobierno", "Persona"]

TIPO_CLIENTE_COLOR = {
    "Empresa":  ("bg-blue-100",   "text-blue-700"),
    "Gobierno": ("bg-purple-100", "text-purple-700"),
    "Persona":  ("bg-green-100",  "text-green-700"),
}


def _floats(d: dict) -> dict:
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in d.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Raíz: redirige a clientes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def raiz(request: Request):
    return RedirectResponse("/catalogos/clientes")


# ─────────────────────────────────────────────────────────────────────────────
# CLIENTES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/clientes", response_class=HTMLResponse)
async def lista_clientes(request: Request, tipo: str = "", buscar: str = ""):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    where, params = [], []
    if tipo:
        where.append("c.tipo = %s"); params.append(tipo)
    if buscar:
        where.append("(c.nombre_comercial ILIKE %s OR c.rfc ILIKE %s OR c.contacto ILIKE %s)")
        params += [f"%{buscar}%"] * 3
    w = ("WHERE " + " AND ".join(where)) if where else ""

    _ck = f"clientes:{user['empresa_db']}" if not tipo and not buscar else None
    cached = cache.get(_ck) if _ck else None

    if cached:
        clientes, tipos = cached
    else:
        with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
            cur.execute(f"""
                SELECT c.id, c.nombre_comercial, c.razon_social, c.tipo,
                       c.rfc, c.contacto, c.telefono, c.email,
                       COUNT(cot.id)  AS num_cotizaciones,
                       MAX(cot.fecha) AS ultima_cotizacion
                FROM clientes c
                LEFT JOIN cotizaciones cot ON cot.cliente_id = c.id
                {w}
                GROUP BY c.id
                ORDER BY c.nombre_comercial
            """, params or None)
            cols     = [d[0] for d in cur.description]
            clientes = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

            cur.execute("SELECT DISTINCT tipo FROM clientes WHERE tipo IS NOT NULL ORDER BY tipo")
            tipos = [r[0] for r in cur.fetchall()]

        if _ck:
            cache.set(_ck, (clientes, tipos), ttl=TTL_CATALOGOS)

    ctx = {
        "user": user,
        "clientes": clientes,
        "tipos": tipos,
        "tipo_sel": tipo,
        "buscar": buscar,
        "tipo_color": TIPO_CLIENTE_COLOR,
        "seccion": "clientes",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="catalogos/_clientes_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="catalogos/clientes.html", context=ctx
    )


@router.get("/clientes/nuevo", response_class=HTMLResponse)
async def nuevo_cliente_form(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
):
    return templates.TemplateResponse(
        request=request,
        name="catalogos/cliente_form.html",
        context={"user": user, "clt": None, "tipos": TIPOS_CLIENTE, "seccion": "clientes"},
    )


@router.post("/clientes/nuevo", response_class=HTMLResponse)
async def crear_cliente(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
    nombre_comercial: str = Form(""),
    razon_social: str = Form(""),
    tipo: str = Form("Empresa"),
    rfc: str = Form(""),
    contacto: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    direccion: str = Form(""),
    regimen_fiscal: str = Form(""),
    cp_fiscal: str = Form(""),
    uso_cfdi: str = Form(""),
):
    nombre_comercial = nombre_comercial.strip()
    if not nombre_comercial or tipo not in TIPOS_CLIENTE:
        vals = dict(nombre_comercial=nombre_comercial, razon_social=razon_social, tipo=tipo,
                    rfc=rfc, contacto=contacto, telefono=telefono, email=email,
                    direccion=direccion, regimen_fiscal=regimen_fiscal,
                    cp_fiscal=cp_fiscal, uso_cfdi=uso_cfdi)
        msg = "El nombre comercial es obligatorio." if not nombre_comercial else "Tipo de cliente inválido."
        return templates.TemplateResponse(
            request=request,
            name="catalogos/cliente_form.html",
            context={"user": user, "clt": vals, "tipos": TIPOS_CLIENTE,
                     "seccion": "clientes", "error": msg},
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO clientes (nombre_comercial, razon_social, tipo, rfc, contacto,
                                  telefono, email, direccion, regimen_fiscal, cp_fiscal, uso_cfdi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            nombre_comercial, razon_social or None, tipo,
            rfc or None, contacto or None, telefono or None,
            email or None, direccion or None,
            regimen_fiscal or None, cp_fiscal or None, uso_cfdi or None,
        ))
        new_id = cur.fetchone()[0]

    cache.invalidar(f"clientes:{user['empresa_db']}")
    audit.registrar(
        "cliente_creado",
        username=user.get("username"),
        detalle=f"id={new_id} nombre={nombre_comercial}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(f"/catalogos/clientes/{new_id}", status_code=303)


@router.get("/clientes/{cliente_id}", response_class=HTMLResponse)
async def detalle_cliente(request: Request, cliente_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        cliente = _floats(dict(zip([d[0] for d in cur.description], row)))

        cur.execute("""
            SELECT id, folio, fecha, total, estado, orden_compra
            FROM cotizaciones
            WHERE cliente_id = %s
            ORDER BY fecha DESC, id DESC
            LIMIT 20
        """, (cliente_id,))
        dcols = [d[0] for d in cur.description]
        cotizaciones = [_floats(dict(zip(dcols, r))) for r in cur.fetchall()]

        cur.execute("""
            SELECT COUNT(*), COALESCE(SUM(total),0),
                   COUNT(*) FILTER (WHERE estado='Pagada'),
                   COUNT(*) FILTER (WHERE estado='Pendiente')
            FROM cotizaciones WHERE cliente_id = %s
        """, (cliente_id,))
        stats_row = cur.fetchone()
        stats = {
            "total_cots": stats_row[0],
            "monto_total": float(stats_row[1]),
            "pagadas":     stats_row[2],
            "pendientes":  stats_row[3],
        }

    from core.constants import ESTADO_COLOR_CSS as ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="catalogos/cliente_detalle.html",
        context={
            "user": user, "cliente": cliente,
            "cotizaciones": cotizaciones, "stats": stats,
            "tipo_color": TIPO_CLIENTE_COLOR,
            "estado_color": ESTADO_COLOR,
            "seccion": "clientes",
        },
    )


@router.get("/clientes/{cliente_id}/editar", response_class=HTMLResponse)
async def editar_cliente_form(
    request: Request,
    cliente_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM clientes WHERE id = %s", (cliente_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Cliente no encontrado")
        clt = _floats(dict(zip([d[0] for d in cur.description], row)))

    return templates.TemplateResponse(
        request=request,
        name="catalogos/cliente_form.html",
        context={"user": user, "clt": clt, "tipos": TIPOS_CLIENTE, "seccion": "clientes"},
    )


@router.post("/clientes/{cliente_id}/editar", response_class=HTMLResponse)
async def guardar_cliente(
    request: Request,
    cliente_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
    nombre_comercial: str = Form(""),
    razon_social: str = Form(""),
    tipo: str = Form("Empresa"),
    rfc: str = Form(""),
    contacto: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    direccion: str = Form(""),
    regimen_fiscal: str = Form(""),
    cp_fiscal: str = Form(""),
    uso_cfdi: str = Form(""),
):
    nombre_comercial = nombre_comercial.strip()
    if not nombre_comercial or tipo not in TIPOS_CLIENTE:
        vals = dict(id=cliente_id, nombre_comercial=nombre_comercial, razon_social=razon_social,
                    tipo=tipo, rfc=rfc, contacto=contacto, telefono=telefono, email=email,
                    direccion=direccion, regimen_fiscal=regimen_fiscal,
                    cp_fiscal=cp_fiscal, uso_cfdi=uso_cfdi)
        msg = "El nombre comercial es obligatorio." if not nombre_comercial else "Tipo de cliente inválido."
        return templates.TemplateResponse(
            request=request,
            name="catalogos/cliente_form.html",
            context={"user": user, "clt": vals, "tipos": TIPOS_CLIENTE,
                     "seccion": "clientes", "error": msg},
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE clientes SET
                nombre_comercial = %s, razon_social = %s, tipo = %s,
                rfc = %s, contacto = %s, telefono = %s, email = %s, direccion = %s,
                regimen_fiscal = %s, cp_fiscal = %s, uso_cfdi = %s
            WHERE id = %s
        """, (
            nombre_comercial, razon_social or None, tipo,
            rfc or None, contacto or None, telefono or None,
            email or None, direccion or None,
            regimen_fiscal or None, cp_fiscal or None, uso_cfdi or None,
            cliente_id,
        ))

    cache.invalidar(f"clientes:{user['empresa_db']}")
    audit.registrar(
        "cliente_editado",
        username=user.get("username"),
        detalle=f"id={cliente_id} nombre={nombre_comercial}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(f"/catalogos/clientes/{cliente_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTOS
# ─────────────────────────────────────────────────────────────────────────────

def _ctx_catalogo(empresa_db: str) -> dict:
    """Carga categorias y subcategorias para formularios de producto (con caché)."""
    _ck = f"categorias:{empresa_db}"
    cached = cache.get(_ck)
    if cached:
        return cached
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        cats = [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT id, nombre, categoria_id FROM subcategorias ORDER BY nombre")
        subs = [{"id": r[0], "nombre": r[1], "categoria_id": r[2]} for r in cur.fetchall()]
    result = {"categorias": cats, "subcategorias": subs}
    cache.set(_ck, result, ttl=TTL_CATEGORIAS)
    return result


@router.get("/productos", response_class=HTMLResponse)
async def lista_productos(
    request: Request,
    buscar: str = "",
    categoria: str = "",
    con_stock: str = "",
    pagina: int = 1,
):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    where, params = [], []
    if buscar:
        where.append("(p.nombre ILIKE %s OR p.codigo ILIKE %s OR p.descripcion ILIKE %s)")
        params += [f"%{buscar}%"] * 3
    if categoria:
        where.append("cat.nombre = %s"); params.append(categoria)
    if con_stock == "1":
        where.append("p.stock_actual > 0")
    elif con_stock == "0":
        where.append("(p.stock_actual IS NULL OR p.stock_actual = 0)")

    w      = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (pagina - 1) * POR_PAGINA_PRODUCTOS

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT p.id, p.codigo, p.nombre, p.unidad_medida,
                   p.precio_base, p.aplica_iva, p.stock_actual, p.stock_minimo,
                   cat.nombre AS categoria, sub.nombre AS subcategoria
            FROM productos p
            LEFT JOIN categorias   cat ON cat.id = p.categoria_id
            LEFT JOIN subcategorias sub ON sub.id = p.subcategoria_id
            {w}
            ORDER BY cat.nombre, p.nombre
            LIMIT {POR_PAGINA_PRODUCTOS} OFFSET {offset}
        """, params or None)
        cols      = [d[0] for d in cur.description]
        productos = [_floats(dict(zip(cols, r))) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COUNT(*)
            FROM productos p
            LEFT JOIN categorias cat ON cat.id = p.categoria_id
            {w}
        """, params or None)
        total = cur.fetchone()[0]

        cur.execute("SELECT nombre FROM categorias ORDER BY nombre")
        categorias = [r[0] for r in cur.fetchall()]

    total_pags = max(1, (total + POR_PAGINA_PRODUCTOS - 1) // POR_PAGINA_PRODUCTOS)

    ctx = {
        "user": user,
        "productos": productos,
        "categorias": categorias,
        "buscar": buscar,
        "categoria_sel": categoria,
        "con_stock": con_stock,
        "pagina": pagina,
        "total": total,
        "total_pags": total_pags,
        "por_pagina": POR_PAGINA_PRODUCTOS,
        "seccion": "productos",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="catalogos/_productos_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="catalogos/productos.html", context=ctx
    )


def _asegurar_col_codigo_barras(empresa_db: str) -> None:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS codigo_barras TEXT")


def _asegurar_col_proveedor_historial(empresa_db: str) -> None:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            "ALTER TABLE producto_precio_historial "
            "ADD COLUMN IF NOT EXISTS proveedor_id INTEGER REFERENCES proveedores(id)"
        )


def _cargar_proveedores(empresa_db: str) -> list:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
        return [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]


def _historial_con_proveedores(cur, producto_id: int) -> list:
    """Devuelve el historial de precios con nombre de proveedor unido."""
    from datetime import datetime as _dt
    cur.execute("""
        SELECT h.id, h.precio, h.fecha, h.motivo, h.fuente, h.proveedor_id,
               prov.nombre AS proveedor_nombre
        FROM producto_precio_historial h
        LEFT JOIN proveedores prov ON prov.id = h.proveedor_id
        WHERE h.producto_id = %s
        ORDER BY h.fecha DESC, h.fecha_registro DESC
    """, (producto_id,))
    hcols = [d[0] for d in cur.description]
    historial = []
    for r in cur.fetchall():
        h = _floats(dict(zip(hcols, r)))
        if isinstance(h.get("fecha"), str):
            try:
                h["fecha"] = _dt.fromisoformat(h["fecha"])
            except (ValueError, TypeError):
                h["fecha"] = None
        historial.append(h)
    return historial


@router.get("/productos/nuevo", response_class=HTMLResponse)
async def nuevo_producto_form(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
):
    _asegurar_col_codigo_barras(user["empresa_db"])
    return templates.TemplateResponse(
        request=request,
        name="catalogos/producto_form.html",
        context={"user": user, "prod": None, "seccion": "productos",
                 **_ctx_catalogo(user["empresa_db"])},
    )


@router.post("/productos/nuevo", response_class=HTMLResponse)
async def crear_producto(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
    nombre: str = Form(""),
    codigo: str = Form(""),
    descripcion: str = Form(""),
    categoria_id: str = Form(""),
    subcategoria_id: str = Form(""),
    unidad_medida: str = Form(""),
    precio_base: str = Form("0"),
    aplica_iva: str = Form("0"),
    clave_sat: str = Form(""),
    clave_unidad_sat: str = Form(""),
    stock_minimo: str = Form("0"),
    codigo_barras: str = Form(""),
):
    nombre = nombre.strip()
    codigo = codigo.strip().upper()
    error = None
    precio_base_f = 0.0
    if not nombre:
        error = "El nombre del producto es obligatorio."
    elif not codigo:
        error = "El código es obligatorio."
    else:
        try:
            precio_base_f = float(precio_base or 0)
        except ValueError:
            error = "El precio base debe ser un número válido."

    if error:
        vals = dict(nombre=nombre, codigo=codigo, descripcion=descripcion,
                    categoria_id=int(categoria_id) if categoria_id else None,
                    subcategoria_id=int(subcategoria_id) if subcategoria_id else None,
                    unidad_medida=unidad_medida, precio_base=precio_base_f,
                    aplica_iva=aplica_iva, clave_sat=clave_sat,
                    clave_unidad_sat=clave_unidad_sat, stock_minimo=stock_minimo)
        return templates.TemplateResponse(
            request=request,
            name="catalogos/producto_form.html",
            context={"user": user, "prod": vals, "seccion": "productos",
                     "error": error, **_ctx_catalogo(user["empresa_db"])},
        )

    try:
        with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
            cur.execute("""
                INSERT INTO productos (nombre, codigo, descripcion, categoria_id, subcategoria_id,
                                       unidad_medida, precio_base, aplica_iva,
                                       clave_sat, clave_unidad_sat, stock_minimo, codigo_barras)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                nombre, codigo, descripcion or None,
                int(categoria_id) if categoria_id else None,
                int(subcategoria_id) if subcategoria_id else None,
                unidad_medida or None, precio_base_f,
                1 if aplica_iva == "1" else 0,
                clave_sat or None, clave_unidad_sat or None,
                float(stock_minimo or 0),
                codigo_barras.strip() or None,
            ))
            new_id = cur.fetchone()[0]
    except Exception as e:
        error = (f"El código '{codigo}' ya está en uso por otro producto."
                 if "unique" in str(e).lower() or "duplicate" in str(e).lower()
                 else "Error al guardar el producto. Intenta de nuevo.")
        vals = dict(nombre=nombre, codigo=codigo, descripcion=descripcion,
                    categoria_id=int(categoria_id) if categoria_id else None,
                    subcategoria_id=int(subcategoria_id) if subcategoria_id else None,
                    unidad_medida=unidad_medida, precio_base=precio_base_f,
                    aplica_iva=aplica_iva, clave_sat=clave_sat,
                    clave_unidad_sat=clave_unidad_sat, stock_minimo=stock_minimo)
        return templates.TemplateResponse(
            request=request,
            name="catalogos/producto_form.html",
            context={"user": user, "prod": vals, "seccion": "productos",
                     "error": error, **_ctx_catalogo(user["empresa_db"])},
        )

    cache.invalidar(f"productos:{user['empresa_db']}")
    audit.registrar(
        "producto_creado",
        username=user.get("username"),
        detalle=f"id={new_id} codigo={codigo} nombre={nombre}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(f"/catalogos/productos/{new_id}", status_code=303)


@router.get("/productos/generar-sku", response_class=JSONResponse)
async def generar_sku_producto(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
    categoria_id: str = "",
    subcategoria_id: str = "",
):
    """Genera un SKU automático: 3 letras de categoría + 3 letras de subcategoría + número secuencial."""
    if not categoria_id:
        return JSONResponse({"sku": ""})
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT nombre FROM categorias WHERE id = %s", (int(categoria_id),))
        row = cur.fetchone()
        if not row:
            return JSONResponse({"sku": ""})
        prefix = row[0][:3].upper()
        if subcategoria_id:
            cur.execute("SELECT nombre FROM subcategorias WHERE id = %s", (int(subcategoria_id),))
            sub_row = cur.fetchone()
            prefix += sub_row[0][:3].upper() if sub_row else "GEN"
        else:
            prefix += "GEN"
        cur.execute(
            "SELECT codigo FROM productos WHERE codigo LIKE %s ORDER BY codigo DESC LIMIT 1",
            (f"{prefix}%",)
        )
        ultimo = cur.fetchone()
        if ultimo:
            try:
                num = int(ultimo[0][len(prefix):]) + 1
            except Exception:
                num = 1
        else:
            num = 1
    return JSONResponse({"sku": f"{prefix}{num:04d}"})


@router.get("/productos/{producto_id}", response_class=HTMLResponse)
async def detalle_producto(request: Request, producto_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT p.*,
                   cat.nombre AS categoria,
                   sub.nombre AS subcategoria
            FROM productos p
            LEFT JOIN categorias    cat ON cat.id = p.categoria_id
            LEFT JOIN subcategorias sub ON sub.id = p.subcategoria_id
            WHERE p.id = %s
        """, (producto_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
        producto = _floats(dict(zip([d[0] for d in cur.description], row)))

        # Historial de precios
        cur.execute("""
            SELECT precio, fecha, motivo, fuente
            FROM producto_precio_historial
            WHERE producto_id = %s
            ORDER BY fecha DESC LIMIT 10
        """, (producto_id,))
        from datetime import datetime as _dt
        hcols     = [d[0] for d in cur.description]
        historial = []
        for r in cur.fetchall():
            h = _floats(dict(zip(hcols, r)))
            if isinstance(h.get("fecha"), str):
                try:
                    h["fecha"] = _dt.fromisoformat(h["fecha"])
                except (ValueError, TypeError):
                    h["fecha"] = None
            historial.append(h)

        # Proveedores vinculados
        cur.execute("""
            SELECT prov.nombre, prov.telefono, prov.email
            FROM producto_proveedor pp
            JOIN proveedores prov ON prov.id = pp.proveedor_id
            WHERE pp.producto_id = %s
        """, (producto_id,))
        pcols      = [d[0] for d in cur.description]
        proveedores = [dict(zip(pcols, r)) for r in cur.fetchall()]

        # Ultimas cotizaciones donde aparece
        cur.execute("""
            SELECT cot.folio, cot.fecha, cot.estado,
                   cd.cantidad, cd.precio_unitario
            FROM cotizacion_detalle cd
            JOIN cotizaciones cot ON cot.id = cd.cotizacion_id
            WHERE cd.producto_id = %s
            ORDER BY cot.fecha DESC LIMIT 5
        """, (producto_id,))
        ucols    = [d[0] for d in cur.description]
        uso_cots = [_floats(dict(zip(ucols, r))) for r in cur.fetchall()]

    from core.constants import ESTADO_COLOR_CSS as ESTADO_COLOR
    return templates.TemplateResponse(
        request=request,
        name="catalogos/producto_detalle.html",
        context={
            "user": user, "producto": producto,
            "historial": historial, "proveedores": proveedores,
            "uso_cots": uso_cots, "estado_color": ESTADO_COLOR,
            "seccion": "productos",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# ACTUALIZAR PRECIO
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/productos/{producto_id}/precio", response_class=HTMLResponse)
async def actualizar_precio(
    request: Request,
    producto_id: int,
    precio_nuevo: float = Form(...),
    motivo: str = Form(""),
    proveedor_id: str = Form(""),
    user=Depends(require_rol("Administrador", "Operador")),
):
    from datetime import date as _date
    if precio_nuevo < 0:
        raise HTTPException(400, "El precio no puede ser negativo.")

    prov_id = int(proveedor_id) if proveedor_id.strip() else None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT precio_base, nombre FROM productos WHERE id = %s", (producto_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
        precio_actual, nombre = float(row[0] or 0), row[1]

        if abs(precio_nuevo - precio_actual) > 0.001:
            cur.execute("UPDATE productos SET precio_base = %s WHERE id = %s",
                        (precio_nuevo, producto_id))
            cur.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente, proveedor_id)
                VALUES (%s, %s, %s, %s, 'manual', %s)
            """, (producto_id, precio_nuevo,
                  _date.today().isoformat(),
                  motivo.strip() or "Actualización manual",
                  prov_id))
            cambio = True
        else:
            cambio = False

        historial   = _historial_con_proveedores(cur, producto_id)
        proveedores = _cargar_proveedores(user["empresa_db"])

    return templates.TemplateResponse(
        request=request,
        name="catalogos/_historial_completo.html",
        context={
            "user":         user,
            "historial":    historial,
            "proveedores":  proveedores,
            "producto_id":  producto_id,
            "precio_actual": precio_nuevo if cambio else precio_actual,
            "toast": f"Precio actualizado a ${precio_nuevo:,.2f}" if cambio else "Sin cambios (precio idéntico)",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# HISTORIAL COMPLETO (fragment HTMX)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/productos/{producto_id}/historial", response_class=HTMLResponse)
async def historial_precios(
    request: Request,
    producto_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        historial = _historial_con_proveedores(cur, producto_id)

        cur.execute("SELECT precio_base FROM productos WHERE id = %s", (producto_id,))
        row = cur.fetchone()
        precio_actual = float(row[0] or 0) if row else 0.0

        proveedores = _cargar_proveedores(user["empresa_db"])

    return templates.TemplateResponse(
        request=request,
        name="catalogos/_historial_completo.html",
        context={
            "user":         user,
            "historial":    historial,
            "proveedores":  proveedores,
            "producto_id":  producto_id,
            "precio_actual": precio_actual,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# AGREGAR REGISTRO MANUAL AL HISTORIAL
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/productos/{producto_id}/historial", response_class=HTMLResponse)
async def agregar_historial_manual(
    request: Request,
    producto_id: int,
    precio: float = Form(...),
    fecha: str = Form(...),
    motivo: str = Form(""),
    proveedor_id: str = Form(""),
    user=Depends(require_rol("Administrador", "Operador")),
):
    if precio < 0:
        raise HTTPException(400, "El precio no puede ser negativo.")

    prov_id = int(proveedor_id) if proveedor_id.strip() else None

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO producto_precio_historial
                (producto_id, precio, fecha, motivo, fuente, proveedor_id)
            VALUES (%s, %s, %s, %s, 'manual', %s)
        """, (producto_id, precio, fecha,
              motivo.strip() or "Registro manual", prov_id))

        historial   = _historial_con_proveedores(cur, producto_id)
        proveedores = _cargar_proveedores(user["empresa_db"])

        cur.execute("SELECT precio_base FROM productos WHERE id = %s", (producto_id,))
        row = cur.fetchone()
        precio_actual = float(row[0] or 0) if row else 0.0

    return templates.TemplateResponse(
        request=request,
        name="catalogos/_historial_completo.html",
        context={
            "user":         user,
            "historial":    historial,
            "proveedores":  proveedores,
            "producto_id":  producto_id,
            "precio_actual": precio_actual,
            "toast": "Registro agregado al historial.",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR MOTIVO DE UN REGISTRO
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/historial/{hid}/editar-motivo", response_class=HTMLResponse)
async def editar_motivo_form(
    request: Request,
    hid: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT motivo FROM producto_precio_historial WHERE id = %s", (hid,))
        row = cur.fetchone()
        motivo_actual = row[0] or "" if row else ""

    return HTMLResponse(f"""
        <form hx-post="/catalogos/historial/{hid}/motivo" hx-target="this" hx-swap="outerHTML"
              class="flex gap-1 items-center">
            <input type="text" name="motivo" value="{motivo_actual}"
                   autofocus
                   class="px-2 py-0.5 text-xs border border-clf-green rounded focus:outline-none w-40">
            <button type="submit" class="text-xs text-clf-green font-bold hover:underline">✓</button>
        </form>
    """)


@router.post("/historial/{hid}/motivo", response_class=HTMLResponse)
async def editar_motivo_historial(
    request: Request,
    hid: int,
    motivo: str = Form(...),
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE producto_precio_historial SET motivo = %s WHERE id = %s RETURNING producto_id",
            (motivo.strip(), hid)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404)

    return HTMLResponse(
        f'<span class="text-xs text-gray-500 italic" '
        f'hx-post="/catalogos/historial/{hid}/motivo" '
        f'hx-trigger="dblclick" hx-swap="outerHTML" '
        f'hx-vals=\'{{\"motivo\": \"{motivo.strip()}\"}}\'>'
        f'{motivo.strip() or "—"}</span>'
    )


@router.get("/productos/{producto_id}/editar", response_class=HTMLResponse)
async def editar_producto_form(
    request: Request,
    producto_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Producto no encontrado")
        prod = _floats(dict(zip([d[0] for d in cur.description], row)))
        cur.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        categorias = [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]
        cur.execute("SELECT id, nombre, categoria_id FROM subcategorias ORDER BY nombre")
        subcategorias = [{"id": r[0], "nombre": r[1], "categoria_id": r[2]} for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="catalogos/producto_form.html",
        context={"user": user, "prod": prod, "seccion": "productos",
                 "categorias": categorias, "subcategorias": subcategorias},
    )


@router.post("/productos/{producto_id}/editar", response_class=HTMLResponse)
async def guardar_producto(
    request: Request,
    producto_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
    nombre: str = Form(""),
    codigo: str = Form(""),
    descripcion: str = Form(""),
    categoria_id: str = Form(""),
    subcategoria_id: str = Form(""),
    unidad_medida: str = Form(""),
    precio_base: str = Form("0"),
    aplica_iva: str = Form("0"),
    clave_sat: str = Form(""),
    clave_unidad_sat: str = Form(""),
    stock_minimo: str = Form("0"),
    codigo_barras: str = Form(""),
):
    nombre = nombre.strip()
    codigo = codigo.strip().upper()
    error = None
    precio_base_f = 0.0
    if not nombre:
        error = "El nombre del producto es obligatorio."
    elif not codigo:
        error = "El código es obligatorio."
    else:
        try:
            precio_base_f = float(precio_base or 0)
        except ValueError:
            error = "El precio base debe ser un número válido."

    if error:
        vals = dict(id=producto_id, nombre=nombre, codigo=codigo, descripcion=descripcion,
                    categoria_id=int(categoria_id) if categoria_id else None,
                    subcategoria_id=int(subcategoria_id) if subcategoria_id else None,
                    unidad_medida=unidad_medida, precio_base=precio_base,
                    aplica_iva=aplica_iva, clave_sat=clave_sat,
                    clave_unidad_sat=clave_unidad_sat, stock_minimo=stock_minimo)
        return templates.TemplateResponse(
            request=request,
            name="catalogos/producto_form.html",
            context={"user": user, "prod": vals, "seccion": "productos",
                     "error": error, **_ctx_catalogo(user["empresa_db"])},
        )

    try:
        with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
            cur.execute("""
                UPDATE productos SET
                    nombre = %s, codigo = %s, descripcion = %s,
                    categoria_id = %s, subcategoria_id = %s,
                    unidad_medida = %s, precio_base = %s, aplica_iva = %s,
                    clave_sat = %s, clave_unidad_sat = %s, stock_minimo = %s,
                    codigo_barras = %s
                WHERE id = %s
            """, (
                nombre, codigo, descripcion or None,
                int(categoria_id) if categoria_id else None,
                int(subcategoria_id) if subcategoria_id else None,
                unidad_medida or None, precio_base_f,
                1 if aplica_iva == "1" else 0,
                clave_sat or None, clave_unidad_sat or None,
                float(stock_minimo or 0),
                codigo_barras.strip() or None,
                producto_id,
            ))
    except Exception as e:
        error = (f"El código '{codigo}' ya está en uso por otro producto."
                 if "unique" in str(e).lower() or "duplicate" in str(e).lower()
                 else "Error al guardar el producto. Intenta de nuevo.")
        vals = dict(id=producto_id, nombre=nombre, codigo=codigo, descripcion=descripcion,
                    categoria_id=int(categoria_id) if categoria_id else None,
                    subcategoria_id=int(subcategoria_id) if subcategoria_id else None,
                    unidad_medida=unidad_medida, precio_base=precio_base,
                    aplica_iva=aplica_iva, clave_sat=clave_sat,
                    clave_unidad_sat=clave_unidad_sat, stock_minimo=stock_minimo)
        return templates.TemplateResponse(
            request=request,
            name="catalogos/producto_form.html",
            context={"user": user, "prod": vals, "seccion": "productos",
                     "error": error, **_ctx_catalogo(user["empresa_db"])},
        )

    cache.invalidar(f"productos:{user['empresa_db']}")
    audit.registrar(
        "producto_editado",
        username=user.get("username"),
        detalle=f"id={producto_id} codigo={codigo} nombre={nombre}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(f"/catalogos/productos/{producto_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/proveedores", response_class=HTMLResponse)
async def lista_proveedores(request: Request, buscar: str = ""):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    where, params = [], []
    if buscar:
        where.append("(p.nombre ILIKE %s OR p.rfc ILIKE %s OR p.contacto ILIKE %s)")
        params += [f"%{buscar}%"] * 3
    w = ("WHERE " + " AND ".join(where)) if where else ""

    _ck = f"proveedores:{user['empresa_db']}" if not buscar else None
    cached = cache.get(_ck) if _ck else None

    if cached:
        proveedores = cached
    else:
        with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
            cur.execute(f"""
                SELECT p.id, p.nombre, p.rfc, p.contacto, p.telefono, p.email,
                       COUNT(pp.producto_id) AS num_productos
                FROM proveedores p
                LEFT JOIN producto_proveedor pp ON pp.proveedor_id = p.id
                {w}
                GROUP BY p.id, p.nombre, p.rfc, p.contacto, p.telefono, p.email
                ORDER BY p.nombre
            """, params or None)
            cols        = [d[0] for d in cur.description]
            proveedores = [dict(zip(cols, r)) for r in cur.fetchall()]
        if _ck:
            cache.set(_ck, proveedores, ttl=TTL_CATALOGOS)

    ctx = {
        "user": user,
        "proveedores": proveedores,
        "buscar": buscar,
        "seccion": "proveedores",
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request, name="catalogos/_proveedores_tabla.html", context=ctx
        )
    return templates.TemplateResponse(
        request=request, name="catalogos/proveedores.html", context=ctx
    )


@router.get("/proveedores/nuevo", response_class=HTMLResponse)
async def nuevo_proveedor_form(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
):
    return templates.TemplateResponse(
        request=request,
        name="catalogos/proveedor_form.html",
        context={"user": user, "prov": None, "seccion": "proveedores"},
    )


@router.post("/proveedores/nuevo", response_class=HTMLResponse)
async def crear_proveedor(
    request: Request,
    user=Depends(require_rol("Administrador", "Operador")),
    nombre: str = Form(""),
    razon_social: str = Form(""),
    rfc: str = Form(""),
    contacto: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    direccion: str = Form(""),
    notas: str = Form(""),
    regimen_fiscal: str = Form(""),
    cp_fiscal: str = Form(""),
    uso_cfdi: str = Form(""),
):
    nombre = nombre.strip()
    if not nombre:
        vals = dict(nombre=nombre, razon_social=razon_social, rfc=rfc, contacto=contacto,
                    telefono=telefono, email=email, direccion=direccion,
                    notas=notas, regimen_fiscal=regimen_fiscal,
                    cp_fiscal=cp_fiscal, uso_cfdi=uso_cfdi)
        return templates.TemplateResponse(
            request=request,
            name="catalogos/proveedor_form.html",
            context={"user": user, "prov": vals, "seccion": "proveedores",
                     "error": "El nombre del proveedor es obligatorio."},
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO proveedores (nombre, razon_social, rfc, contacto, telefono, email,
                                     direccion, notas, regimen_fiscal, cp_fiscal, uso_cfdi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            nombre, razon_social or None, rfc or None, contacto or None,
            telefono or None, email or None, direccion or None,
            notas or None, regimen_fiscal or None, cp_fiscal or None, uso_cfdi or None,
        ))
        new_id = cur.fetchone()[0]

    cache.invalidar(f"proveedores:{user['empresa_db']}")
    audit.registrar(
        "proveedor_creado",
        username=user.get("username"),
        detalle=f"id={new_id} nombre={nombre}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(f"/catalogos/proveedores/{new_id}", status_code=303)


@router.get("/proveedores/{prov_id}/editar", response_class=HTMLResponse)
async def editar_proveedor_form(
    request: Request,
    prov_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM proveedores WHERE id = %s", (prov_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Proveedor no encontrado")
        prov = dict(zip([d[0] for d in cur.description], row))

    return templates.TemplateResponse(
        request=request,
        name="catalogos/proveedor_form.html",
        context={"user": user, "prov": prov, "seccion": "proveedores"},
    )


@router.post("/proveedores/{prov_id}/editar", response_class=HTMLResponse)
async def guardar_proveedor(
    request: Request,
    prov_id: int,
    user=Depends(require_rol("Administrador", "Operador")),
    nombre: str = Form(""),
    razon_social: str = Form(""),
    rfc: str = Form(""),
    contacto: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    direccion: str = Form(""),
    notas: str = Form(""),
    regimen_fiscal: str = Form(""),
    cp_fiscal: str = Form(""),
    uso_cfdi: str = Form(""),
):
    nombre = nombre.strip()
    if not nombre:
        vals = dict(id=prov_id, nombre=nombre, razon_social=razon_social, rfc=rfc,
                    contacto=contacto, telefono=telefono, email=email, direccion=direccion,
                    notas=notas, regimen_fiscal=regimen_fiscal,
                    cp_fiscal=cp_fiscal, uso_cfdi=uso_cfdi)
        return templates.TemplateResponse(
            request=request,
            name="catalogos/proveedor_form.html",
            context={"user": user, "prov": vals, "seccion": "proveedores",
                     "error": "El nombre del proveedor es obligatorio."},
        )

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE proveedores SET
                nombre = %s, razon_social = %s, rfc = %s, contacto = %s,
                telefono = %s, email = %s, direccion = %s,
                notas = %s, regimen_fiscal = %s, cp_fiscal = %s, uso_cfdi = %s
            WHERE id = %s
        """, (
            nombre, razon_social or None, rfc or None, contacto or None,
            telefono or None, email or None, direccion or None,
            notas or None, regimen_fiscal or None, cp_fiscal or None, uso_cfdi or None,
            prov_id,
        ))

    cache.invalidar(f"proveedores:{user['empresa_db']}")
    audit.registrar(
        "proveedor_editado",
        username=user.get("username"),
        detalle=f"id={prov_id} nombre={nombre}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(f"/catalogos/proveedores/{prov_id}", status_code=303)


@router.get("/proveedores/{prov_id}", response_class=HTMLResponse)
async def detalle_proveedor(request: Request, prov_id: int):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT * FROM proveedores WHERE id = %s", (prov_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Proveedor no encontrado")
        proveedor = dict(zip([d[0] for d in cur.description], row))

        cur.execute("""
            SELECT p.id, p.codigo, p.nombre, p.precio_base, p.unidad_medida,
                   cat.nombre AS categoria
            FROM producto_proveedor pp
            JOIN productos    p   ON p.id   = pp.producto_id
            LEFT JOIN categorias cat ON cat.id = p.categoria_id
            WHERE pp.proveedor_id = %s
            ORDER BY cat.nombre, p.nombre
        """, (prov_id,))
        pcols     = [d[0] for d in cur.description]
        productos = [_floats(dict(zip(pcols, r))) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="catalogos/proveedor_detalle.html",
        context={
            "user": user, "proveedor": proveedor,
            "productos": productos, "seccion": "proveedores",
        },
    )
