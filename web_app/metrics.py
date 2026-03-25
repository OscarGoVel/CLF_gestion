# -*- coding: utf-8 -*-
"""
web_app/metrics.py
Motor de metricas en memoria para CLF Gestion Web.

Registra sin dependencias externas (no Prometheus, no Grafana).
Thread-safe: usa locks para que multiples workers no corrompan contadores.

Metricas que recopila:
  · Tiempo de respuesta por ruta (avg, p95, max)
  · Conteo de requests por ruta y metodo HTTP
  · Distribucion de codigos de estado (2xx, 3xx, 4xx, 5xx)
  · Requests activos en este momento
  · Errores recientes (ultimas 50 excepciones)
  · Uptime desde que arranco el servidor
"""

import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Estructuras de datos
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RouteStats:
    """Estadisticas acumuladas de una ruta especifica."""
    count:        int   = 0
    errors:       int   = 0        # respuestas >= 400
    total_ms:     float = 0.0
    max_ms:       float = 0.0
    # Ventana deslizante de los ultimos 200 tiempos (para p95)
    tiempos:      deque = field(default_factory=lambda: deque(maxlen=200))

    def registrar(self, ms: float, status: int):
        self.count     += 1
        self.total_ms  += ms
        self.max_ms     = max(self.max_ms, ms)
        self.tiempos.append(ms)
        if status >= 400:
            self.errors += 1

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.tiempos:
            return 0.0
        sorted_t = sorted(self.tiempos)
        idx = max(0, int(len(sorted_t) * 0.95) - 1)
        return sorted_t[idx]

    @property
    def error_pct(self) -> float:
        return (self.errors / self.count * 100) if self.count else 0.0


@dataclass
class ErrorReciente:
    ts:     str
    ruta:   str
    status: int
    detalle: str


# ─────────────────────────────────────────────────────────────────────────────
# Registro global de metricas
# ─────────────────────────────────────────────────────────────────────────────

class MetricsRegistry:

    def __init__(self):
        self._lock          = threading.Lock()
        self._inicio        = time.monotonic()
        self._inicio_dt     = datetime.now(timezone.utc)

        # Contadores globales
        self._total         = 0
        self._activos       = 0          # requests en vuelo ahora mismo
        self._status_codes  = defaultdict(int)

        # Por ruta: clave = "METHOD /path"
        self._rutas: dict[str, RouteStats] = defaultdict(RouteStats)

        # Errores recientes
        self._errores: deque[ErrorReciente] = deque(maxlen=50)

    # ── Registro ─────────────────────────────────────────────────────────────

    def request_inicio(self) -> float:
        """Llama al iniciar cada request. Retorna timestamp de inicio."""
        with self._lock:
            self._activos += 1
        return time.monotonic()

    def request_fin(self, inicio: float, metodo: str, path: str, status: int):
        """Llama al terminar cada request con su duracion y status."""
        ms = (time.monotonic() - inicio) * 1000
        clave = f"{metodo} {path}"
        with self._lock:
            self._activos       = max(0, self._activos - 1)
            self._total        += 1
            self._status_codes[status] += 1
            self._rutas[clave].registrar(ms, status)
            if status >= 400:
                self._errores.append(ErrorReciente(
                    ts=datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    ruta=clave,
                    status=status,
                    detalle="",
                ))

    def registrar_excepcion(self, metodo: str, path: str, exc: str):
        """Registra una excepcion no controlada (500)."""
        with self._lock:
            self._errores.append(ErrorReciente(
                ts=datetime.now(timezone.utc).strftime("%H:%M:%S"),
                ruta=f"{metodo} {path}",
                status=500,
                detalle=str(exc)[:120],
            ))

    # ── Lectura ───────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Retorna un snapshot consistente de todas las metricas."""
        with self._lock:
            uptime_s = time.monotonic() - self._inicio

            total         = self._total
            activos       = self._activos
            status_codes  = dict(self._status_codes)
            errores       = list(self._errores)

            # Top 15 rutas por numero de requests
            rutas_raw = {k: v for k, v in self._rutas.items()
                         if not k.endswith(("/health", "/static"))}
            top_rutas = sorted(rutas_raw.items(),
                               key=lambda x: x[1].count, reverse=True)[:15]

            # Tiempos globales (de todas las rutas)
            todos_tiempos: list[float] = []
            for rs in self._rutas.values():
                todos_tiempos.extend(rs.tiempos)

        # Calcular metricas globales fuera del lock
        total_2xx = sum(v for k, v in status_codes.items() if 200 <= k < 300)
        total_4xx = sum(v for k, v in status_codes.items() if 400 <= k < 500)
        total_5xx = sum(v for k, v in status_codes.items() if k >= 500)

        avg_ms = (sum(todos_tiempos) / len(todos_tiempos)) if todos_tiempos else 0
        if todos_tiempos:
            sorted_t = sorted(todos_tiempos)
            p95_ms = sorted_t[max(0, int(len(sorted_t) * 0.95) - 1)]
            max_ms = sorted_t[-1]
        else:
            p95_ms = max_ms = 0

        horas, rem = divmod(int(uptime_s), 3600)
        minutos, segs = divmod(rem, 60)

        return {
            "uptime":      f"{horas:02d}:{minutos:02d}:{segs:02d}",
            "uptime_s":    uptime_s,
            "inicio_dt":   self._inicio_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total":       total,
            "activos":     activos,
            "avg_ms":      round(avg_ms, 1),
            "p95_ms":      round(p95_ms, 1),
            "max_ms":      round(max_ms, 1),
            "total_2xx":   total_2xx,
            "total_4xx":   total_4xx,
            "total_5xx":   total_5xx,
            "error_rate":  round((total_4xx + total_5xx) / total * 100, 1) if total else 0,
            "status_codes": dict(sorted(status_codes.items())),
            "top_rutas":   [
                {
                    "ruta":      ruta,
                    "count":     rs.count,
                    "avg_ms":    round(rs.avg_ms, 1),
                    "p95_ms":    round(rs.p95_ms, 1),
                    "max_ms":    round(rs.max_ms, 1),
                    "errors":    rs.errors,
                    "error_pct": round(rs.error_pct, 1),
                }
                for ruta, rs in top_rutas
            ],
            "errores_recientes": [
                {"ts": e.ts, "ruta": e.ruta, "status": e.status, "detalle": e.detalle}
                for e in reversed(errores)
            ],
        }


# Instancia global
registry = MetricsRegistry()
