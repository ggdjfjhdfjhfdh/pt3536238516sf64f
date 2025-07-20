FROM python:3.12-slim

WORKDIR /app

# Crear directorio para plantillas
RUN mkdir -p /app/templates

# Copiar archivos necesarios para la instalación del paquete
COPY setup.py .
COPY pentest/ pentest/


RUN apt-get update && \
    # ───── utilidades básicas ───── 
    apt-get install -y --no-install-recommends \
        curl wget git ca-certificates build-essential \
        bsdmainutils dnsutils hexdump \
    \
    # ───── dependencias para WeasyPrint y GObject ───── 
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
        libgobject-2.0-0 libgobject-2.0-dev libgirepository-1.0-1 \
        gir1.2-glib-2.0 libcairo2 libfontconfig1 \
        libjpeg62-turbo libgif7 libpng16-16 \
        libfribidi0 libxml2 libxslt1.1 \
        wkhtmltopdf \
    \
    # ───── herramientas de seguridad ───── 
    && wget -qO /usr/local/bin/httpx      https://github.com/projectdiscovery/httpx/releases/download/v1.6.3/httpx_1.6.3_linux_amd64  && chmod +x /usr/local/bin/httpx \
    && wget -qO /usr/local/bin/subfinder  https://github.com/projectdiscovery/subfinder/releases/download/v2.6.6/subfinder_2.6.6_linux_amd64  && chmod +x /usr/local/bin/subfinder \
    && apt-get install -y amass \
    && pip install --no-cache-dir dnstwist \
    && rm -rf /var/lib/apt/lists/*

# Ya no usamos nuclei ni testssl.sh, hemos implementado análisis manuales

# Copiar templates y configurar el worker
COPY templates/ /app/templates/

# Instalar el paquete pentest y dependencias adicionales
RUN pip install -e . \
    && pip install --no-cache-dir mailersend==0.6.0 reportlab==4.1.0 redis==5.0.4 requests==2.32.3 jinja2==3.1.4 weasyprint==62.2

CMD ["pentest-worker"]
