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
from rq import Queue, Worker
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
q = Queue("scans", connection=redis.from_url(REDIS_URL))

# ────────────────────── utilidades ────────────────────── 
SAFE_DOMAIN = re.compile(r"^[a-z0-9.-]{3,253}$", re.I)

def create_tmp_dir(domain):
    return tempfile.mkdtemp(prefix=f"scan_{domain}_")

# Ejecutar comandos shell y capturar salida
def sh(cmd):
    print(f"Ejecutando: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error ({result.returncode}): {result.stderr}")
    return result.stdout

# 1. Reconocimiento de subdominios
def recon(domain, tmp_dir):
    print(f"[1/7] Iniciando reconocimiento para {domain}...")
    subs_path = f"{tmp_dir}/subdomains.txt"
    
    try:
        # Intentar usar amass si está instalado
        subs = sh(f"amass enum -passive -d {domain} -o -")
    except:
        print("Amass no disponible, usando método alternativo")
        subs = ""
    
    try:
        # Intentar usar subfinder si está instalado
        subs += sh(f"subfinder -d {domain} -silent")
    except:
        print("Subfinder no disponible, usando método alternativo")
        # Fallback básico si las herramientas no están disponibles
        subs += f"www.{domain}\n{domain}\nmail.{domain}\nblog.{domain}"
    
    with open(subs_path, "w") as f:
        f.write(subs)
    
    print(f"Subdominios encontrados: {subs.count('\n')}")
    return subs_path

# 2. Fingerprinting de hosts activos
def fingerprint(subs_path, tmp_dir):
    print(f"[2/7] Realizando fingerprinting de hosts...")
    httpx_path = f"{tmp_dir}/httpx.json"
    
    try:
        # Intentar usar httpx si está instalado
        sh(f"httpx -l {subs_path} -json -tech-detect -status-code -o {httpx_path}")
    except:
        print("httpx no disponible, usando método alternativo")
        # Crear un JSON básico si httpx no está disponible
        with open(subs_path, "r") as f:
            domains = f.read().splitlines()
        
        results = []
        for domain in domains:
            if domain.strip():
                results.append({
                    "url": f"https://{domain.strip()}",
                    "status_code": 0,
                    "technologies": ["No detectado"],
                    "title": "No disponible"
                })
        
        with open(httpx_path, "w") as f:
            json.dump(results, f)
    
    return httpx_path

# 3. Análisis de vulnerabilidades manual (reemplaza Nuclei)
def nuclei_scan(live_json, tmp_dir):
    print(f"[3/7] Ejecutando análisis de vulnerabilidades manual...")
    nuclei_path = f"{tmp_dir}/nuclei.json"

    # Validar que el archivo de entrada de httpx no esté vacío
    if not os.path.exists(live_json) or os.path.getsize(live_json) == 0:
        print(f"Advertencia: El archivo de entrada '{live_json}' está vacío o no existe.")
        with open(nuclei_path, "w") as f:
            json.dump([], f)
        return nuclei_path

    # Lista para almacenar las vulnerabilidades encontradas
    vulnerabilities = []
    
    try:
        # Leer los hosts desde el archivo JSON de httpx
        hosts = []
        with open(live_json, 'r') as f:
            for line in f:
                try:
                    host_data = json.loads(line.strip())
                    if 'url' in host_data:
                        hosts.append(host_data['url'])
                except json.JSONDecodeError:
                    continue
        
        print(f"Analizando {len(hosts)} hosts...")
        
        # Análisis básico de seguridad para cada host
        for host in hosts:
            # 1. Verificar si el host usa HTTP en lugar de HTTPS
            if host.startswith('http://') and not host.startswith('http://localhost'):
                vulnerabilities.append({
                    "host": host,
                    "template": "http-insecure-protocol",
                    "severity": "high",
                    "description": "El sitio utiliza HTTP sin cifrado, lo que expone la información transmitida.",
                    "info": {"severity": "high"}
                })
            
            # 2. Verificar cabeceras de seguridad básicas
            try:
                response = requests.get(host, timeout=5, verify=False, allow_redirects=True)
                headers = response.headers
                
                # Verificar X-Frame-Options (protección contra clickjacking)
                if 'X-Frame-Options' not in headers:
                    vulnerabilities.append({
                        "host": host,
                        "template": "missing-x-frame-options",
                        "severity": "high",
                        "description": "Falta la cabecera X-Frame-Options, lo que podría permitir ataques de clickjacking.",
                        "info": {"severity": "high"}
                    })
                
                # Verificar Content-Security-Policy
                if 'Content-Security-Policy' not in headers:
                    vulnerabilities.append({
                        "host": host,
                        "template": "missing-csp",
                        "severity": "high",
                        "description": "Falta la cabecera Content-Security-Policy, lo que podría permitir ataques XSS.",
                        "info": {"severity": "high"}
                    })
                
                # Verificar X-Content-Type-Options
                if 'X-Content-Type-Options' not in headers:
                    vulnerabilities.append({
                        "host": host,
                        "template": "missing-x-content-type-options",
                        "severity": "high",
                        "description": "Falta la cabecera X-Content-Type-Options, lo que podría permitir ataques de MIME sniffing.",
                        "info": {"severity": "high"}
                    })
            except Exception as e:
                print(f"Error al analizar {host}: {e}")
        
        # Guardar los resultados en formato JSON
        with open(nuclei_path, "w") as f:
            for vuln in vulnerabilities:
                f.write(json.dumps(vuln) + "\n")
        
        print(f"Análisis completado. Se encontraron {len(vulnerabilities)} vulnerabilidades potenciales.")
    
    except Exception as e:
        print(f"Ocurrió un error inesperado durante el análisis manual: {e}")
        # Crear un JSON vacío si el análisis falla para no romper el flujo
        with open(nuclei_path, "w") as f:
            json.dump([], f)
    
    return nuclei_path

