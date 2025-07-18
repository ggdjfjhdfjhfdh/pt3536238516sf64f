FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .

# Crear directorio para plantillas
RUN mkdir -p /app/templates

RUN apt-get update && \
    # ───── utilidades básicas ───── 
    apt-get install -y --no-install-recommends \
        curl wget git ca-certificates build-essential \
        bsdmainutils dnsutils hexdump \
    \
    # ───── dependencias para WeasyPrint ───── 
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
        libjpeg62-turbo libgif7 libpng16-16 \
    \
    # ───── herramientas de seguridad ───── 
    && wget -qO /usr/local/bin/httpx      https://github.com/projectdiscovery/httpx/releases/download/v1.6.3/httpx_1.6.3_linux_amd64  && chmod +x /usr/local/bin/httpx \
    && wget -qO /usr/local/bin/subfinder  https://github.com/projectdiscovery/subfinder/releases/download/v2.6.6/subfinder_2.6.6_linux_amd64  && chmod +x /usr/local/bin/subfinder \
    && apt-get install -y amass \
    && pip install --no-cache-dir dnstwist \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

# Ya no usamos nuclei ni testssl.sh, hemos implementado análisis manuales

COPY run_scan.py entrypoint.sh ./
COPY templates/* /app/templates/
RUN chmod +x /app/entrypoint.sh
CMD ["/app/entrypoint.sh"]
