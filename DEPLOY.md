# CLF Gestión — Instructivo de Deploy

## URLs de producción

| Servicio | URL |
|---|---|
| Frontend (Firebase Hosting) | https://clf-gestion.web.app |
| Backend (Cloud Run) | https://clfgestion-ipf4b7xrrq-uc.a.run.app |
| Firebase Console | https://console.firebase.google.com/project/clf-gestion |

---

## Prerequisitos

- `gcloud` CLI autenticado: `gcloud auth login`
- `firebase` CLI instalado: `npm install -g firebase-tools`
- Proyecto activo: `gcloud config set project clf-gestion`

---

## Deploy solo Frontend

Usar cuando solo cambian archivos en `frontend/src/`.

```bash
# 1. Build
cd frontend
npm run build

# 2. Deploy a Firebase Hosting
cd ..
firebase deploy --only hosting
```

---

## Deploy solo Backend

Usar cuando cambian archivos en `web_app/`, `core/`, `requirements_web.txt` o `Dockerfile`.

```bash
# 1. Build imagen y push a GCR
gcloud builds submit --tag gcr.io/clf-gestion/clfgestion

# 2. Deploy a Cloud Run
gcloud run deploy clfgestion \
  --image gcr.io/clf-gestion/clfgestion \
  --platform managed \
  --region us-central1
```

---

## Deploy completo (Frontend + Backend)

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Build y push backend
gcloud builds submit --tag gcr.io/clf-gestion/clfgestion

# Deploy backend
gcloud run deploy clfgestion --image gcr.io/clf-gestion/clfgestion --platform managed --region us-central1


# Deploy frontend
firebase deploy --only hosting
```

---

## ¿Qué desplegar según los cambios?

| Archivos modificados | Frontend | Backend |
|---|---|---|
| `frontend/src/**` | ✅ | ❌ |
| `web_app/**`, `core/**` | ❌ | ✅ |
| `requirements_web.txt`, `Dockerfile` | ❌ | ✅ |
| Ambos | ✅ | ✅ |

---

## Estructura del proyecto en GCP

- **Proyecto GCP:** `clf-gestion`
- **Servicio Cloud Run:** `clfgestion` · región `us-central1`
- **Imagen Docker:** `gcr.io/clf-gestion/clfgestion`
- **Firebase Hosting:** proyecto `clf-gestion` · directorio público `frontend/dist`
- **Base de datos:** Cloud SQL PostgreSQL
  - `clf_usuarios` — base global (usuarios, empresas)
  - `clf_empresa` — base por empresa (datos operativos)

---

## Verificar deploy

```bash
# Ver revisiones activas de Cloud Run
gcloud run revisions list --service clfgestion --region us-central1

# Ver último deploy de Firebase
firebase hosting:channel:list
```
