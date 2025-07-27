FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
COPY services/api-fastapi/requirements.txt services/api-fastapi/
COPY fix-dependencies.py .

# Instalar dependencias con resolución de conflictos
RUN pip install --upgrade pip && \
    pip install --no-cache-dir 'anyio>=3.7.1,<5.0.0' && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r services/api-fastapi/requirements.txt && \
    python fix-dependencies.py

COPY services/api-fastapi/app services/api-fastapi/app
COPY . .
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.api-fastapi.app.main:app", "--host", "0.0.0.0", "--port", "8000"]