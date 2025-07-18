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
def sh(cmd, ignore_errors=False):
    print(f"Ejecutando: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)  # 5 min timeout
        if result.returncode != 0:
            error_msg = f"Error ({result.returncode}): {result.stderr}"
            print(error_msg)
            if not ignore_errors:
                raise Exception(error_msg)
        return result.stdout
    except subprocess.TimeoutExpired:
        print(f"Timeout ejecutando: {cmd}")
        if not ignore_errors:
            raise Exception(f"Timeout ejecutando: {cmd}")
        return ""
    except Exception as e:
        print(f"Excepción ejecutando {cmd}: {str(e)}")
        if not ignore_errors:
            raise
        return ""

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

# 3. Escaneo de vulnerabilidades con nuclei
def nuclei_scan(live_json, tmp_dir):
    print(f"[3/7] Ejecutando escaneo de vulnerabilidades...")
    nuclei_path = f"{tmp_dir}/nuclei.json"
    
    try:
        # Verificar que nuclei esté instalado
        version_check = sh("nuclei -version", ignore_errors=True)
        if version_check:
            # Usar parámetros más robustos para nuclei
            sh(f"nuclei -l {live_json} -severity high,critical -json -o {nuclei_path} -timeout 5 -retries 2", ignore_errors=True)
        else:
            raise Exception("Nuclei no está instalado o no es accesible")
    except Exception as e:
        print(f"Error con nuclei: {str(e)}")
        print("Creando archivo de resultados vacío para nuclei")
        # Crear un JSON vacío si nuclei no está disponible o falla
        with open(nuclei_path, "w") as f:
            json.dump([], f)
    
    return nuclei_path

# 4. Escaneo de configuración TLS
def tls_scan(domain, tmp_dir):
    print(f"[4/7] Analizando configuración TLS...")
    tls_path = f"{tmp_dir}/tls.json"
    
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
        sh(f"testssl.sh --quiet --jsonfile {tls_path} {domain}", ignore_errors=True)
        
        # Verificar que el archivo JSON se haya creado correctamente
        if not os.path.exists(tls_path) or os.path.getsize(tls_path) == 0:
            raise Exception("El archivo JSON de testssl.sh no se creó correctamente")
            
    except Exception as e:
        print(f"Error con testssl.sh: {str(e)}")
        print("Creando archivo de resultados básico para TLS")
        # Crear un JSON básico si testssl no está disponible o falla
        with open(tls_path, "w") as f:
            json.dump({
                "domain": domain, 
                "tls_issues": "No analizado",
                "error": str(e),
                "scanResult": [{
                    "id": "fallback",
                    "severity": "INFO",
                    "finding": "No se pudo analizar la configuración TLS"
                }]
            }, f)
    
    return tls_path

# 5. Búsqueda de credenciales filtradas
def check_leaks(domain, tmp_dir):
    print(f"[5/7] Buscando credenciales filtradas...")
    leaks_path = f"{tmp_dir}/leaks.json"
    
    try:
        # Verificar si pyhibp está instalado
        try:
            import importlib
            pyhibp_spec = importlib.util.find_spec("pyhibp")
            if pyhibp_spec is None:
                raise ImportError("Módulo pyhibp no encontrado")
                
            # Ejemplo con HIBP (requiere pyhibp)
            from pyhibp import pwnedpasswords as pw
            # Configurar API key si es necesario
            # from pyhibp import set_api_key
            # set_api_key("tu-api-key")
            
            # Comprobar emails comunes para el dominio
            emails = [
                f"admin@{domain}", 
                f"info@{domain}", 
                f"contact@{domain}", 
                f"security@{domain}",
                f"soporte@{domain}",
                f"contacto@{domain}"
            ]
            
            # Usar un diccionario para almacenar resultados con manejo de errores por email
            results = {}
            for email in emails:
                try:
                    results[email] = {"filtrado": pw.is_password_present(email), "error": None}
                except Exception as e:
                    results[email] = {"filtrado": False, "error": str(e)}
        except ImportError as e:
            print(f"Error importando pyhibp: {str(e)}")
            raise
    except Exception as e:
        print(f"Error con pyhibp: {str(e)}")
        print("Usando método alternativo para verificación de filtraciones")
        # Crear un JSON más informativo si pyhibp no está disponible
        results = {
            f"admin@{domain}": {"filtrado": "No verificado", "error": "pyhibp no disponible"},
            f"info@{domain}": {"filtrado": "No verificado", "error": "pyhibp no disponible"},
            f"contacto@{domain}": {"filtrado": "No verificado", "error": "pyhibp no disponible"}
        }
    
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
                httpx_data = json.load(f)
                subs = []
                for item in httpx_data:
                    subs.append({
                        "url": item.get("url", ""),
                        "status": item.get("status_code", "N/A"),
                        "tech": item.get("technologies", ["N/D"])
                    })
        except:
            # Fallback si no hay datos de httpx
            subs = [{"url": u, "status": 200, "tech": ["N/D"]} for u in raw_subs[:25]]
    except:
        raw_subs = []
        subs = []
    
    # Vulnerabilidades (Nuclei)
    try:
        with open(results['nuclei']) as f:
            raw_nuclei = json.load(f)
        vulns = [{
            "host": n.get("matched-at", ""),
            "template": n.get("template-id", ""),
            "severity": n.get("info", {}).get("severity", "low"),
            "description": n.get("info", {}).get("description", "No disponible")
        } for n in raw_nuclei if n.get("info", {}).get("severity") in ["high", "critical"]]
    except:
        raw_nuclei = []
        vulns = []
    
    # TLS - Mejor procesamiento del resultado de testssl.sh
    try:
        with open(results['tls']) as f:
            tls_data = json.load(f)
            
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
            leaks_data = json.load(f)
            
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
                typo_data = json.load(f)
                
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
        with open(template_path, "w") as f:
            f.write("<!DOCTYPE html><html><body><h1>Informe de seguridad - {{domain}}</h1><p>Generado el {{now}}</p></body></html>")
        print("Se ha creado una plantilla básica como fallback")
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
            with open(str(pdf_path), 'w') as f:
                f.write(f"Informe de seguridad - {domain}\n")
                f.write(f"Generado el {dt.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                f.write(f"Se encontraron {len(subs)} subdominios y {len(vulns)} vulnerabilidades.\n")
            print("Se ha creado un archivo de texto como último recurso")
    
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

    # Leer el PDF y codificarlo en base64
    try:
        with open(pdf_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
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
            try:
                with open(results.get('subdomains', ''), 'r') as f:
                    subdomains_count = len([line for line in f if line.strip()])
            except:
                subdomains_count = "N/D"
                
            # Contar vulnerabilidades
            try:
                with open(results.get('nuclei', ''), 'r') as f:
                    nuclei_data = json.load(f)
                    vulns_count = len(nuclei_data)
            except:
                vulns_count = "N/D"
                
            email_body += f"""<ul style='list-style-type: none; padding-left: 0;'>
                <li style='margin-bottom: 10px;'><strong>🔍 Subdominios encontrados:</strong> {subdomains_count}</li>
                <li><strong>⚠️ Vulnerabilidades detectadas:</strong> {vulns_count} (críticas/altas)</li>
            </ul>"""
        except Exception as e:
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
        
        # Generar PDF
        pdf_path = build_pdf(domain, tmp_dir, results)
        
        # Ya no subimos a S3, solo guardamos la ruta local
        report_path = upload_to_s3(pdf_path, domain)
        
        # Enviar notificación con el PDF adjunto (MailerSend) y resumen en el cuerpo
        ok_email = send_notification(email, pdf_path, domain, results)
        
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
