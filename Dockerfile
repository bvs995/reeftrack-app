# ==============================================================================
# 🌊 AquaPulse Backend - Production Multi-Stage Dockerfile
# ==============================================================================

# Build Stage
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python en wheels
COPY backend/requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Runtime Stage
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Instalar solo librerías de tiempo de ejecución (libpq y curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias precompiladas desde builder
COPY --from=builder /install /usr/local

# Crear usuario sin privilegios por seguridad
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Copiar código del backend
COPY backend /app/backend

# Permisos para el usuario no-root
RUN chown -R appuser:appgroup /app

USER appuser

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    ALLOWED_ORIGINS="*" \
    DB_POOL_SIZE=10 \
    DB_MAX_OVERFLOW=20

EXPOSE 8000

# Health Check periódico
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Comando de arranque para producción con workers de Uvicorn
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
