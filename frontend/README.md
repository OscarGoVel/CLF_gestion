# CLF Gestión — Frontend

SPA React para el sistema ERP CLF. Consume la API REST del backend FastAPI.

## Stack

- React 19.2 + Vite 8 + React Router DOM v7
- PWA (vite-plugin-pwa) — instalable en móvil y desktop
- CSS custom properties — design system en `src/index.css`

## Variables de entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `VITE_API_URL` | URL base del backend | `http://localhost:8000` |

En producción, Firebase Hosting reescribe `/api/*` al backend de Cloud Run, por lo que `VITE_API_URL` queda vacío en `.env.production`.

## Desarrollo local

```bash
npm install
npm run dev          # http://localhost:5173 — proxy a localhost:8000
```

## Build

```bash
npm run build        # genera frontend/dist/
npm run preview      # sirve el build localmente para verificar
```

## Lint y formato

```bash
npm run lint         # ESLint
npm run format       # Prettier (formatea src/)
```

## Estructura

```
src/
├── pages/           ← una carpeta por módulo (cotizaciones/, crm/, etc.)
├── components/      ← design system: DataTable, Modal, StatusBadge, KpiCard…
├── hooks/           ← useFetch, useAuth
├── lib/             ← apiClient.js (HTTP centralizado), toast.js
└── contexts/        ← RazonSocialContext (multi-empresa)
```

## Componentes reutilizables

| Componente | Uso |
|------------|-----|
| `StatusBadge` | Badge de estado semántico |
| `DataTable` | Tabla con sort client-side |
| `KpiCard` / `KpiGrid` | Métricas ejecutivas |
| `Modal` / `ConfirmModal` | Overlays |
| `SectionCard` | Contenedor con título |
| `EmptyState` | Estado vacío con CTA |
| `FilterChips` | Chips de filtro con conteo |
| `SidePreview` + `FieldGrid` | Panel lateral de detalles |
| `Historial` | Timeline de eventos por entidad |
| `Stepper` | Indicador de pasos |
| `TableStates` | Loading/Empty rows para tablas |
