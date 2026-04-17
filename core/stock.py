# -*- coding: utf-8 -*-
"""
core/stock.py
Lógica pura de clasificación ABC de inventario.
Sin dependencias de UI ni de frameworks.
"""
from typing import Sequence


def clasificar_abc(datos: Sequence[tuple]) -> dict:
    """
    Clasifica productos según el análisis ABC por valor de inventario.

    Parámetros
    ----------
    datos : secuencia de tuplas (producto_id, valor)
        producto_id puede ser int o cualquier clave hasheable.
        valor       es el valor numérico de inventario (stock × costo).

    Retorna
    -------
    dict { producto_id: {'categoria': 'A'|'B'|'C',
                          'valor': float,
                          'porcentaje_acum': float} }

    Reglas clásicas
    ---------------
      A → acumulado hasta  80 % del valor total
      B → acumulado de 80 % a 95 %
      C → acumulado de 95 % a 100 %
    """
    if not datos:
        return {}

    total = sum(float(v) for _, v in datos)
    if total == 0:
        return {pid: {"categoria": "C", "valor": 0.0, "porcentaje_acum": 100.0}
                for pid, _ in datos}

    ordenado = sorted(datos, key=lambda x: float(x[1]), reverse=True)
    resultado = {}
    acum = 0.0
    for pid, valor in ordenado:
        valor = float(valor)
        acum += valor
        pct = (acum / total) * 100
        cat = "A" if pct <= 80 else ("B" if pct <= 95 else "C")
        resultado[pid] = {
            "categoria":       cat,
            "valor":           round(valor, 2),
            "porcentaje_acum": round(pct, 1),
        }
    return resultado


def calcular_abc_desde_cursor(cursor) -> dict:
    """
    Versión para la app de escritorio: ejecuta el query de stock y
    llama a clasificar_abc() con los resultados.

    Retorna el mismo dict que clasificar_abc().
    """
    cursor.execute("""
        SELECT p.id,
               (p.stock_actual * COALESCE(
                   (SELECT AVG(cd.costo_unitario)
                    FROM compra_detalle cd
                    WHERE cd.producto_id = p.id), 0
               )) AS valor
        FROM productos p
        WHERE p.stock_actual > 0
    """)
    rows = cursor.fetchall()
    return clasificar_abc([(r[0], r[1]) for r in rows])
