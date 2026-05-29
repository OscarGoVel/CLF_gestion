# -*- coding: utf-8 -*-
import hashlib
import mimetypes
import re
from pathlib import Path

_ALLOWED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
_MAX_BYTES    = 5 * 1024 * 1024  # 5 MB


def _nombre_seguro(nombre: str) -> str:
    stem = Path(nombre).stem
    stem = stem.lower().strip()
    stem = re.sub(r"[^a-z0-9_-]", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    return stem[:40] or "imagen"


def subir_imagen(contenido: bytes, nombre_original: str, empresa_db: str, bucket_name: str) -> str:
    """
    Sube `contenido` a GCS y retorna la URL pública permanente.
    La visibilidad pública la otorga la política IAM del bucket (allUsers objectViewer).
    """
    if not bucket_name:
        raise RuntimeError("GCS_IMAGES_BUCKET no configurado en variables de entorno.")
    if len(contenido) > _MAX_BYTES:
        raise ValueError(f"La imagen excede el límite de {_MAX_BYTES // 1024 // 1024} MB.")
    mime, _ = mimetypes.guess_type(nombre_original)
    if mime not in _ALLOWED_MIME:
        raise ValueError(f"Tipo de archivo no permitido: {mime}. Acepta: PNG, JPEG, GIF, WEBP, SVG.")
    ext       = Path(nombre_original).suffix.lower()
    digest    = hashlib.sha256(contenido).hexdigest()[:8]
    nombre    = _nombre_seguro(nombre_original)
    blob_name = f"crm_imagenes/{empresa_db}/{digest}_{nombre}{ext}"
    from google.cloud import storage as gcs
    blob = gcs.Client().bucket(bucket_name).blob(blob_name)
    blob.upload_from_string(contenido, content_type=mime)
    return blob.public_url


def listar_imagenes(empresa_db: str, bucket_name: str) -> list[dict]:
    if not bucket_name:
        return []
    from google.cloud import storage as gcs
    client = gcs.Client()
    blobs  = client.list_blobs(bucket_name, prefix=f"crm_imagenes/{empresa_db}/")
    return [
        {"nombre": Path(b.name).name, "url": b.public_url, "size_kb": round(b.size / 1024, 1)}
        for b in blobs
    ]