# 4. Análisis manual de configuración TLS
def tls_scan(domain, tmp_dir):
    print(f"[4/7] Analizando configuración TLS manualmente...")
    tls_path = f"{tmp_dir}/tls.json"
    
    try:
        import ssl
        import socket
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from datetime import datetime
        
        # Resultados del análisis
        results = {
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "tls_issues": [],
            "certificate": {},
            "protocols": []
        }
        
        # Verificar los protocolos TLS soportados
        protocols_to_test = [
            ssl.PROTOCOL_TLSv1,
            ssl.PROTOCOL_TLSv1_1,
            ssl.PROTOCOL_TLSv1_2,
            ssl.PROTOCOL_TLSv1_3
        ]
        
        protocol_names = {
            ssl.PROTOCOL_TLSv1: "TLSv1.0",
            ssl.PROTOCOL_TLSv1_1: "TLSv1.1",
            ssl.PROTOCOL_TLSv1_2: "TLSv1.2",
            ssl.PROTOCOL_TLSv1_3: "TLSv1.3"
        }
        
        for protocol in protocols_to_test:
            try:
                context = ssl.SSLContext(protocol)
                with socket.create_connection((domain, 443), timeout=5) as sock:
                    with context.wrap_socket(sock, server_hostname=domain) as ssock:
                        results["protocols"].append({
                            "name": protocol_names.get(protocol, "Unknown"),
                            "supported": True,
                            "cipher": ssock.cipher()
                        })
                        
                        # Si es TLSv1.0 o TLSv1.1 (obsoletos), añadir como problema
                        if protocol in [ssl.PROTOCOL_TLSv1, ssl.PROTOCOL_TLSv1_1]:
                            results["tls_issues"].append({
                                "severity": "high",
                                "finding": f"Protocolo obsoleto {protocol_names.get(protocol)} soportado",
                                "description": f"El servidor soporta {protocol_names.get(protocol)}, que es considerado inseguro."
                            })
            except Exception as e:
                results["protocols"].append({
                    "name": protocol_names.get(protocol, "Unknown"),
                    "supported": False,
                    "error": str(e)
                })
        
        # Obtener información del certificado
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert_bin = ssock.getpeercert(binary_form=True)
                    cert = x509.load_der_x509_certificate(cert_bin, default_backend())
                    
                    # Extraer información básica del certificado
                    results["certificate"] = {
                        "subject": str(cert.subject),
                        "issuer": str(cert.issuer),
                        "not_valid_before": cert.not_valid_before.isoformat(),
                        "not_valid_after": cert.not_valid_after.isoformat(),
                        "serial_number": cert.serial_number
                    }
                    
                    # Verificar fecha de expiración
                    if cert.not_valid_after < datetime.now():
                        results["tls_issues"].append({
                            "severity": "critical",
                            "finding": "Certificado expirado",
                            "description": f"El certificado expiró el {cert.not_valid_after.strftime('%Y-%m-%d')}"
                        })
                    elif (cert.not_valid_after - datetime.now()).days < 30:
                        results["tls_issues"].append({
                            "severity": "high",
                            "finding": "Certificado próximo a expirar",
                            "description": f"El certificado expirará el {cert.not_valid_after.strftime('%Y-%m-%d')}"
                        })
        except Exception as e:
            results["certificate"] = {"error": str(e)}
            results["tls_issues"].append({
                "severity": "high",
                "finding": "Error al analizar certificado",
                "description": str(e)
            })
        
        # Guardar resultados
        with open(tls_path, "w") as f:
            json.dump(results, f, indent=2)
            
        print(f"Análisis TLS completado. Se encontraron {len(results['tls_issues'])} problemas.")
    
    except ImportError as e:
        print(f"Error: Falta alguna librería para el análisis TLS: {e}")
        # Crear un JSON básico si faltan dependencias
        with open(tls_path, "w") as f:
            json.dump({
                "domain": domain, 
                "tls_issues": [{
                    "severity": "info",
                    "finding": "Análisis TLS no disponible",
                    "description": f"No se pudo realizar el análisis TLS: {str(e)}"
                }]
            }, f)
    except Exception as e:
        print(f"Error durante el análisis TLS: {e}")
        # Crear un JSON básico en caso de error
        with open(tls_path, "w") as f:
            json.dump({
                "domain": domain, 
                "tls_issues": [{
                    "severity": "info",
                    "finding": "Error en análisis TLS",
                    "description": f"Ocurrió un error durante el análisis: {str(e)}"
                }]
            }, f)
    
    return tls_path

