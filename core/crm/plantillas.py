# -*- coding: utf-8 -*-
"""
core/crm/plantillas.py
Renderiza plantillas HTML de correo reemplazando variables de cliente.
"""

import re


_VAR_RE = re.compile(r'\{\{(\w+)\}\}')


def renderizar(html_body: str, contexto: dict) -> str:
    """
    Reemplaza {{variable}} en `html_body` con los valores de `contexto`.
    Las variables desconocidas se dejan como cadena vacía.
    """
    def _repl(m):
        return str(contexto.get(m.group(1), ''))
    return _VAR_RE.sub(_repl, html_body)


def contexto_cliente(cliente: dict, extra: dict | None = None) -> dict:
    """
    Construye el contexto de variables para un cliente dado.
    `cliente` debe tener al menos: nombre_comercial, contacto, email.
    """
    ctx = {
        'nombre_comercial': cliente.get('nombre_comercial', ''),
        'razon_social':     cliente.get('razon_social', ''),
        'contacto':         cliente.get('contacto', ''),
        'email':            cliente.get('email', ''),
        'telefono':         cliente.get('telefono', ''),
        'rfc':              cliente.get('rfc', ''),
    }
    if extra:
        ctx.update(extra)
    return ctx


def extraer_variables(html_body: str) -> list[str]:
    """Devuelve la lista de variables únicas presentes en la plantilla."""
    return sorted(set(_VAR_RE.findall(html_body)))
