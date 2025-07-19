FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .

# Crear directorio para plantillas
RUN mkdir -p /app/templates

RUN apk add --no-cache \
    libgobject-2.0 \
    libpango-1.0 \
    harfbuzz \
    libfontconfig \
    libjpeg-turbo \
    openjpeg

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
    \
    # ───── herramientas de seguridad ───── 
    && wget -qO /usr/local/bin/httpx      https://github.com/projectdiscovery/httpx/releases/download/v1.6.3/httpx_1.6.3_linux_amd64  && chmod +x /usr/local/bin/httpx \
    && wget -qO /usr/local/bin/subfinder  https://github.com/projectdiscovery/subfinder/releases/download/v2.6.6/subfinder_2.6.6_linux_amd64  && chmod +x /usr/local/bin/subfinder \
    && apt-get install -y amass \
    && pip install --no-cache-dir dnstwist \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

# Ya no usamos nuclei ni testssl.sh, hemos implementado análisis manuales

COPY . .
RUN pip install -e .
COPY ../../templates/ /app/templates/
CMD ["pentest-worker"]
