# -*- coding: utf-8 -*-
"""
web_app/cache.py
Caché en memoria con TTL (Time-To-Live) simple.
Sin dependencias externas — no requiere Redis.

Uso:
    from web_app.cache import cache

    # Guardar
    cache.set("kpis:empresa_db", datos, ttl=120)

    # Leer (devuelve None si no existe o expiró)
    datos = cache.get("kpis:empresa_db")

    # Invalidar todas las claves que empiezan con un prefijo
    cache.invalidar("kpis:")
"""

import threading
import time


class _TTLCache:
    """Dict con expiración por clave. Thread-safe."""

    def __init__(self):
        self._store: dict[str, tuple[object, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, exp = entry
            if time.monotonic() > exp:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value, ttl: int = 60):
        """Almacena value con expiración de ttl segundos."""
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    def invalidar(self, prefijo: str = ""):
        """Elimina todas las claves que empiezan con prefijo (o todas si prefijo='')."""
        with self._lock:
            if not prefijo:
                self._store.clear()
            else:
                claves = [k for k in self._store if k.startswith(prefijo)]
                for k in claves:
                    del self._store[k]

    def stats(self) -> dict:
        with self._lock:
            ahora = time.monotonic()
            vivas  = sum(1 for _, (_, exp) in self._store.items() if ahora <= exp)
            return {"entradas_total": len(self._store), "entradas_vivas": vivas}


# Instancia global compartida por toda la app
cache = _TTLCache()

# TTLs en segundos
TTL_KPIS       = 120   # KPIs del dashboard: 2 minutos
TTL_CATALOGOS  = 300   # Listas de catálogos (clientes, productos, proveedores): 5 minutos
TTL_CATEGORIAS = 600   # Categorías y subcategorías: 10 minutos
