#!/bin/bash
set -e

echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -la

echo "Listing files in /app directory:"
ls -la /app

# Verificar que hexdump esté disponible
if ! command -v hexdump &> /dev/null; then
    echo "hexdump no encontrado, intentando instalarlo..."
    apt-get update && apt-get install -y --no-install-recommends bsdmainutils || apt-get install -y --no-install-recommends busybox
    
    # Verificar nuevamente
    if ! command -v hexdump &> /dev/null; then
        echo "ADVERTENCIA: No se pudo instalar hexdump. Algunas funcionalidades como testssl.sh podrían no funcionar correctamente."
    else
        echo "hexdump instalado correctamente."
    fi
else
    echo "hexdump ya está disponible en el sistema."
fi

# Verificar que testssl.sh esté disponible
if ! command -v testssl.sh &> /dev/null; then
    echo "testssl.sh no encontrado, verificando instalación..."
    if [ -f "/opt/testssl/testssl.sh" ]; then
        echo "Creando enlace simbólico para testssl.sh..."
        ln -sf /opt/testssl/testssl.sh /usr/local/bin/testssl.sh
        chmod +x /usr/local/bin/testssl.sh
    else
        echo "ADVERTENCIA: No se encontró testssl.sh en /opt/testssl/"
    fi
else
    echo "testssl.sh ya está disponible en el sistema."
fi

if [ -f "/app/run_scan.py" ]; then
    echo "run_scan.py encontrado, iniciando aplicación..."
    python /app/run_scan.py
else
    echo "Error: run_scan.py no encontrado!"
    exit 1
fi