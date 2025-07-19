import os
import redis
import json
import tempfile
import subprocess
import datetime as dt
import base64
import requests
import re
import shutil
import pandas as pd
import warnings
from pathlib import Path
from rq import Queue, Worker
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
# Mantenemos reportlab por compatibilidad
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

# Suprimir advertencias de SSL no verificado (normales en pentesting)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
q = Queue("scans", connection=redis.from_url(REDIS_URL))

# ────────────────────── utilidades ────────────────────── 
SAFE_DOMAIN = re.compile(r"^[a-z0-9.-]{3,253}$", re.I)

def create_tmp_dir(domain):
    return tempfile.mkdtemp(prefix=f"scan_{domain}_")

# Ejecutar comandos shell y capturar salida con mejor manejo de errores
def sh(cmd, ignore_errors=False, timeout=300):
    print(f"Ejecutando: {cmd}")
    try:
        # Usar un timeout configurable con valor predeterminado de 5 minutos
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            error_msg = f"Error ({result.returncode}): {result.stderr}"
            print(error_msg)
            if not ignore_errors:
                raise Exception(error_msg)
        return result.stdout
    except subprocess.TimeoutExpired:
        print(f"Timeout ejecutando: {cmd} (después de {timeout} segundos)")
        if not ignore_errors:
            raise Exception(f"Timeout ejecutando: {cmd} (después de {timeout} segundos)")
        return ""
    except Exception as e:
        print(f"Excepción ejecutando {cmd}: {str(e)}")
        if not ignore_errors:
            raise
        return ""

# 1. Reconocimiento de subdominios mejorado
def recon(domain, tmp_dir):
    print(f"[1/7] Iniciando reconocimiento avanzado para {domain}...")
    subs_path = f"{tmp_dir}/subdomains.txt"
    all_subs = set()
    
    # Método 1: DNS bruteforce con nombres comunes
    print("Método 1: DNS bruteforce con nombres comunes")
    common_subdomains = [
        "www", "mail", "remote", "blog", "webmail", "server", "ns1", "ns2", 
        "smtp", "secure", "vpn", "m", "shop", "ftp", "mail2", "test", "portal", 
        "dns", "host", "mail1", "mx", "support", "dev", "web", "api", "cdn", 
        "app", "proxy", "admin", "news", "connect", "helpdesk", "intranet", 
        "gateway", "exchange", "cp", "cloud", "auth", "legacy", "mobile", "forum",
        "beta", "stage", "pruebas", "desarrollo", "soporte", "tienda", "clientes"
    ]
    
    for sub in common_subdomains:
        all_subs.add(f"{sub}.{domain}")
    
    # Método 2: Certificados SSL/TLS (crt.sh)
    print("Método 2: Búsqueda en certificados SSL/TLS (crt.sh)")
    try:
        import requests
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            try:
                data = response.json()
                for entry in data:
                    name = entry.get('name_value', '').lower()
                    # Filtrar wildcards y dominios no válidos
                    if name and '*' not in name and name.endswith(domain):
                        all_subs.add(name)
                print(f"Encontrados {len(data)} certificados en crt.sh")
            except Exception as e:
                print(f"Error procesando datos de crt.sh: {str(e)}")
    except Exception as e:
        print(f"Error consultando crt.sh: {str(e)}")
    
    # Método 3: Búsqueda en DNS públicos
    print("Método 3: Búsqueda en DNS públicos")
    dns_servers = [
        "8.8.8.8", "1.1.1.1", "9.9.9.9", "208.67.222.222"
    ]
    
    for sub in list(all_subs)[:20]:  # Limitar a 20 para no sobrecargar
        for dns in dns_servers:
            try:
                cmd = f"nslookup {sub} {dns}"
                result = sh(cmd, ignore_errors=True, timeout=5)
                # Si hay respuesta positiva, añadir a la lista
                if "Non-existent domain" not in result and "can't find" not in result:
                    print(f"✓ Confirmado: {sub} (DNS: {dns})")
                    break
            except Exception as e:
                pass
    
    # Método 4: Herramientas externas si están disponibles
    try:
        # Intentar usar amass si está instalado
        amass_result = sh(f"amass enum -passive -d {domain} -o -", ignore_errors=True)
        if amass_result:
            print("Amass ejecutado correctamente")
            for line in amass_result.splitlines():
                if line.strip():
                    all_subs.add(line.strip())
    except Exception as e:
        print(f"Amass no disponible: {str(e)}")
    
    try:
        # Intentar usar subfinder si está instalado
        subfinder_result = sh(f"subfinder -d {domain} -silent", ignore_errors=True)
        if subfinder_result:
            print("Subfinder ejecutado correctamente")
            for line in subfinder_result.splitlines():
                if line.strip():
                    all_subs.add(line.strip())
    except Exception as e:
        print(f"Subfinder no disponible: {str(e)}")
    
    # Método 5: Búsqueda en archivos históricos (web.archive.org)
    print("Método 5: Búsqueda en archivos históricos")
    try:
        url = f"http://web.archive.org/cdx/search/cdx?url=*.{domain}&output=json&fl=original&collapse=urlkey"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            try:
                data = response.json()
                if len(data) > 1:  # La primera fila es el encabezado
                    for entry in data[1:]:  # Saltar el encabezado
                        try:
                            # Extraer el subdominio de la URL
                            from urllib.parse import urlparse
                            url = entry[0]
                            hostname = urlparse(url).netloc.lower()
                            if hostname.endswith(domain):
                                all_subs.add(hostname)
                        except Exception:
                            pass
                    print(f"Encontrados {len(data)-1} URLs en web.archive.org")
            except Exception as e:
                print(f"Error procesando datos de web.archive.org: {str(e)}")
    except Exception as e:
        print(f"Error consultando web.archive.org: {str(e)}")
    
    # Asegurar que el dominio principal esté incluido
    all_subs.add(domain)
    
    # Guardar todos los subdominios encontrados
    subs_list = sorted(list(all_subs))
    with open(subs_path, "w") as f:
        f.write("\n".join(subs_list))
    
    print(f"Subdominios encontrados: {len(subs_list)}")
    return subs_path

