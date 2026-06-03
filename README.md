# CLF Gestión — ERP Logístico B2B

Sistema de gestión operativa para **CLF (Comercializadora Logística Fuerza Yucateca)**, Yucatán, México. Cubre el ciclo completo: cotización → compra → inventario → factura CFDI 4.0.

## Stack

| Capa | Tecnología |
|------|------------|
| Frontend | React 19 + Vite + React Router v7 — Firebase Hosting |
| Backend | FastAPI + Python 3.11 + Uvicorn — Cloud Run (GCP) |
| Base de datos | PostgreSQL — Cloud SQL (GCP) |
| Auth | JWT HS256 (8 h) + PBKDF2-HMAC-SHA256 200 k iter |
| Migraciones | Alembic |
| Storage | Google Cloud Storage (XMLs de facturas) |

## Módulos

| Módulo | Ruta |
|--------|------|
| Dashboard | `/panel` |
| Cotizaciones | `/comercial/cotizaciones` |
| CRM / Pipeline | `/comercial/crm` |
| Clientes | `/comercial/clientes` |
| Devoluciones | `/comercial/devoluciones` |
| Compras | `/abastecimiento/compras` |
| Proveedores | `/abastecimiento/proveedores` |
| Estudio de mercado | `/abastecimiento/estudios` |
| Stock | `/inventario/stock` |
| Pre-inventario | `/inventario/conteos` |
| Productos | `/inventario/productos` |
| Documentos CFDI | `/documentos/cfdi` |
| Cobranza (CxC) | `/finanzas/cobranza` |
| Cuentas por pagar | `/finanzas/cuentas-pagar` |
| Costos fijos | `/finanzas/costos-fijos` |
| Reportes | `/reportes` |
| Admin | `/admin` |

## Setup local

### Requisitos previos

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (o acceso a Cloud SQL via proxy)
- `gcloud` CLI (para Cloud SQL en dev)

### Backend

```bash
# 1. Instalar dependencias
pip install -r requirements_web.txt
pip install -r requirements-dev.txt  # para tests

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales locales

# 3. Configurar empresas
cp config.json.example config.json  # o preguntar al equipo
# config.json no se versiona (credenciales de BD por empresa)

# 4. Levantar el servidor
uvicorn web_app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# 1. Instalar dependencias
npm install

# 2. Configurar entorno
# Para desarrollo local ya existe .env.development con VITE_API_URL=http://localhost:8000

# 3. Levantar el servidor de desarrollo
npm run dev
# Disponible en http://localhost:5173
```

### Ejecutar tests

```bash
pytest tests/ -v
```

## Estructura del proyecto

```
CLF_gestion/
├── frontend/           ← SPA React (Vite)
│   └── src/
│       ├── pages/      ← una carpeta por módulo de negocio
│       ├── components/ ← componentes reutilizables del design system
│       ├── hooks/      ← useFetch, useAuth, etc.
│       ├── lib/        ← apiClient.js, toast.js
│       └── contexts/   ← RazonSocialContext
├── web_app/            ← API FastAPI
│   ├── routers/
│   │   └── api_*.py    ← endpoints REST activos (uno por módulo)
│   ├── migrations/     ← versiones Alembic (NNNN_*.py)
│   ├── core/           ← lógica de negocio desacoplada
│   ├── auth.py         ← hashing y JWT
│   ├── rbac.py         ← roles y permisos granulares
│   ├── database.py     ← pool de conexiones por empresa
│   └── main.py         ← app FastAPI, middleware, lifespan
├── core/               ← módulos de dominio compartidos
├── tests/              ← suite pytest (integration + API)
├── docs/               ← documentación adicional
├── Dockerfile          ← imagen de producción (Python 3.11-slim)
├── requirements_web.txt
├── requirements-dev.txt
└── alembic.ini
```

## Arquitectura multi-empresa

Cada empresa tiene su propio pool de conexiones hacia su base de datos `clf_empresa`. La base global `clf_usuarios` almacena usuarios, roles y auditoría. El `empresa_db` viaja en el JWT y se valida en cada request.

## Variables de entorno

Ver [`.env.example`](.env.example) para la lista completa. Las variables críticas de producción están documentadas en [`env-cloudrun.yaml.example`](env-cloudrun.yaml.example).

## Deploy

Ver [`docs/deploy.md`](docs/deploy.md) para instrucciones detalladas de despliegue en Firebase Hosting (frontend) y Cloud Run (backend).

## Tests

```bash
# Correr toda la suite
pytest tests/ -v

# Solo un módulo
pytest tests/test_api_cotizaciones.py -v

# Con cobertura
pytest tests/ --cov=web_app --cov-report=term-missing
```

Los tests usan `httpx.AsyncClient` con `ASGITransport` — no requieren servidor levantado, pero sí una base de datos PostgreSQL accesible según las variables de entorno.
