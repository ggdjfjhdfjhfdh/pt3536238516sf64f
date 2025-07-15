FROM python:3.12-slim
WORKDIR /app
COPY services/api-fastapi/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/api-fastapi/app app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
