# -*- coding: utf-8 -*-
"""
core/crm/segmentacion.py
Cálculo RFM (Recencia, Frecuencia, Monto) desde cotizaciones.
"""

from datetime import date
from typing import Any


_ESTADOS_PAGADOS = (
    'Pagada', 'Facturada', 'Entregada',
    'Parcialmente Entregada', 'Programada',
)


def calcular_rfm(cur) -> list[dict]:
    """
    Calcula RFM para todos los clientes activos.
    `cur` debe ser un cursor ya conectado a la DB empresa.
    Devuelve lista de dicts con: cliente_id, recencia_dias, frecuencia, monto_total, segmento_rfm
    """
    cur.execute("""
        SELECT
            c.id                                                    AS cliente_id,
            CURRENT_DATE - MAX(cot.fecha)::date                    AS recencia_dias,
            COUNT(cot.id)                                          AS frecuencia,
            COALESCE(SUM(cot.total), 0)                            AS monto_total
        FROM clientes c
        LEFT JOIN cotizaciones cot
               ON cot.cliente_id = c.id
              AND cot.estado IN %s
              AND cot.fecha >= CURRENT_DATE - INTERVAL '12 months'
        WHERE (c.activo IS NULL OR c.activo = TRUE)
        GROUP BY c.id
    """, (_ESTADOS_PAGADOS,))

    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    for r in rows:
        r['recencia_dias'] = int(r['recencia_dias']) if r['recencia_dias'] is not None else 9999
        r['frecuencia']    = int(r['frecuencia'])
        r['monto_total']   = float(r['monto_total'])
        r['segmento_rfm']  = _clasificar(r['recencia_dias'], r['frecuencia'], r['monto_total'])

    return rows


def _clasificar(recencia: int, frecuencia: int, monto: float) -> str:
    if recencia <= 30 and frecuencia >= 3 and monto >= 50_000:
        return 'Champions'
    if recencia <= 90 and frecuencia >= 2:
        return 'Loyal'
    if 90 < recencia <= 180 and frecuencia >= 1:
        return 'At Risk'
    if recencia > 180 and frecuencia >= 1:
        return 'Lost'
    return 'Prospect'


def guardar_rfm_snapshot(cur, rows: list[dict]) -> None:
    """Inserta un nuevo snapshot RFM (no sobreescribe histórico)."""
    cur.execute("DELETE FROM crm_rfm_snapshot")
    for r in rows:
        cur.execute("""
            INSERT INTO crm_rfm_snapshot
                (cliente_id, recencia_dias, frecuencia, monto_total, segmento_rfm)
            VALUES (%s, %s, %s, %s, %s)
        """, (r['cliente_id'], r['recencia_dias'], r['frecuencia'],
              r['monto_total'], r['segmento_rfm']))


def resumen_rfm(cur) -> dict:
    """Distribución de clientes por segmento RFM desde el snapshot más reciente."""
    cur.execute("""
        SELECT segmento_rfm, COUNT(*) AS total
        FROM crm_rfm_snapshot
        GROUP BY segmento_rfm
        ORDER BY total DESC
    """)
    return {r[0]: r[1] for r in cur.fetchall()}