# 5. Búsqueda de credenciales filtradas (implementación manual)
def check_leaks(domain, tmp_dir):
    print("[5/7] Buscando credenciales filtradas...")
    leaks_path = f"{tmp_dir}/leaks.json"
    
    # Lista de correos comunes para verificar
    emails_to_check = [
        f"info@{domain}", f"contact@{domain}", f"admin@{domain}",
        f"support@{domain}", f"test@{domain}", f"dev@{domain}",
        f"contacto@{domain}", f"ventas@{domain}", f"soporte@{domain}",
        f"ayuda@{domain}"
    ]
    
    print(f"Verificando {len(emails_to_check)} correos comunes en HIBP...")
    
    results = {}
    
    try:
        import requests
        import hashlib
        import time
        
        # Implementación manual de verificación de filtraciones
        # usando la API de Have I Been Pwned sin depender de pyhibp
        
        for email in emails_to_check:
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
    
    except ImportError as e:
        print(f"Módulo requests no disponible: {e}")
        for email in emails_to_check:
            results[email] = {
                "filtrado": "no verificado",
                "error": "Dependencias no disponibles",
                "severidad": "info"
            }
    
    except Exception as e:
        print(f"Error al verificar filtraciones: {str(e)}")
        for email in emails_to_check:
            results[email] = {
                "filtrado": "error",
                "error": str(e),
                "severidad": "info"
            }
    
    # Guardar resultados
    with open(leaks_path, "w") as f:
        json.dump(results, f, indent=2)
    
    return leaks_path

# 6. Detección de typosquatting
def check_typosquats(domain, tmp_dir):
    print(f"[6/7] Analizando posibles dominios de phishing...")
    typo_path = f"{tmp_dir}/dnstwist.csv"
    
    try:
        # Intentar usar dnstwist si está instalado
        sh(f"dnstwist -f csv -o {typo_path} {domain}")
    except:
        print("dnstwist no disponible, usando método alternativo")
        # Crear un CSV básico si dnstwist no está disponible
        with open(typo_path, "w") as f:
            f.write(f"fuzzer,domain-name,dns-a,dns-aaaa,dns-mx,dns-ns,geoip-country,ssdeep-score\n")
            f.write(f"original,{domain},,,,,,\n")
            f.write(f"addition,{domain}s,,,,,,\n")
            f.write(f"bitsquatting,{domain.replace('a', 'e') if 'a' in domain else domain.replace('e', 'a')},,,,,,\n")
    
    return typo_path

