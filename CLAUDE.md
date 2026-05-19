# CLF Gestión — Contexto para Claude Code

## Cómo cargar contexto antes de trabajar

Este proyecto tiene documentación completa en el Obsidian Vault. Leer en este orden según la tarea:

### Siempre leer primero (contexto mínimo)
```
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\AGENTS.md
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\ai\memory\clf-summary.md
```

### Para trabajo en un módulo específico
```
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\projects\clf_system\CLF_Mod_<Nombre>.md
```

### Para decisiones arquitectónicas o bugs complejos
```
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\ai\agents\codex.md
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\decisions\ADR-00X-<tema>.md
```

### Para contexto completo del stack
```
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\ai\context\architecture-overview.md
```

---

## Stack (resumen rápido)

- **Frontend:** React 19.2.5 + Vite + React Router v7 — `frontend/src/`
- **Backend:** FastAPI + Python 3.11 — `web_app/`
- **DB:** PostgreSQL (`clf_usuarios` global + `clf_empresa` por empresa)
- **Auth:** JWT HS256 8h + PBKDF2 200k iter
- **Deploy:** Docker + Cloud Run (GCP) + Firebase Hosting

---

## Reglas de implementación

### React
- Wireframe-first: HTML funcional con datos reales antes que estilos
- Usar React Router v7: `<Link>`, `useNavigate()` — nunca `window.location`
- Reutilizar componentes existentes: `Pill.jsx`, `Stepper.jsx`, `NextRibbon.jsx`, `DataTable.jsx`, `SidePreview.jsx`, `FilterChips.jsx`, `KpiCard.jsx`, `Modal.jsx`, `TableStates.jsx`, `MobileNav.jsx`
- No crear abstracciones sin necesidad explícita

### FastAPI
- Lógica de negocio en `core/`, no en `routers/`
- Solo crear nuevos routers `api_*.py` — los routers Jinja en `web_app/` son legacy, no modificar
- Cada endpoint extrae empresa_id del JWT: `get_current_user()` → `get_db_empresa(empresa_id)`

### General
- No refactorizar código no relacionado con la tarea
- No agregar manejo de errores para escenarios imposibles
- Commits atómicos: un commit por feature/fix
- No escribir comentarios que expliquen qué hace el código

---

## Estructura del proyecto

```
CLF_gestion/
├── frontend/
│   └── src/
│       ├── pages/          ← páginas React (una por módulo)
│       ├── components/     ← Pill, Stepper, NextRibbon, DataTable, SidePreview, FilterChips, KpiCard, Modal, TableStates, MobileNav
│       └── App.jsx         ← rutas principales
├── web_app/
│   ├── routers/
│   │   ├── api_*.py        ← API REST activa (React)
│   │   └── *.py            ← routers Jinja legacy (no modificar)
│   ├── core/               ← lógica de negocio
│   ├── auth.py, rbac.py    ← autenticación y roles
│   └── database.py         ← conexiones PostgreSQL
└── CLAUDE.md               ← este archivo
```

---

## Estado actual (Fase 5 — Nuevos KPIs)

Todos los módulos React están en producción. Fases 1–4 completadas.

Pendiente de Fase 4: migrar validación de montos al cambiar estado de cotización a PATCH endpoint
en `api_cotizaciones.py` (actualmente solo en router Jinja legacy `cotizaciones.py:782`).

KPIs pendientes para Fase 5 (ver `CLF_Plan_Maestro.md`):
1. Tasa de conversión (`resultado` + `motivo_perdida`) → requiere campo nuevo en `cotizaciones`
2. DSO por cliente → `api_estado_cuenta.py`
3. Días de inventario por producto → `api_stock.py`
4. Aging de cartera global en Análisis
5. Alertas de margen negativo (líneas con `costo_compra > costo_snapshot`)

---

## Plan maestro completo

```
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\projects\clf_system\CLF_Plan_Maestro.md
```
