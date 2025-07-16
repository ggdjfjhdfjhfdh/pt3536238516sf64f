FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN apt-get update && \
    # ───── utilidades básicas ───── 
    apt-get install -y --no-install-recommends \
        curl wget git ca-certificates build-essential \
        util-linux bsdmainutils  # ← incluye «hexdump» \
    \
    # ───── herramientas de seguridad ───── 
    && wget -qO /usr/local/bin/httpx      https://github.com/projectdiscovery/httpx/releases/download/v1.6.3/httpx_1.6.3_linux_amd64  && chmod +x /usr/local/bin/httpx \
    && wget -qO /usr/local/bin/nuclei     https://github.com/projectdiscovery/nuclei/releases/download/v3.3.1/nuclei_3.3.1_linux_amd64  && chmod +x /usr/local/bin/nuclei \
    && wget -qO /usr/local/bin/subfinder  https://github.com/projectdiscovery/subfinder/releases/download/v2.6.6/subfinder_2.6.6_linux_amd64  && chmod +x /usr/local/bin/subfinder \
    && git clone --depth 1 https://github.com/drwetter/testssl.sh.git  /opt/testssl \
    && ln -s /opt/testssl/testssl.sh /usr/local/bin/testssl.sh \
    && apt-get install -y amass \
    && pip install --no-cache-dir dnstwist \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*
COPY run_scan.py .
CMD ["python", "run_scan.py"]
