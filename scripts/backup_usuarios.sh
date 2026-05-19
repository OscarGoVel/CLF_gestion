#!/bin/bash
# Backup de clf_usuarios a Google Cloud Storage.
# Ejecutar manualmente o configurar en Cloud Scheduler.
#
# Prerequisito: gcloud auth login && gcloud config set project clf-gestion
# Crear bucket si no existe: gsutil mb gs://clf-gestion-backups
#
# Para automatizar con Cloud Scheduler:
#   gcloud scheduler jobs create http clf-usuarios-backup \
#     --schedule="0 3 * * *" \
#     --uri="https://sqladmin.googleapis.com/sql/v1beta4/projects/clf-gestion/instances/clf-db-instance/export" \
#     --message-body='{"exportContext":{"kind":"sql#exportContext","fileType":"SQL","uri":"gs://clf-gestion-backups/clf_usuarios_$(date +%Y%m%d).sql","databases":["clf_usuarios"]}}' \
#     --oauth-service-account-email=<SERVICE_ACCOUNT>

set -e

PROJECT="clf-gestion"
INSTANCE="clf-db-instance"
BUCKET="gs://clf-gestion-backups"
DB="clf_usuarios"
FECHA=$(date +%Y%m%d_%H%M%S)
DESTINO="${BUCKET}/clf_usuarios_${FECHA}.sql"

echo "Exportando ${DB} → ${DESTINO} ..."

gcloud sql export sql "${INSTANCE}" "${DESTINO}" \
  --project="${PROJECT}" \
  --database="${DB}" \
  --offload

echo "Backup completado: ${DESTINO}"

# Limpiar backups con más de 30 días
echo "Limpiando backups de más de 30 días..."
gsutil ls "${BUCKET}/clf_usuarios_*.sql" | while read -r obj; do
  age_days=$(( ( $(date +%s) - $(gsutil stat "$obj" | grep "Creation time" | awk -F: '{print $2":"$3":"$4}' | xargs -I{} date -d "{}" +%s 2>/dev/null || echo 0) ) / 86400 ))
  if [ "$age_days" -gt 30 ]; then
    gsutil rm "$obj"
    echo "Eliminado: $obj"
  fi
done

echo "Listo."
