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
- Reutilizar componentes existentes: `StatusBadge.jsx`, `EmptyState.jsx`, `SectionCard.jsx`, `KpiCard.jsx`, `DataTable.jsx`, `SidePreview.jsx`, `FilterChips.jsx`, `Modal.jsx`, `ConfirmModal.jsx`, `TableStates.jsx`, `Historial.jsx`, `Stepper.jsx`, `NextRibbon.jsx`
- `Pill.jsx` y `MobileNav.jsx` están deprecados — no usar
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
│       ├── components/     ← StatusBadge, EmptyState, SectionCard, KpiCard, DataTable, SidePreview,
│       │                      FilterChips, Modal, ConfirmModal, TableStates, Historial, Stepper, NextRibbon
│       └── App.jsx         ← rutas principales (estructura /panel, /comercial/*, /abastecimiento/*, etc.)
├── web_app/
│   ├── routers/
│   │   ├── api_*.py        ← API REST activa (React)
│   │   └── *.py            ← routers Jinja legacy (no modificar)
│   ├── migrations/         ← Alembic: versiones en versions/NNNN_*.py
│   ├── core/               ← lógica de negocio
│   ├── historial.py        ← registro de eventos por entidad
│   ├── auth.py, rbac.py    ← autenticación y roles
│   └── database.py         ← conexiones PostgreSQL
└── CLAUDE.md               ← este archivo
```

---

## Estado actual (Fases 1–17 completas — Fase 15 casi lista)

Todos los módulos React en producción. Sidebar colapsable (Fase 16) y sistema de diseño (Fase 17) completos.

**Rutas actuales (post Fase 16):**

- `/panel` — Dashboard
- `/comercial/cotizaciones*` — Cotizaciones
- `/comercial/crm*` — CRM / Pipeline
- `/comercial/clientes` — Clientes
- `/comercial/devoluciones*` — Devoluciones
- `/abastecimiento/compras*` — Compras
- `/abastecimiento/proveedores` — Proveedores
- `/abastecimiento/estudios*` — Estudio de mercado
- `/inventario/stock*` — Stock
- `/inventario/conteos*` — Pre-inventario
- `/inventario/productos*` — Productos
- `/documentos/cfdi*` — Facturas / CFDI
- `/finanzas/cobranza*` — Estado de Cuenta (API: `/api/finanzas/cobranza`)
- `/finanzas/cuentas-pagar` — Cuentas por Pagar
- `/finanzas/costos-fijos*` — Costos Fijos
- `/reportes` — Análisis
- `/admin` — Admin

**Pendiente único (Fase 15):**

- Notificaciones automáticas al cambiar estado de cotización (SendGrid/Twilio)

**Migraciones:** Usar Alembic. Nuevas migraciones en `web_app/migrations/versions/NNNN_*.py`. NO poner SQL en `main.py`.

---

## Plan maestro completo

```
C:\Users\oscar\OneDrive\Documentos\Obsidian Vault\projects\clf_system\CLF_Plan_Maestro.md
```
