# -*- coding: utf-8 -*-
"""
sesion.py
Estado global de la sesión activa.
"""

# Dict mutable — se actualiza in-place al hacer login/logout.
USUARIO_ACTUAL: dict = {
    'id':       None,
    'username': '',
    'nombre':   '',
    'rol':      '',   # 'Administrador' | 'Operador' | 'Solo lectura'
}

# Bandera de reinicio — usada por __main__ para saber qué hacer
# tras salir del mainloop sin cerrar la app definitivamente.
#   None             → salida normal
#   'cerrar_sesion'  → volver a login (misma empresa)
#   'cambiar_empresa'→ volver a login + selector de empresa
ACCION_REINICIO: list = [None]


def esta_logueado() -> bool:
    return USUARIO_ACTUAL['id'] is not None


def nombre_display() -> str:
    return USUARIO_ACTUAL.get('nombre') or USUARIO_ACTUAL.get('username') or '—'


def cerrar_sesion():
    USUARIO_ACTUAL.update({'id': None, 'username': '', 'nombre': '', 'rol': ''})
