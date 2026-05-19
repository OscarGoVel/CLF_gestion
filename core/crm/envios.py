# -*- coding: utf-8 -*-
"""
core/crm/envios.py
Integración con SendGrid para envío de correos CRM.
Requiere variable de entorno SENDGRID_API_KEY.
"""

import os
import json
import logging
import urllib.request
import urllib.error

_log = logging.getLogger('clf.crm.envios')

_SENDGRID_URL = 'https://api.sendgrid.com/v3/mail/send'
_FROM_EMAIL   = os.getenv('CRM_FROM_EMAIL', 'noreply@clf-gestion.com')
_FROM_NAME    = os.getenv('CRM_FROM_NAME',  'CLF Gestión')


def enviar_correo(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
    attachment_url: str | None = None,
) -> tuple[bool, str]:
    """
    Envía un correo vía SendGrid.
    Retorna (éxito: bool, mensaje_id_o_error: str).
    """
    api_key = os.getenv('SENDGRID_API_KEY')
    if not api_key:
        _log.warning("SENDGRID_API_KEY no configurada — envío omitido (modo prueba)")
        return True, 'test-mode-no-key'

    payload = {
        'personalizations': [{
            'to': [{'email': to_email, 'name': to_name}],
            'subject': subject,
        }],
        'from': {'email': _FROM_EMAIL, 'name': _FROM_NAME},
        'content': [{'type': 'text/html', 'value': html_content}],
        'tracking_settings': {
            'click_tracking':  {'enable': True},
            'open_tracking':   {'enable': True},
        },
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        _SENDGRID_URL,
        data=data,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            msg_id = resp.headers.get('X-Message-Id', '')
            _log.info("Correo enviado a %s, msg_id=%s", to_email, msg_id)
            return True, msg_id
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        _log.error("SendGrid HTTP %s: %s", e.code, body)
        return False, f"HTTP {e.code}: {body[:200]}"
    except Exception as e:
        _log.error("Error enviando correo: %s", e)
        return False, str(e)