# 7. Generación del informe PDF con WeasyPrint y Jinja2
def build_pdf(domain, tmp_dir, results):
    print("[7/7] Generando informe PDF...")
    pdf_path = f"{tmp_dir}/{domain}_security_report.pdf"

    # ───────────────── Recopilación y procesado de datos ──────────────────
    
    # 1. Subdominios y datos de httpx
    subdomains_data = []
    try:
        with open(results['httpx'], 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # Asegurar que cada elemento tenga los campos necesarios
                    if isinstance(data, dict):
                        # Asegurar que tenga los campos mínimos necesarios
                        if 'url' not in data:
                            data['url'] = "URL no disponible"
                        if 'status_code' not in data:
                            data['status_code'] = 0
                        if 'title' not in data:
                            data['title'] = "Sin título"
                        if 'technologies' not in data or not isinstance(data['technologies'], list):
                            data['technologies'] = []
                        subdomains_data.append(data)
                except json.JSONDecodeError:
                    continue
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de httpx: {e}")

    # 2. Vulnerabilidades de Nuclei
    nuclei_vulns = []
    try:
        with open(results['nuclei'], 'r') as f:
            for line in f:
                try:
                    vuln = json.loads(line)
                    # Asegurar que cada vulnerabilidad tenga los campos necesarios
                    if isinstance(vuln, dict):
                        # Verificar y establecer campos mínimos
                        if 'host' not in vuln:
                            vuln['host'] = domain
                        if 'template' not in vuln:
                            vuln['template'] = "Vulnerabilidad desconocida"
                        if 'severity' not in vuln:
                            # Intentar obtener severidad de info si existe
                            if isinstance(vuln.get('info'), dict) and 'severity' in vuln['info']:
                                vuln['severity'] = vuln['info']['severity']
                            else:
                                vuln['severity'] = "unknown"
                        if 'description' not in vuln:
                            vuln['description'] = "Sin descripción disponible"
                        
                        # Asegurar que info sea un diccionario
                        if 'info' not in vuln or not isinstance(vuln['info'], dict):
                            vuln['info'] = {'severity': vuln.get('severity', 'unknown')}
                        
                        # Filtrar solo severidades altas y críticas
                        if vuln.get('severity') in ['high', 'critical'] or \
                           vuln.get('info', {}).get('severity') in ['high', 'critical']:
                            nuclei_vulns.append(vuln)
                except json.JSONDecodeError:
                    continue
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de Nuclei: {e}")

    # 3. Datos de TLS
    tls_data = {}
    try:
        with open(results['tls'], 'r') as f:
            tls_data = json.load(f)
            # Asegurar que tls_issues sea una lista
            if 'tls_issues' not in tls_data or not isinstance(tls_data['tls_issues'], list):
                tls_data['tls_issues'] = []
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de TLS: {e}")
        tls_data = {"domain": domain, "tls_issues": []}

    # 4. Credenciales filtradas
    leaked_creds = {}
    try:
        with open(results['leaks'], 'r') as f:
            leaked_creds = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de leaks: {e}")
        leaked_creds = {}

    # 5. Dominios de typosquatting
    typosquatting_domains = []
    try:
        with open(results['typosquats'], 'r') as f:
            # Usar pandas para leer el CSV y convertirlo a dict
            import pandas as pd
            df = pd.read_csv(f)
            # Filtrar solo dominios con registros DNS (potencialmente activos)
            active_typos = df[df['dns-a'].notna() | df['dns-aaaa'].notna() | df['dns-mx'].notna()]
            typosquatting_domains = active_typos.to_dict('records')
    except (FileNotFoundError, Exception) as e:
        print(f"No se pudo procesar el archivo de typosquatting: {e}")

    # ───────────────── Renderizado del HTML ──────────────────
    
    from jinja2 import Environment, FileSystemLoader
    
    # Buscar la plantilla en múltiples ubicaciones posibles
    template_dirs = [
        os.path.join(os.path.dirname(__file__), 'templates'),  # Directorio actual/templates
        '/app/templates',                                      # Directorio en Docker
        os.path.join(os.path.dirname(__file__))                # Directorio actual
    ]
    
    # Intentar cargar la plantilla desde las ubicaciones disponibles
    for template_path in template_dirs:
        if os.path.exists(os.path.join(template_path, 'report.html')):
            env = Environment(loader=FileSystemLoader(template_path))
            template = env.get_template('report.html')
            print(f"Plantilla encontrada en: {template_path}")
            break
    else:
        raise FileNotFoundError(f"No se encontró la plantilla report.html en ninguna ubicación: {template_dirs}")

    # ───────────────── Preparación del contexto para Jinja2 ──────────────────

    # Contar problemas TLS de severidad alta o crítica
    tls_issues_count = sum(1 for issue in tls_data.get('tls_issues', []) 
                         if isinstance(issue, dict) and issue.get('severity') in ['high', 'critical'])
    
    # Contar correos filtrados
    leaked_emails_count = sum(1 for email, data in leaked_creds.items() 
                            if isinstance(data, dict) and data.get('filtrado') is True)

    summary = {
        "subdomains": len(subdomains_data),
        "vulns": len(nuclei_vulns),
        "tls": tls_issues_count,
        "leaks": leaked_emails_count
    }

    context = {
        "now": dt.datetime.now().strftime('%d/%m/%Y a las %H:%M'),
        "domain": domain,
        "summary": summary,
        "subs": subdomains_data,
        "vulns": nuclei_vulns,
        "typos": typosquatting_domains
    }

    # Renderizar el HTML
    html_out = template.render(context)

    # ───────────────── Creación del PDF con WeasyPrint ──────────────────
    from weasyprint import HTML

    try:
        HTML(string=html_out).write_pdf(pdf_path)
        print(f"Informe PDF generado correctamente en: {pdf_path}")
    except Exception as e:
        print(f"Error al generar el PDF con WeasyPrint: {e}")
        # Fallback: guardar el HTML para depuración
        with open(f"{tmp_dir}/debug_report.html", "w") as f:
            f.write(html_out)
        return None # Indicar que la creación del PDF falló
    return pdf_path

# 8. Ya no subimos a S3, simplemente devolvemos la ruta del PDF
def upload_to_s3(pdf_path, domain):
    print(f"Usando PDF local (ya no se sube a S3)...")
    return pdf_path

# 9. Enviar notificación por email con MailerSend (con adjunto)
def send_notification(email, pdf_path, domain):
    key  = os.getenv("MAILERSEND_API_KEY")
    if not key:
        print("MAILERSEND_API_KEY no definido")
        return False

    with open(pdf_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    # Cargar el resumen de resultados para el email
    # NOTA: Esto es una simplificación. En un caso real, pasaríamos los datos
    # desde `run_scan` a `send_notification` para no leer el disco dos veces.
    try:
        with open(f"{os.path.dirname(pdf_path)}/httpx.json", 'r') as f:
            subdomain_count = sum(1 for _ in f)
        with open(f"{os.path.dirname(pdf_path)}/nuclei.json", 'r') as f:
            vuln_count = sum(1 for _ in f)
    except FileNotFoundError:
        subdomain_count = "N/A"
        vuln_count = "N/A"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; color: #333;">
        <h1 style="color: #1a237e;">Pentest Express</h1>
        <p>Hola,</p>
        <p>Adjunto encontrarás tu informe de seguridad para el dominio <strong>{domain}</strong>, generado el {dt.datetime.now().strftime('%d/%m/%Y')}.</p>
        
        <div style="background-color: #f8f9fa; border: 1px solid #e9ecef; padding: 15px; border-radius: 5px;">
            <h3 style="color: #1a237e;">Resumen rápido:</h3>
            <ul>
                <li><strong>Subdominios encontrados:</strong> {subdomain_count}</li>
                <li><strong>Vulnerabilidades (críticas/altas):</strong> {vuln_count}</li>
            </ul>
        </div>

        <p>Para un análisis detallado, consulta el informe PDF adjunto.</p>
        <br>
        <p>Gracias por confiar en Pentest Express.</p>
        <hr>
        <p style="font-size: 10px; color: #888;">Este mensaje es confidencial. Si no eres el destinatario, por favor, notifícalo y elimínalo.</p>
    </div>
    """

    payload = {
        "from": {"email": "informes@auditatetumismo.es", "name": "Pentest Express"},
        "to":   [{"email": email}],
        "subject": f"Informe de seguridad – {domain}",
        "html": html_body,
        "attachments": [{
            "filename": os.path.basename(pdf_path),
            "content":  encoded,
            "disposition": "attachment"
        }]
    }

    r = requests.post(
        "https://api.mailersend.com/v1/email",
        json=payload,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        timeout=20
    )

    ok = r.status_code == 202
    print("MailerSend:", r.status_code, r.text[:120])
    return ok

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
        httpx_path  = fingerprint(subs_path, tmp_dir)
        nuclei_path = nuclei_scan(httpx_path, tmp_dir)
        tls_path    = tls_scan(domain, tmp_dir)
        leaks_path  = check_leaks(domain, tmp_dir)
        typo_path   = check_typosquats(domain, tmp_dir)

        results = {
            "subdomains": subs_path,
            "httpx":      httpx_path,
            "nuclei":     nuclei_path,
            "tls":        tls_path,
            "leaks":      leaks_path,
            "typosquats": typo_path,
        }
        
        # Generar PDF
        pdf_path = build_pdf(domain, tmp_dir, results)
        
        # Ya no subimos a S3, solo guardamos la ruta local
        report_path = upload_to_s3(pdf_path, domain)
        
        # Enviar notificación con el PDF adjunto (MailerSend)
        ok_email = send_notification(email, pdf_path, domain)
        
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
        return {"status":"error","domain":domain,"email":email,"error":str(e)}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)   # limpia /tmp

# Punto de entrada para el worker
if __name__ == "__main__":
    print("Iniciando worker de escaneo...")
    Worker([q]).work()