# 2. Fingerprinting avanzado de hosts activos
def fingerprint(subs_path, tmp_dir):
    print(f"[2/7] Realizando fingerprinting avanzado de hosts...")
    httpx_path = f"{tmp_dir}/httpx.json"
    
    try:
        # Intentar usar httpx si está instalado
        sh(f"httpx -l {subs_path} -json -tech-detect -status-code -title -content-length -web-server -o {httpx_path}")
    except Exception as e:
        print(f"httpx no disponible ({str(e)}), usando método alternativo")
        # Implementar un fingerprinting básico con requests
        with open(subs_path, "r") as f:
            domains = f.read().splitlines()
        
        import requests
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import socket
        import ssl
        from urllib.parse import urlparse
        import re
        
        # Función para detectar tecnologías basadas en headers y contenido
        def detect_tech(headers, content):
            technologies = []
            
            # Detección basada en headers
            server = headers.get('Server', '')
            if server:
                technologies.append(server)
            
            # Frameworks comunes
            if 'X-Powered-By' in headers:
                technologies.append(headers['X-Powered-By'])
            
            if 'WordPress' in content or '/wp-content/' in content or '/wp-includes/' in content:
                technologies.append('WordPress')
            
            if 'Joomla' in content or '/media/jui/' in content:
                technologies.append('Joomla')
            
            if 'Drupal' in content or 'drupal.settings' in content:
                technologies.append('Drupal')
            
            if 'Laravel' in content or 'laravel_session' in headers.get('Set-Cookie', ''):
                technologies.append('Laravel')
            
            if 'Django' in content or 'csrfmiddlewaretoken' in content:
                technologies.append('Django')
            
            # JavaScript frameworks
            if 'react' in content or 'React.createElement' in content:
                technologies.append('React')
            
            if 'angular' in content or 'ng-app' in content:
                technologies.append('Angular')
            
            if 'vue' in content or 'Vue.js' in content:
                technologies.append('Vue.js')
            
            # CDNs y servicios
            if 'cloudflare' in headers.get('Server', '').lower() or 'cloudflare' in headers.get('CF-RAY', ''):
                technologies.append('Cloudflare')
            
            if 'akamai' in headers.get('Server', '').lower():
                technologies.append('Akamai')
            
            if 'fastly' in headers.get('Server', '').lower():
                technologies.append('Fastly')
            
            # Extraer título
            title_match = re.search('<title>(.*?)</title>', content, re.IGNORECASE)
            title = title_match.group(1) if title_match else 'No title'
            
            return technologies, title
        
        # Función para escanear un solo dominio
        def scan_domain(domain):
            if not domain.strip():
                return None
            
            result = {
                "url": "",
                "status_code": 0,
                "technologies": ["No detectado"],
                "title": "No disponible",
                "content_length": 0,
                "web_server": "Desconocido",
                "ip": "Desconocido",
                "ports": []
            }
            
            # Verificar HTTP y HTTPS
            for protocol in ['https', 'http']:
                try:
                    url = f"{protocol}://{domain}"
                    response = requests.get(url, timeout=10, verify=False, allow_redirects=True)
                    
                    # Obtener información básica
                    result["url"] = response.url
                    result["status_code"] = response.status_code
                    result["content_length"] = len(response.content)
                    result["web_server"] = response.headers.get('Server', 'Desconocido')
                    
                    # Detectar tecnologías
                    techs, title = detect_tech(response.headers, response.text)
                    if techs:
                        result["technologies"] = techs
                    result["title"] = title
                    
                    # Obtener IP
                    try:
                        parsed_url = urlparse(url)
                        hostname = parsed_url.netloc
                        result["ip"] = socket.gethostbyname(hostname)
                    except Exception:
                        pass
                    
                    # Verificar puertos comunes
                    common_ports = [80, 443, 8080, 8443]
                    open_ports = []
                    for port in common_ports:
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(1)
                            s.connect((result["ip"], port))
                            open_ports.append(port)
                            s.close()
                        except Exception:
                            pass
                    
                    result["ports"] = open_ports
                    
                    # Si tuvimos éxito, no necesitamos probar el otro protocolo
                    break
                    
                except requests.exceptions.RequestException:
                    continue
                except Exception as e:
                    print(f"Error escaneando {domain}: {str(e)}")
            
            return result if result["url"] else None
        
        # Escanear dominios en paralelo
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_domain = {executor.submit(scan_domain, domain): domain for domain in domains}
            for future in as_completed(future_to_domain):
                result = future.result()
                if result:
                    results.append(result)
        
        # Guardar resultados
        with open(httpx_path, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"Fingerprinting completado: {len(results)} hosts activos encontrados")
        
        for domain in domains:
                results.append({
                    "url": f"https://{domain.strip()}",
                    "status_code": 0,
                    "technologies": ["No detectado"],
                    "title": "No disponible"
                })
        
        with open(httpx_path, "w") as f:
            json.dump(results, f)
    
    return httpx_path

