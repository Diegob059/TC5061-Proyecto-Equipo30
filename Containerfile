# ==============================================================================
# Containerfile — MiBici Risk API (FastAPI + LightGBM Runtime)
# Estándar OCI compatible con Podman y Docker
# ==============================================================================
FROM python:3.12-slim

LABEL org.opencontainers.image.title="MiBici Risk Prediction API" \
      org.opencontainers.image.description="API REST de inferencia de riesgo operativo en estaciones MiBici" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="MLOps Equipo 30"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Instalar runtime OpenMP requerido por LightGBM en Linux (libgomp1)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias fijadas y aisladas de la API
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copiar el paquete de la API
COPY api ./api

EXPOSE 8000

# Healthcheck nativo para validación de contenedor
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
