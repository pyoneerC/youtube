# Usar una imagen base oficial de Python 3.11
FROM python:3.11-slim

# Establecer variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt y script de instalación
COPY requirements.txt install.sh ./

# Hacer ejecutable el script de instalación
RUN chmod +x install.sh

# Instalar dependencias de Python usando nuestro script personalizado
RUN ./install.sh

# Copiar el resto del código de la aplicación
COPY . .

# Crear un usuario no root para ejecutar la aplicación
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Exponer el puerto que usa la aplicación
EXPOSE 8000

# Configurar variables de entorno para producción
ENV FLASK_ENV=production \
    GUNICORN_WORKERS=4 \
    GUNICORN_THREADS=2 \
    PORT=8000

# Comando para ejecutar la aplicación
CMD gunicorn --workers=${GUNICORN_WORKERS} \
    --threads=${GUNICORN_THREADS} \
    --bind=0.0.0.0:${PORT} \
    --timeout=120 \
    --access-logfile=- \
    --error-logfile=- \
    app:app