# 3. Escaneo avanzado de vulnerabilidades con nuclei y alternativas
def nuclei_scan(live_json, tmp_dir):
    print(f"[3/7] Ejecutando escaneo avanzado de vulnerabilidades...")
    nuclei_path = f"{tmp_dir}/nuclei.json"
    
    # Validar que el archivo de entrada no esté vacío
    if not os.path.exists(live_json) or os.path.getsize(live_json) == 0:
        print(f"Advertencia: El archivo de entrada '{live_json}' está vacío o no existe.")
        with open(nuclei_path, "w") as f:
            json.dump([], f)
        return nuclei_path
    
    # Extraer URLs del archivo JSON de httpx
    urls = []
    try:
        with open(live_json, "r") as f:
            data = json.load(f)
            for item in data:
                if isinstance(item, dict) and "url" in item:
                    urls.append(item["url"])
    except Exception as e:
        print(f"Error extrayendo URLs de {live_json}: {str(e)}")
        # Crear un archivo temporal con las URLs
    
    if not urls:
        print("No se encontraron URLs para escanear")
        with open(nuclei_path, "w") as f:
            json.dump([], f)
        return nuclei_path
    
    # Guardar URLs en un archivo temporal para nuclei
    urls_file = f"{tmp_dir}/urls_to_scan.txt"
    with open(urls_file, "w") as f:
        f.write("\n".join(urls))
    
    # Resultados combinados de todos los métodos
    all_results = []
    
    # Método 1: Nuclei (si está disponible)
    try:
        # Verificar que nuclei esté instalado
        version_check = sh("nuclei -version", ignore_errors=True)
        if version_check:
            print("Ejecutando Nuclei con plantillas de seguridad web...")
            # Usar parámetros más robustos para nuclei, incluyendo más severidades
            sh(f"nuclei -l {urls_file} -severity low,medium,high,critical -json -o {nuclei_path} -timeout 10 -retries 2 -rate-limit 150", ignore_errors=True, timeout=900)  # 15 min timeout
            
            # Verificar que el archivo de resultados se haya creado correctamente
            if os.path.exists(nuclei_path) and os.path.getsize(nuclei_path) > 0:
                try:
                    with open(nuclei_path, "r") as f:
                        content = f.read().strip()
                        if content:
                            # Cargar resultados de nuclei
                            try:
                                nuclei_results = json.loads(content)
                                if isinstance(nuclei_results, list):
                                    all_results.extend(nuclei_results)
                                    print(f"Nuclei encontró {len(nuclei_results)} vulnerabilidades")
                                else:
                                    all_results.append(nuclei_results)
                                    print("Nuclei encontró 1 vulnerabilidad")
                            except json.JSONDecodeError:
                                print("El archivo de resultados de nuclei no es un JSON válido")
                except Exception as e:
                    print(f"Error procesando resultados de nuclei: {str(e)}")
            else:
                print("Nuclei no generó resultados")
        else:
            print("Nuclei no está instalado o no es accesible")
    except Exception as e:
        print(f"Error con nuclei: {str(e)}")
    
    # Método 2: Escaneo básico de seguridad con Python
    print("Ejecutando escaneo básico de seguridad con Python...")
    try:
        import requests
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Función para verificar headers de seguridad
        def check_security_headers(url):
            results = []
            try:
                response = requests.get(url, timeout=10, verify=False, allow_redirects=True)
                headers = response.headers
                
                # Verificar Content-Security-Policy
                if 'Content-Security-Policy' not in headers:
                    results.append({
                        "template-id": "missing-csp-header",
                        "info": {
                            "name": "Missing Content-Security-Policy Header",
                            "severity": "high",
                            "description": "El sitio no tiene configurada una política de seguridad de contenido (CSP), lo que puede permitir ataques XSS."
                        },
                        "matched-at": url
                    })
                
                # Verificar X-Frame-Options
                if 'X-Frame-Options' not in headers:
                    results.append({
                        "template-id": "missing-x-frame-options",
                        "info": {
                            "name": "Missing X-Frame-Options Header",
                            "severity": "medium",
                            "description": "El sitio no tiene configurado X-Frame-Options, lo que puede permitir ataques de clickjacking."
                        },
                        "matched-at": url
                    })
                
                # Verificar X-XSS-Protection
                if 'X-XSS-Protection' not in headers:
                    results.append({
                        "template-id": "missing-xss-protection",
                        "info": {
                            "name": "Missing X-XSS-Protection Header",
                            "severity": "medium",
                            "description": "El sitio no tiene configurado X-XSS-Protection, lo que puede aumentar el riesgo de ataques XSS."
                        },
                        "matched-at": url
                    })
                
                # Verificar Strict-Transport-Security (HSTS)
                if 'Strict-Transport-Security' not in headers and url.startswith('https'):
                    results.append({
                        "template-id": "missing-hsts",
                        "info": {
                            "name": "Missing HTTP Strict Transport Security",
                            "severity": "medium",
                            "description": "El sitio no tiene configurado HSTS, lo que puede permitir ataques de downgrade a HTTP."
                        },
                        "matched-at": url
                    })
                
                # Verificar X-Content-Type-Options
                if 'X-Content-Type-Options' not in headers:
                    results.append({
                        "template-id": "missing-content-type-options",
                        "info": {
                            "name": "Missing X-Content-Type-Options Header",
                            "severity": "low",
                            "description": "El sitio no tiene configurado X-Content-Type-Options, lo que puede permitir ataques de MIME sniffing."
                        },
                        "matched-at": url
                    })
                
                # Verificar Referrer-Policy
                if 'Referrer-Policy' not in headers:
                    results.append({
                        "template-id": "missing-referrer-policy",
                        "info": {
                            "name": "Missing Referrer-Policy Header",
                            "severity": "low",
                            "description": "El sitio no tiene configurado Referrer-Policy, lo que puede filtrar información sensible en las referencias."
                        },
                        "matched-at": url
                    })
                
                # Verificar Cookies sin atributos de seguridad
                if 'Set-Cookie' in headers:
                    cookies = headers.get_all('Set-Cookie')
                    for cookie in cookies:
                        if 'HttpOnly' not in cookie:
                            results.append({
                                "template-id": "cookie-without-httponly",
                                "info": {
                                    "name": "Cookie Without HttpOnly Flag",
                                    "severity": "medium",
                                    "description": "Una cookie no tiene el atributo HttpOnly, lo que puede permitir el robo de cookies mediante XSS."
                                },
                                "matched-at": url
                            })
                        if 'Secure' not in cookie and url.startswith('https'):
                            results.append({
                                "template-id": "cookie-without-secure",
                                "info": {
                                    "name": "Cookie Without Secure Flag",
                                    "severity": "medium",
                                    "description": "Una cookie no tiene el atributo Secure, lo que puede permitir la transmisión de cookies por HTTP no cifrado."
                                },
                                "matched-at": url
                            })
                
                # Verificar información sensible en el código fuente
                source_code = response.text.lower()
                if 'api_key' in source_code or 'apikey' in source_code or 'api-key' in source_code:
                    results.append({
                        "template-id": "exposed-api-key",
                        "info": {
                            "name": "Possible API Key Exposure",
                            "severity": "high",
                            "description": "Se ha detectado una posible exposición de clave de API en el código fuente."
                        },
                        "matched-at": url
                    })
                
                if 'password' in source_code and ('var' in source_code or 'const' in source_code or 'let' in source_code):
                    results.append({
                        "template-id": "exposed-password",
                        "info": {
                            "name": "Possible Password Exposure",
                            "severity": "high",
                            "description": "Se ha detectado una posible exposición de contraseña en el código fuente."
                        },
                        "matched-at": url
                    })
                
                return results
            except Exception as e:
                print(f"Error escaneando {url}: {str(e)}")
                return []
        
        # Escanear URLs en paralelo
        python_results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(check_security_headers, url): url for url in urls}
            for future in as_completed(future_to_url):
                result = future.result()
                if result:
                    python_results.extend(result)
        
        print(f"Escaneo básico encontró {len(python_results)} problemas de seguridad")
        all_results.extend(python_results)
        
    except Exception as e:
        print(f"Error en el escaneo básico de seguridad: {str(e)}")
    
    # Guardar todos los resultados combinados
    with open(nuclei_path, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"Total de vulnerabilidades encontradas: {len(all_results)}")
    return nuclei_path

