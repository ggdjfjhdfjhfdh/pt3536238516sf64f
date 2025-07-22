# Pentest Express API

Escáner de seguridad modular y tipado para análisis automatizado de dominios.

## Características

- Reconocimiento de subdominios
- Fingerprinting de hosts activos
- Escaneo de vulnerabilidades

- Detección de credenciales filtradas
- Detección de dominios typosquatting
- Generación de informes PDF
- Notificaciones por email

## Estructura

```
pentest/
├── __init__.py
├── core.py        (CLI / entry-point)
├── config.py      (constantes, rutas, time-outs)
├── runners.py     (run_cmd, ThreadPool wrapper)
├── exceptions.py  (excepciones personalizadas)
├── http.py        (sesión HTTP con retries)
├── recon.py       (reconocimiento de subdominios)
├── fingerprint.py (detección de hosts activos)
├── nuclei_scan.py (escaneo de vulnerabilidades)

├── leaks.py       (búsqueda de credenciales filtradas)
├── typosquat.py   (detección de dominios typosquatting)
└── report.py      (generación de informes)
```

## Instalación

```bash
pip install -e .
```

## Requisitos

- Python 3.8+
- Redis
- Herramientas externas:
  - amass / subfinder (reconocimiento)
  - httpx (fingerprinting)
  - nuclei (escaneo de vulnerabilidades)
  - dnstwist (detección de typosquatting)

## Variables de entorno

- `REDIS_URL`: URL de conexión a Redis (default: `redis://redis:6379/0`)
- `HIBP_API_KEY`: Clave API para Have I Been Pwned
- `MAILERSEND_API_KEY`: Clave API para MailerSend

## Uso

### Como worker

```bash
pentest-worker
```

### Como librería

```python
from pentest.core import generate_pdf

pdf_path = generate_pdf(
    domain="example.com",
    recipient_email="cliente@example.com",
    debug=True,
    hibp_api_key="tu-api-key"
)
print(f"Informe generado: {pdf_path}")
```

## Mejoras implementadas

- Código modular y tipado
- Logging centralizado
- Función `run_cmd()` centralizada y segura
- ThreadPoolExecutor global reutilizable
- Sesión HTTP con retries
- Corrección de `check_leaks` para usar la API correcta
- Excepciones personalizadas
- Plantillas Jinja2 pre-compiladas
- Limpieza de directorio temporal solo si todo OK