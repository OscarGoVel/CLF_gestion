# Usar una imagen ligera de Python
FROM python:3.11-slim

# Evitar que Python genere archivos .pyc y permitir que los logs se vean en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo en el contenedor
WORKDIR /app

# Instalar dependencias del sistema necesarias (si las hay, para psycopg2-binary usualmente no hace falta mucho en slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar el archivo de requerimientos e instalar dependencias
COPY requirements_web.txt .
RUN pip install --no-cache-dir -r requirements_web.txt

# Copiar las carpetas necesarias del proyecto
COPY web_app/ ./web_app/
COPY core/ ./core/
COPY assets/ ./assets/
COPY app_config.py .

# Puerto estandar que usa Cloud Run
EXPOSE 8080

# Comando para iniciar la aplicacion
# Cloud Run inyecta la variable de entorno PORT, asi que la usamos por seguridad
CMD ["sh", "-c", "uvicorn web_app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