# 4. Escaneo de configuración TLS
def tls_scan(domain, tmp_dir):
    print(f"[4/7] Analizando configuración TLS avanzada...")
    tls_path = f"{tmp_dir}/tls.json"
    
    # Resultados combinados
    results = {
        "domain": domain,
        "scanResult": [],
        "protocols": {},
        "ciphers": [],
        "certificate": {}
    }
    
    # Método 1: testssl.sh (si está disponible)
    try:
        # Verificar que hexdump esté disponible
        hexdump_check = sh("which hexdump || command -v hexdump", ignore_errors=True)
        if not hexdump_check:
            print("ADVERTENCIA: hexdump no está disponible, intentando instalarlo...")
            # Intentar instalar hexdump si no está disponible
            sh("apt-get update && apt-get install -y --no-install-recommends bsdmainutils || apt-get install -y --no-install-recommends busybox", ignore_errors=True)
            
        # Verificar que testssl.sh esté disponible
        testssl_check = sh("which testssl.sh || command -v testssl.sh", ignore_errors=True)
        if not testssl_check:
            print("ADVERTENCIA: testssl.sh no está disponible, verificando instalación...")
            if os.path.exists("/opt/testssl/testssl.sh"):
                print("Creando enlace simbólico para testssl.sh...")
                sh("ln -sf /opt/testssl/testssl.sh /usr/local/bin/testssl.sh && chmod +x /usr/local/bin/testssl.sh", ignore_errors=True)
        
        # Intentar usar testssl.sh con parámetros más robustos
        testssl_tmp_path = f"{tmp_dir}/testssl_raw.json"
        sh(f"testssl.sh --quiet --severity LOW,MEDIUM,HIGH,CRITICAL --jsonfile {testssl_tmp_path} {domain}", ignore_errors=True, timeout=600)
        
        # Verificar que el archivo JSON se haya creado correctamente
        if os.path.exists(testssl_tmp_path) and os.path.getsize(testssl_tmp_path) > 0:
            try:
                with open(testssl_tmp_path, "r") as f:
                    testssl_data = json.load(f)
                    # Extraer resultados relevantes
                    if "scanResult" in testssl_data:
                        results["scanResult"].extend(testssl_data["scanResult"])
                    print(f"Análisis testssl.sh completado con {len(testssl_data.get('scanResult', []))} hallazgos")
            except Exception as e:
                print(f"Error procesando resultados de testssl.sh: {str(e)}")
        else:
            print("testssl.sh no generó resultados válidos")
    except Exception as e:
        print(f"Error con testssl.sh: {str(e)}")
    
    # Método 2: Análisis TLS básico con Python
    print("Ejecutando análisis TLS complementario con Python...")
    try:
        import socket
        import ssl
        from datetime import datetime
        
        # Verificar protocolos TLS soportados
        protocols = {
            ssl.PROTOCOL_TLSv1: "TLSv1.0",
            ssl.PROTOCOL_TLSv1_1: "TLSv1.1",
            ssl.PROTOCOL_TLSv1_2: "TLSv1.2"
        }
        
        for protocol, name in protocols.items():
            try:
                context = ssl.SSLContext(protocol)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                with socket.create_connection((domain, 443), timeout=5) as sock:
                    with context.wrap_socket(sock) as ssock:
                        results["protocols"][name] = True
                        
                        # Verificar protocolos obsoletos
                        if name in ["TLSv1.0", "TLSv1.1"]:
                            results["scanResult"].append({
                                "id": f"obsolete_protocol_{name.lower().replace('.', '_')}",
                                "severity": "MEDIUM",
                                "finding": f"El servidor soporta el protocolo obsoleto {name}"
                            })
            except Exception:
                results["protocols"][name] = False
        
        # Si no hay soporte para TLSv1.2, es un problema crítico
        if not results["protocols"].get("TLSv1.2", False):
            results["scanResult"].append({
                "id": "no_tls_1_2_support",
                "severity": "CRITICAL",
                "finding": "El servidor no soporta TLSv1.2, que es el mínimo recomendado"
            })
        
        # Obtener información del certificado
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Verificar fecha de expiración
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.now()).days
                    
                    results["certificate"] = {
                        "subject": str(cert.get('subject')),
                        "issuer": str(cert.get('issuer')),
                        "version": cert.get('version'),
                        "notBefore": cert.get('notBefore'),
                        "notAfter": cert.get('notAfter'),
                        "serialNumber": cert.get('serialNumber'),
                        "expiresIn": days_until_expiry
                    }
                    
                    if days_until_expiry < 30:
                        results["scanResult"].append({
                            "id": "cert_expiring_soon",
                            "severity": "HIGH" if days_until_expiry < 7 else "MEDIUM",
                            "finding": f"El certificado expira en {days_until_expiry} días"
                        })
                    
                    # Verificar algoritmo de firma
                    if 'sha1' in cert.get('signatureAlgorithm', '').lower():
                        results["scanResult"].append({
                            "id": "weak_signature_algorithm",
                            "severity": "HIGH",
                            "finding": "El certificado utiliza SHA-1 como algoritmo de firma, que es considerado débil"
                        })
        except Exception as e:
            print(f"Error obteniendo información del certificado: {str(e)}")
            results["scanResult"].append({
                "id": "tls_connection_failed",
                "severity": "CRITICAL",
                "finding": f"No se pudo establecer una conexión TLS: {str(e)}"
            })
        
        # Verificar HSTS y otros headers de seguridad
        try:
            import requests
            response = requests.get(f"https://{domain}", timeout=10, verify=False)
            if 'Strict-Transport-Security' not in response.headers:
                results["scanResult"].append({
                    "id": "missing_hsts",
                    "severity": "MEDIUM",
                    "finding": "El servidor no implementa HTTP Strict Transport Security (HSTS)"
                })
        except Exception as e:
            print(f"Error verificando HSTS: {str(e)}")
    except Exception as e:
        print(f"Error en el análisis TLS con Python: {str(e)}")
    
    # Si no hay resultados del escaneo, agregar un mensaje informativo
    if not results["scanResult"]:
        results["scanResult"].append({
            "id": "no_issues_found",
            "severity": "INFO",
            "finding": "No se encontraron problemas de seguridad TLS"
        })
    
    # Guardar resultados combinados
    with open(tls_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Análisis TLS completado con {len(results['scanResult'])} hallazgos")
    return tls_path

# 5. Búsqueda avanzada de credenciales filtradas
def check_leaks(domain, tmp_dir):
    print(f"[5/7] Buscando credenciales filtradas y exposición de datos...")
    leaks_path = f"{tmp_dir}/leaks.json"
    
    # Lista ampliada de correos comunes para verificar
    emails = [
        f"admin@{domain}", 
        f"info@{domain}", 
        f"contact@{domain}", 
        f"security@{domain}",
        f"soporte@{domain}",
        f"contacto@{domain}",
        f"webmaster@{domain}",
        f"ventas@{domain}",
        f"sales@{domain}",
        f"support@{domain}",
        f"marketing@{domain}",
        f"rrhh@{domain}",
        f"hr@{domain}",
        f"it@{domain}",
        f"no-reply@{domain}",
        f"noreply@{domain}",
        f"help@{domain}",
        f"ayuda@{domain}"
    ]
    
    # Estructura para almacenar todos los resultados
    all_results = {
        "domain": domain,
        "emails_checked": len(emails),
        "compromised_count": 0,
        "compromised_emails": [],
        "data_sources": [],
        "pastebin_leaks": [],
        "github_leaks": [],
        "error": None
    }
    
    # Método 1: Verificación con Have I Been Pwned (HIBP)
    print("Método 1: Verificando filtraciones con Have I Been Pwned...")
    try:
        # Verificar si pyhibp está instalado
        try:
            import importlib
            pyhibp_spec = importlib.util.find_spec("pyhibp")
            if pyhibp_spec is None:
                raise ImportError("Módulo pyhibp no encontrado")
                
            # Usar HIBP con pyhibp
            from pyhibp import pwnedpasswords as pw
            from pyhibp import pwnedpasswords as hibp
            # Configurar API key si es necesario
            # from pyhibp import set_api_key
            # set_api_key("tu-api-key")
            
            # Verificar cada email
            for email in emails:
                try:
                    is_pwned = pw.is_password_present(email)
                    if is_pwned:
                        all_results["compromised_count"] += 1
                        all_results["compromised_emails"].append({
                            "email": email,
                            "breaches": "Verificado con HIBP",
                            "appearances": "Desconocido"
                        })
                except Exception as e:
                    print(f"Error verificando {email} con pyhibp: {str(e)}")
        except ImportError as e:
            print(f"Error importando pyhibp: {str(e)}")
            raise
    except Exception as e:
        print(f"Error con pyhibp: {str(e)}")
        print("Usando método alternativo para verificación de filtraciones")
        
        # Método 2: Implementación alternativa usando requests y la API de HIBP directamente
        print("Método 2: Verificando filtraciones con API directa de HIBP...")
        try:
            import requests
            import hashlib
            import time
            
            for email in emails:
                try:
                    # Crear un hash SHA-1 del correo para mayor privacidad
                    email_hash = hashlib.sha1(email.encode('utf-8')).hexdigest().upper()
                    prefix = email_hash[:5]
                    suffix = email_hash[5:]
                    
                    # Consultar la API de HIBP con el prefijo del hash
                    url = f"https://api.pwnedpasswords.com/range/{prefix}"
                    headers = {
                        "User-Agent": "PentestExpress/1.0",
                        "Accept": "application/json"
                    }
                    
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        # Buscar el sufijo en la respuesta
                        is_pwned = False
                        for line in response.text.splitlines():
                            if line.split(":")[0] == suffix:
                                is_pwned = True
                                count = int(line.split(":")[1])
                                results[email] = {
                                    "filtrado": True,
                                    "apariciones": count,
                                    "severidad": "high" if count > 10 else "medium"
                                }
                                print(f"⚠️ El correo {email} aparece en filtraciones de datos ({count} veces)")
                                break
                        
                        if not is_pwned:
                            results[email] = {
                                "filtrado": False,
                                "apariciones": 0,
                                "severidad": "info"
                            }
                            print(f"✅ El correo {email} no aparece en filtraciones")
                    else:
                        results[email] = {
                            "filtrado": "desconocido",
                            "error": f"Error en API: {response.status_code}",
                            "severidad": "info"
                        }
                        print(f"No se pudo verificar el email {email}: Error en API ({response.status_code})")
                    
                    # Esperar un poco entre consultas para no sobrecargar la API
                    time.sleep(1.5)
                    
                except Exception as e:
                    print(f"No se pudo verificar el email {email}: {str(e)}")
                    results[email] = {
                        "filtrado": "desconocido",
                        "error": str(e),
                        "severidad": "info"
                    }
        except Exception as e:
            print(f"Error con el método alternativo: {str(e)}")
            # Crear un JSON más informativo si ambos métodos fallan
            for email in emails:
                results[email] = {"filtrado": "No verificado", "error": "Métodos de verificación no disponibles"}
    
    # Guardar resultados en formato JSON
    with open(leaks_path, "w") as f:
        json.dump({"domain": domain, "resultados": results}, f, indent=2)
    
    return leaks_path

# 6. Detección de typosquatting
def check_typosquats(domain, tmp_dir):
    print(f"[6/7] Analizando posibles dominios de phishing...")
    typo_path = f"{tmp_dir}/dnstwist.csv"
    typo_json_path = f"{tmp_dir}/dnstwist.json"
    
    try:
        # Verificar que dnstwist esté instalado
        version_check = sh("dnstwist --help", ignore_errors=True)
        if not version_check:
            raise Exception("dnstwist no está instalado o no es accesible")
            
        # Ejecutar dnstwist con formato CSV y JSON para mayor flexibilidad
        sh(f"dnstwist -f csv -o {typo_path} {domain}", ignore_errors=True)
        
        # También generar formato JSON para facilitar el procesamiento
        json_result = sh(f"dnstwist -f json {domain}", ignore_errors=True)
        if json_result:
            with open(typo_json_path, "w") as f:
                f.write(json_result)
        
        # Verificar que el archivo CSV se haya creado correctamente
        if not os.path.exists(typo_path) or os.path.getsize(typo_path) == 0:
            raise Exception("El archivo CSV de dnstwist no se creó correctamente")
            
    except Exception as e:
        print(f"Error con dnstwist: {str(e)}")
        print("Creando archivos de resultados básicos para typosquatting")
        
        # Crear un CSV básico si dnstwist no está disponible o falla
        with open(typo_path, "w") as f:
            f.write(f"fuzzer,domain-name,dns-a,dns-aaaa,dns-mx,dns-ns,geoip-country,ssdeep-score\n")
            f.write(f"original,{domain},,,,,,\n")
            f.write(f"addition,{domain}s,,,,,,\n")
            f.write(f"bitsquatting,{domain.replace('a', 'e') if 'a' in domain else domain.replace('e', 'a')},,,,,,\n")
        
        # Crear también un JSON básico
        basic_results = [
            {"fuzzer": "original", "domain": domain, "dns_a": None, "dns_mx": None},
            {"fuzzer": "addition", "domain": f"{domain}s", "dns_a": None, "dns_mx": None},
            {"fuzzer": "bitsquatting", "domain": domain.replace('a', 'e') if 'a' in domain else domain.replace('e', 'a'), "dns_a": None, "dns_mx": None}
        ]
        with open(typo_json_path, "w") as f:
            json.dump(basic_results, f, indent=2)
    
    return typo_path, typo_json_path

# Configuración de Jinja2
TEMPL_PATH = Path(__file__).parent / "templates"
env = Environment(
    loader=FileSystemLoader(TEMPL_PATH),
    autoescape=select_autoescape()
)

# 7. Generación del informe PDF con WeasyPrint y Jinja2
def build_pdf(domain, tmp_dir, results):
    print(f"[7/7] Generando informe PDF profesional con WeasyPrint...")
    pdf_path = f"{tmp_dir}/{domain}_security_report.pdf"
    
    # ---------- 1) cargar datos ----------------- 
    # Subdominios
    try:
        with open(results['subdomains']) as f:
            raw_subs = [l.strip() for l in f if l.strip()]
        # Intentar cargar información de httpx si está disponible
        try:
            with open(results['httpx']) as f:
                content = f.read().strip()
                if not content:  # Verificar que el archivo no esté vacío
                    raise ValueError("Archivo httpx vacío")
                httpx_data = json.loads(content)
                subs = []
                for item in httpx_data:
                    subs.append({
                        "url": item.get("url", ""),
                        "status": item.get("status_code", "N/A"),
                        "tech": item.get("technologies", ["N/D"])
                    })
        except Exception as e:
            print(f"Error procesando httpx: {str(e)}")
            # Fallback si no hay datos de httpx
            subs = [{"url": u, "status": 200, "tech": ["N/D"]} for u in raw_subs[:25]]
    except Exception as e:
        print(f"Error cargando subdominios: {str(e)}")
        raw_subs = []
        subs = []
    
    # Vulnerabilidades (Nuclei)
    try:
        with open(results['nuclei']) as f:
            content = f.read().strip()
            if not content:  # Verificar que el archivo no esté vacío
                raw_nuclei = []
            else:
                raw_nuclei = json.loads(content)
                # Asegurar que sea una lista
                if not isinstance(raw_nuclei, list):
                    print("Advertencia: datos de nuclei no son una lista, convirtiendo")
                    raw_nuclei = [raw_nuclei] if raw_nuclei else []
        vulns = [{
            "host": n.get("matched-at", ""),
            "template": n.get("template-id", ""),
            "severity": n.get("info", {}).get("severity", "low"),
            "description": n.get("info", {}).get("description", "No disponible")
        } for n in raw_nuclei if n.get("info", {}).get("severity") in ["high", "critical"]]
    except Exception as e:
        print(f"Error procesando nuclei: {str(e)}")
        raw_nuclei = []
        vulns = []
    
    # TLS - Mejor procesamiento del resultado de testssl.sh
    try:
        with open(results['tls']) as f:
            content = f.read().strip()
            if not content:  # Verificar que el archivo no esté vacío
                raise ValueError("Archivo TLS vacío")
            tls_data = json.loads(content)
            
        # Verificar si es el formato de fallback o el formato real de testssl.sh
        if "error" in tls_data and "scanResult" in tls_data:
            # Es el formato de fallback
            tls_status = "No analizado: " + tls_data.get("error", "Error desconocido")
        elif "scanResult" in tls_data:
            # Es el formato real de testssl.sh
            # Buscar problemas de severidad alta o crítica
            high_issues = [issue for issue in tls_data.get("scanResult", []) 
                          if issue.get("severity", "").upper() in ["HIGH", "CRITICAL"]]
            
            if high_issues:
                # Mostrar los primeros 2 problemas críticos
                critical_findings = [issue.get("finding", "Problema desconocido") 
                                   for issue in high_issues[:2]]
                tls_status = f"Problemas críticos: {', '.join(critical_findings)}"
                if len(high_issues) > 2:
                    tls_status += f" y {len(high_issues) - 2} más"
            else:
                # Buscar problemas de severidad media
                medium_issues = [issue for issue in tls_data.get("scanResult", []) 
                               if issue.get("severity", "").upper() == "MEDIUM"]
                
                if medium_issues:
                    tls_status = f"{len(medium_issues)} problemas de seguridad moderados"
                else:
                    tls_status = "Configuración TLS segura"
        else:
            # Formato desconocido, usar método antiguo
            tls_content = json.dumps(tls_data)
            tls_status = "Problemas detectados" if "tls_issues" in tls_content else "OK"
    except Exception as e:
        print(f"Error procesando TLS: {str(e)}")
        tls_status = "No analizado"
    
    # Credenciales filtradas - Manejar nuevo formato JSON
    try:
        with open(results['leaks']) as f:
            content = f.read().strip()
            if not content:  # Verificar que el archivo no esté vacío
                raise ValueError("Archivo leaks vacío")
            leaks_data = json.loads(content)
            
        # Comprobar si es el nuevo formato (con estructura domain y resultados)
        if isinstance(leaks_data, dict) and 'resultados' in leaks_data:
            # Nuevo formato
            resultados = leaks_data.get('resultados', {})
            # Contar credenciales filtradas (donde filtrado=True y error=None)
            leaks_count = sum(1 for v in resultados.values() 
                              if isinstance(v, dict) and v.get('filtrado') is True and v.get('error') is None)
            
            # Obtener lista de emails comprometidos
            compromised_emails = [email for email, data in resultados.items() 
                                 if isinstance(data, dict) and data.get('filtrado') is True and data.get('error') is None]
            
            if leaks_count > 0:
                leaks_status = f"{leaks_count} credenciales comprometidas: {', '.join(compromised_emails[:3])}"
                if len(compromised_emails) > 3:
                    leaks_status += f" y {len(compromised_emails) - 3} más"
            else:
                leaks_status = "No se encontraron filtraciones"
        else:
            # Formato antiguo (diccionario simple)
            leaks_count = sum(1 for v in leaks_data.values() if v is True)
            leaks_status = f"{leaks_count} credenciales comprometidas" if leaks_count > 0 else "No se encontraron filtraciones"
    except Exception as e:
        print(f"Error procesando filtraciones: {str(e)}")
        leaks_status = "No analizado"
    
    # Typosquatting - Usar JSON si está disponible, sino usar CSV
    try:
        if results.get("typosquats_json") and os.path.exists(results["typosquats_json"]):
            # Usar el archivo JSON que es más estructurado
            with open(results["typosquats_json"]) as f:
                content = f.read().strip()
                if not content:  # Verificar que el archivo no esté vacío
                    raise ValueError("Archivo typosquats_json vacío")
                typo_data = json.loads(content)
                
            # Filtrar solo dominios activos (con DNS A o MX configurados)
            active_typos = [t for t in typo_data if t.get("dns_a") or t.get("dns_mx")]
            
            # Ordenar por peligrosidad (priorizar dominios con MX configurado)
            active_typos.sort(key=lambda x: 1 if x.get("dns_mx") else 0, reverse=True)
            
            typos = active_typos[:20]
        else:
            # Fallback al CSV
            import csv
            typos = []
            try:
                with open(results["typosquats"], 'r') as f:
                    content = f.read().strip()
                    if not content:  # Verificar que el archivo no esté vacío
                        raise ValueError("Archivo typosquats CSV vacío")
                    # Reiniciar el puntero del archivo para leer desde el principio
                    f.seek(0)
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Verificar si el dominio tiene DNS configurado
                        if row.get('dns-a') or row.get('dns-aaaa') or row.get('dns-mx'):
                            typos.append({
                                'domain': row.get('domain-name', ''),
                                'fuzzer': row.get('fuzzer', ''),
                                'dns_a': row.get('dns-a', ''),
                                'dns_mx': row.get('dns-mx', '')
                            })
                        if len(typos) >= 20:  # limitar a 20 resultados
                            break
            except Exception as csv_error:
                print(f"Error procesando CSV de dnstwist: {csv_error}")
                typos = []
    except Exception as e:
        print(f"Error procesando typosquatting: {str(e)}")
        typos = []
    
    # Resumen
    summary = {
        "subdomains": len(raw_subs),
        "vulns": len(vulns),
        "tls": tls_status,
        "leaks": leaks_status
    }
    
    # ---------- 2) render HTML ------------------ 
    ctx = dict(
        domain=domain,
        now=dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        summary=summary,
        subs=subs,
        vulns=vulns,
        typos=typos,
        page_number="1"  # WeasyPrint puede manejar esto automáticamente con CSS
    )
    
    # Imprimir información de depuración para verificar que los datos están correctos
    print(f"Datos para el informe: {len(subs)} subdominios, {len(vulns)} vulnerabilidades, {len(typos)} dominios typosquatting")
    print(f"Resumen: {summary}")
    
    # Verificar que la plantilla existe
    template_path = TEMPL_PATH / "report.html"
    if not template_path.exists():
        print(f"ERROR: La plantilla no existe en {template_path}")
        # Crear una plantilla básica como fallback
        try:
            os.makedirs(TEMPL_PATH, exist_ok=True)
            with open(template_path, "w") as f:
                f.write("<!DOCTYPE html><html><body><h1>Informe de seguridad - {{domain}}</h1><p>Generado el {{now}}</p></body></html>")
            print("Se ha creado una plantilla básica como fallback")
        except Exception as e:
            print(f"ERROR al crear plantilla fallback: {e}")
            # Continuar con una plantilla en memoria
    else:
        print(f"Plantilla encontrada en {template_path}")
    
    # Verificar que el entorno Jinja2 está configurado correctamente
    try:
        html = env.get_template("report.html").render(**ctx)
        print("Plantilla HTML renderizada correctamente")
    except Exception as e:
        print(f"ERROR al renderizar la plantilla HTML: {e}")
        # Crear HTML básico como fallback
        html = f"""<!DOCTYPE html>
        <html>
        <body>
            <h1>Informe de seguridad - {domain}</h1>
            <p>Generado el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            <p>Se encontraron {len(subs)} subdominios y {len(vulns)} vulnerabilidades.</p>
        </body>
        </html>"""
        print("Se ha creado un HTML básico como fallback")
    
    # ---------- 3) HTML -> PDF ------------------ 
    try:
        HTML(string=html, base_url=str(TEMPL_PATH)).write_pdf(pdf_path)
        print(f"PDF generado correctamente y guardado en {pdf_path}")
    except Exception as e:
        print(f"ERROR al generar el PDF con WeasyPrint: {e}")
        # Crear un PDF básico como fallback usando reportlab
        try:
            from reportlab.pdfgen import canvas
            p = canvas.Canvas(str(pdf_path))
            p.drawString(100, 750, f"Informe de seguridad - {domain}")
            p.drawString(100, 730, f"Generado el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}")
            p.drawString(100, 710, f"Se encontraron {len(subs)} subdominios y {len(vulns)} vulnerabilidades.")
            p.save()
            print("Se ha creado un PDF básico como fallback usando reportlab")
        except Exception as e2:
            print(f"ERROR al generar el PDF fallback con reportlab: {e2}")
            # Último recurso: crear un archivo de texto
            try:
                with open(str(pdf_path), 'w') as f:
                    f.write(f"Informe de seguridad - {domain}\n")
                    f.write(f"Generado el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                    f.write(f"Se encontraron {len(subs)} subdominios y {len(vulns)} vulnerabilidades.\n")
                print("Se ha creado un archivo de texto como último recurso")
            except Exception as e3:
                print(f"ERROR al crear archivo de texto: {e3}")
                # Si todo falla, devolver la ruta aunque no exista el archivo
    
    # Verificar que el archivo existe
    if not os.path.exists(pdf_path):
        print(f"ADVERTENCIA: El archivo PDF no existe en la ruta: {pdf_path}")
    elif os.path.getsize(pdf_path) == 0:
        print(f"ADVERTENCIA: El archivo PDF está vacío: {pdf_path}")
    
    return pdf_path

# 8. Ya no subimos a S3, simplemente devolvemos la ruta del PDF
def upload_to_s3(pdf_path, domain):
    print(f"Usando PDF local (ya no se sube a S3)...")
    return pdf_path

# 9. Enviar notificación por email con MailerSend (con adjunto)
def send_notification(email, pdf_path, domain, results=None):
    key = os.getenv("MAILERSEND_API_KEY")
    if not key:
        print("MAILERSEND_API_KEY no definido")
        return False

    # Verificar que el PDF existe y es accesible
    if not os.path.exists(pdf_path):
        print(f"Error: El archivo PDF no existe en la ruta: {pdf_path}")
        return False
        
    if os.path.getsize(pdf_path) == 0:
        print(f"Error: El archivo PDF está vacío: {pdf_path}")
        return False

    # Leer el PDF y codificarlo en base64
    try:
        with open(pdf_path, "rb") as f:
            pdf_content = f.read()
            if len(pdf_content) == 0:
                print(f"Error: El archivo PDF está vacío aunque existe: {pdf_path}")
                return False
            encoded = base64.b64encode(pdf_content).decode()
    except Exception as e:
        print(f"Error leyendo PDF: {str(e)}")
        encoded = None

    # Generar un resumen del escaneo para incluir en el cuerpo del email
    email_body = f"""<div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px;">
        <div style="text-align: center; border-bottom: 1px solid #eee; padding-bottom: 20px; margin-bottom: 20px;">
            <h1 style="font-size: 24px; color: #1a237e; margin: 0;">Pentest Express</h1>
        </div>
        <h2 style="font-size: 20px; color: #2c3e50;">Informe de Seguridad para {domain}</h2>
        <p>Estimado cliente,</p>
        <p>Adjuntamos el informe de seguridad generado para su dominio <strong>{domain}</strong> el {dt.datetime.now():%d/%m/%Y a las %H:%M}.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #2c3e50; margin-top: 0; border-bottom: 1px solid #ddd; padding-bottom: 10px;">Resumen del Análisis</h3>"""
    
    # Añadir información del escaneo si está disponible
    if results:
        try:
            # Contar subdominios
            subdomains_count = "N/D"
            try:
                if os.path.exists(results.get('subdomains', '')):
                    with open(results.get('subdomains', ''), 'r') as f:
                        subdomains_count = len([line for line in f if line.strip()])
            except Exception as e:
                print(f"Error contando subdominios: {str(e)}")
                
            # Contar vulnerabilidades
            vulns_count = "N/D"
            try:
                if os.path.exists(results.get('nuclei', '')):
                    with open(results.get('nuclei', ''), 'r') as f:
                        content = f.read().strip()
                        if content:
                            try:
                                nuclei_data = json.loads(content)
                                if isinstance(nuclei_data, list):
                                    vulns_count = len(nuclei_data)
                                else:
                                    vulns_count = 0
                            except json.JSONDecodeError:
                                print("Error decodificando JSON de nuclei")
                                vulns_count = 0
            except Exception as e:
                print(f"Error contando vulnerabilidades: {str(e)}")
                
            email_body += f"""<ul style='list-style-type: none; padding-left: 0;'>
                <li style='margin-bottom: 10px;'><strong>🔍 Subdominios encontrados:</strong> {subdomains_count}</li>
                <li><strong>⚠️ Vulnerabilidades detectadas:</strong> {vulns_count} (críticas/altas)</li>
            </ul>"""
        except Exception as e:
            print(f"Error generando resumen del escaneo: {str(e)}")
            email_body += f"<p>No se pudo generar el resumen del escaneo: {str(e)}</p>"
    
    email_body += """</div>
        <p>Para un análisis detallado de los hallazgos, consulte el <strong>informe PDF adjunto</strong>.</p>
        <p>Si tiene alguna pregunta o necesita una evaluación más profunda, no dude en contactarnos.</p>
        <div style="text-align: center; color: #888; font-size: 12px; border-top: 1px solid #eee; padding-top: 20px; margin-top: 20px;">
            <p>Pentest Express &copy; {dt.datetime.now().year} | Informe confidencial</p>
        </div>
    </div>"""

    # Preparar payload para MailerSend
    payload = {
        "from": {"email": "informes@pentestexpress.com", "name": "Auditatetumismo"},
        "to":   [{"email": email}],
        "subject": f"Informe de seguridad – {domain}",
        "html": email_body,
    }
     
    # Añadir el PDF como adjunto si está disponible
    if encoded:
        payload["attachments"] = [{
            "filename": os.path.basename(pdf_path),
            "content":  encoded,
            "disposition": "attachment"
        }]
    else:
        print("ADVERTENCIA: No se pudo adjuntar el PDF al email")

    # Intentar enviar el email con reintentos
    max_retries = 3
    retry_delay = 5  # segundos
    
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(
                "https://api.mailersend.com/v1/email",
                json=payload,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                timeout=30,  # Aumentar timeout para archivos grandes
                verify=True  # Verificar certificados SSL/TLS
            )

            ok = r.status_code == 202
            print(f"MailerSend (intento {attempt}/{max_retries}):", r.status_code, r.text[:120])
            
            if ok:
                return True
            elif attempt < max_retries:
                print(f"Reintentando en {retry_delay} segundos...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponencial
            else:
                print(f"Todos los intentos de envío fallaron. Último código: {r.status_code}")
                return False
                
        except requests.RequestException as e:
            print(f"Error de conexión en intento {attempt}/{max_retries}: {str(e)}")
            if attempt < max_retries:
                print(f"Reintentando en {retry_delay} segundos...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponencial
            else:
                print("Todos los intentos de conexión fallaron")
                return False
    
    return False  # No debería llegar aquí, pero por si acaso

# Función principal que ejecuta todo el proceso
def generate_pdf(domain, email):
    print(f"Iniciando escaneo completo para {domain}...")

    if not SAFE_DOMAIN.match(domain):
        return {"status":"error", "error":"Dominio no válido"}

    tmp_dir = create_tmp_dir(domain)          # dir temporal único
    print("Directorio temporal:", tmp_dir)

    try:
        # 1-6  ────────────── pipeline ────────────── 
        subs_path   = recon(domain, tmp_dir)
        
        # Verificar que se generó el archivo de subdominios
        if not os.path.exists(subs_path) or os.path.getsize(subs_path) == 0:
            print(f"ADVERTENCIA: No se encontraron subdominios para {domain}")
            # Crear un archivo con al menos el dominio principal para continuar
            with open(subs_path, 'w') as f:
                f.write(f"{domain}\n")
        
        httpx_path  = fingerprint(subs_path, tmp_dir)
        nuclei_path = nuclei_scan(httpx_path, tmp_dir)
        tls_path    = tls_scan(domain, tmp_dir)
        leaks_path  = check_leaks(domain, tmp_dir)
        typo_results = check_typosquats(domain, tmp_dir)
        
        # Desempaquetar los resultados de typosquatting (ahora devuelve dos valores)
        if isinstance(typo_results, tuple) and len(typo_results) == 2:
            typo_path, typo_json_path = typo_results
        else:
            # Compatibilidad con versiones anteriores
            typo_path = typo_results
            typo_json_path = None

        results = {
            "subdomains": subs_path,
            "httpx":      httpx_path,
            "nuclei":     nuclei_path,
            "tls":        tls_path,
            "leaks":      leaks_path,
            "typosquats": typo_path,
            "typosquats_json": typo_json_path,
        }
        
        # Verificar que todos los archivos de resultados existen
        missing_files = []
        for key, file_path in results.items():
            if not file_path or not os.path.exists(file_path):
                print(f"ADVERTENCIA: Archivo de resultados no encontrado: {key} -> {file_path}")
                missing_files.append(key)
        
        if missing_files:
            print(f"ADVERTENCIA: Faltan {len(missing_files)} archivos de resultados: {', '.join(missing_files)}")
        
        # Generar PDF
        pdf_path = build_pdf(domain, tmp_dir, results)
        
        # Verificar que el PDF se generó correctamente
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            print(f"ERROR: No se pudo generar el PDF en {pdf_path} o está vacío")
            # Intentar generar un informe de texto básico como último recurso
            txt_path = f"{tmp_dir}/{domain}_informe_basico.txt"
            try:
                with open(txt_path, 'w') as f:
                    f.write(f"Informe de seguridad básico para {domain}\n")
                    f.write(f"Generado el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                    f.write("No se pudo generar el informe PDF completo.\n")
                pdf_path = txt_path
                print(f"Se ha creado un informe básico en texto: {txt_path}")
            except Exception as e2:
                print(f"ERROR al crear informe básico: {str(e2)}")
        
        # Ya no subimos a S3, solo guardamos la ruta local
        report_path = upload_to_s3(pdf_path, domain)
        
        # Enviar notificación con el PDF adjunto (MailerSend) y resumen en el cuerpo
        ok_email = send_notification(email, pdf_path, domain, results)
        
        if not ok_email:
            print(f"ADVERTENCIA: No se pudo enviar el email a {email}")
            # Intentar reenviar con un informe básico si el original falló
            if os.path.exists(pdf_path) and pdf_path.endswith('.pdf'):
                txt_path = f"{tmp_dir}/{domain}_informe_basico.txt"
                try:
                    with open(txt_path, 'w') as f:
                        f.write(f"Informe de seguridad básico para {domain}\n")
                        f.write(f"Generado el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                        f.write("El informe PDF completo no pudo ser enviado por email.\n")
                    print(f"Reintentando envío con informe básico: {txt_path}")
                    ok_email = send_notification(email, txt_path, domain, results)
                except Exception as e2:
                    print(f"ERROR al crear y enviar informe básico: {str(e2)}")
        
        print(f"✅ Escaneo completo para {domain}")
        print(f"📊 Informe generado en: {pdf_path}")
        
        return {
            "status": "success",
            "domain": domain,
            "email": email,
            "report_path": pdf_path,
            "mailersend": ok_email
        }

    except Exception as e:
        print("❌ Error durante el escaneo:", e)
        # Intentar generar un informe de error
        error_path = f"{tmp_dir}/{domain}_error_report.txt"
        try:
            with open(error_path, 'w') as f:
                f.write(f"Informe de error para {domain}\n")
                f.write(f"Generado el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                f.write(f"Error durante el proceso de escaneo: {str(e)}\n")
            
            # Intentar enviar notificación de error
            try:
                send_notification(email, error_path, domain, {'error': str(e)})
            except Exception as e2:
                print(f"No se pudo enviar notificación de error: {str(e2)}")
        except Exception as e2:
            print(f"No se pudo generar informe de error: {str(e2)}")
            
        return {"status":"error","domain":domain,"email":email,"error":str(e)}
    finally:
        # Mantener los archivos por un tiempo para depuración si hay errores
        try:
            if 'status' in locals() and locals().get('status') == 'error':
                print(f"Manteniendo archivos temporales para depuración en: {tmp_dir}")
            else:
                shutil.rmtree(tmp_dir, ignore_errors=True)   # limpia /tmp
        except Exception as e:
            print(f"Error al limpiar directorio temporal: {str(e)}")
            # Intentar limpiar de todos modos
            shutil.rmtree(tmp_dir, ignore_errors=True)

# Punto de entrada para el worker
if __name__ == "__main__":
    print("Iniciando worker de escaneo...")
    Worker([q]).work()
