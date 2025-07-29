FROM python:3.12-slim
WORKDIR /app

# Instalar herramientas de compilación necesarias para nassl/sslyze
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY services/api-fastapi/requirements.txt services/api-fastapi/
COPY fix-dependencies.py .

# Instalar dependencias con resolución de conflictos
RUN pip install --upgrade pip && \
    pip install --no-cache-dir 'anyio>=3.7.1,<5.0.0' && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r services/api-fastapi/requirements.txt && \
    python fix-dependencies.py

# Copiar archivos del proyecto
COPY services/api-fastapi/app services/api-fastapi/app
COPY . .

# Copiar plantillas a la ubicación esperada por Docker
COPY templates/ /app/templates/
# Crear directorio pentest/templates y copiar desde templates principal
RUN mkdir -p /app/pentest/templates
COPY templates/report.html /app/pentest/templates/report.html
COPY templates/report_enhanced.html /app/pentest/templates/report_enhanced.html

# Instalar el paquete pentest para asegurar que las plantillas estén disponibles
RUN pip install -e .

ENV PYTHONPATH=/app
CMD ["uvicorn", "services.api-fastapi.app.main:app", "--host", "0.0.0.0", "--port", "8000"]