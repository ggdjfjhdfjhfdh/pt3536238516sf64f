FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
COPY services/api-fastapi/requirements.txt services/api-fastapi/
RUN pip install --no-cache-dir -r requirements.txt \
    -r services/api-fastapi/requirements.txt

COPY services/api-fastapi/app services/api-fastapi/app
COPY . .
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.api-fastapi.app.main:app", "--host", "0.0.0.0", "--port", "8000"]