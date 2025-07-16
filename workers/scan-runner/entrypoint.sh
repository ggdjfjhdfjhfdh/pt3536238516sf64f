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
    apt-get update && apt-get install -y --no-install-recommends bsdmainutils || apt-get install -y --no-install-recommends busybox || apt-get install -y --no-install-recommends bsdextrautils
    
    # Verificar nuevamente
    if ! command -v hexdump &> /dev/null; then
        echo "ADVERTENCIA: No se pudo instalar hexdump. Intentando crear un enlace simbólico a xxd si está disponible..."
        
        # Intentar usar xxd como alternativa si está disponible
        if command -v xxd &> /dev/null; then
            echo '#!/bin/bash\nxxd "$@"' > /usr/local/bin/hexdump
            chmod +x /usr/local/bin/hexdump
            echo "Se ha creado un wrapper de hexdump usando xxd."
        else
            echo "ADVERTENCIA: No se pudo instalar hexdump ni encontrar alternativas. Algunas funcionalidades como testssl.sh podrían no funcionar correctamente."
        fi
    else
        echo "hexdump instalado correctamente."
    fi
else
    echo "hexdump ya está disponible en el sistema."
fi

# Verificar que testssl.sh esté disponible
if ! command -v testssl.sh &> /dev/null; then
    echo "testssl.sh no encontrado, verificando instalación..."
    
    # Buscar testssl.sh en ubicaciones comunes
    if [ -f "/opt/testssl/testssl.sh" ]; then
        echo "Creando enlace simbólico para testssl.sh desde /opt/testssl/..."
        ln -sf /opt/testssl/testssl.sh /usr/local/bin/testssl.sh
        chmod +x /usr/local/bin/testssl.sh
    elif [ -d "/opt/testssl" ]; then
        echo "Directorio testssl encontrado pero no el script. Intentando clonar el repositorio..."
        rm -rf /opt/testssl
        git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl
        ln -sf /opt/testssl/testssl.sh /usr/local/bin/testssl.sh
        chmod +x /usr/local/bin/testssl.sh
    else
        echo "Clonando testssl.sh desde GitHub..."
        git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl
        ln -sf /opt/testssl/testssl.sh /usr/local/bin/testssl.sh
        chmod +x /usr/local/bin/testssl.sh
    fi
    
    # Verificar nuevamente
    if ! command -v testssl.sh &> /dev/null; then
        echo "ADVERTENCIA: No se pudo instalar testssl.sh correctamente."
    else
        echo "testssl.sh instalado correctamente."
        # Verificar que testssl.sh funcione correctamente
        echo "Verificando que testssl.sh funcione correctamente..."
        testssl.sh --version || echo "ADVERTENCIA: testssl.sh está instalado pero podría no funcionar correctamente."
    fi
else
    echo "testssl.sh ya está disponible en el sistema."
    # Verificar que testssl.sh funcione correctamente
    echo "Verificando que testssl.sh funcione correctamente..."
    testssl.sh --version || echo "ADVERTENCIA: testssl.sh está instalado pero podría no funcionar correctamente."
fi

if [ -f "/app/run_scan.py" ]; then
    echo "run_scan.py encontrado, iniciando aplicación..."
    python /app/run_scan.py
else
    echo "Error: run_scan.py no encontrado!"
    exit 1
fi