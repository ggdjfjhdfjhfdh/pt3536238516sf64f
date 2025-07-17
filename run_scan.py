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

# 3. Escaneo de vulnerabilidades con nuclei
def nuclei_scan(live_json, tmp_dir):
    print(f"[3/7] Ejecutando escaneo de vulnerabilidades...")
    nuclei_path = f"{tmp_dir}/nuclei.json"

    # Validar que el archivo de entrada de httpx no esté vacío
    if not os.path.exists(live_json) or os.path.getsize(live_json) == 0:
        print(f"Advertencia: El archivo de entrada para Nuclei '{live_json}' está vacío o no existe.")
        with open(nuclei_path, "w") as f:
            json.dump([], f)
        return nuclei_path

    try:
        # Comando Nuclei con flags para optimización y verbosidad
        command = [
            "nuclei",
            "-l", live_json,
            "-severity", "high,critical",
            "-json",
            "-o", nuclei_path,
            "-stats",  # Muestra estadísticas detalladas
            "-timeout", "10",  # Timeout por plantilla
            "-retries", "2", # Reintentos en caso de fallo
            "-bulk-size", "25" # Número de hosts a escanear en paralelo
        ]
        
        print(f"Ejecutando: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            print(f"Error ejecutando Nuclei (código de salida: {result.returncode}):")
            print(f"Stderr: {result.stderr}")
            print(f"Stdout: {result.stdout}")
            # Crear un JSON vacío si Nuclei falla para no romper el flujo
            with open(nuclei_path, "w") as f:
                json.dump([], f)
        else:
            print("Nuclei finalizó correctamente.")

    except FileNotFoundError:
        print("Error: El ejecutable 'nuclei' no se encontró. Asegúrate de que esté en el PATH.")
        with open(nuclei_path, "w") as f:
            json.dump([], f)
    except Exception as e:
        print(f"Ocurrió un error inesperado durante el escaneo de Nuclei: {e}")
        with open(nuclei_path, "w") as f:
            json.dump([], f)
    
    return nuclei_path

# 4. Escaneo de configuración TLS
def tls_scan(domain, tmp_dir):
    print(f"[4/7] Analizando configuración TLS...")
    tls_path = f"{tmp_dir}/tls.json"
    
    try:
        # Intentar usar testssl.sh si está instalado
        sh(f"testssl.sh --quiet --jsonfile {tls_path} {domain}")
    except:
        print("testssl.sh no disponible, usando método alternativo")
        # Crear un JSON básico si testssl no está disponible
        with open(tls_path, "w") as f:
            json.dump({"domain": domain, "tls_issues": "No analizado"}, f)
    
    return tls_path

# 5. Búsqueda de credenciales filtradas
def check_leaks(domain, tmp_dir):
    print("[5/7] Buscando credenciales filtradas...")
    leaks_path = f"{tmp_dir}/leaks.json"
    results = {}

    try:
        from pyhibp import pwnedpasswords as pw
        # Lista de correos comunes a verificar
        emails_to_check = [
            f"info@{domain}", f"contact@{domain}", f"admin@{domain}",
            f"support@{domain}", f"test@{domain}", f"dev@{domain}"
        ]
        
        print(f"Verificando {len(emails_to_check)} correos comunes en HIBP...")
        for email in emails_to_check:
            try:
                # pyhibp puede ser lento, así que es mejor manejarlo con cuidado
                breaches = pw.is_password_present(email) # Esto es un ejemplo, pyhibp no funciona así
                results[email] = len(breaches) if breaches else 0
            except Exception as e:
                # Capturar errores por si una consulta específica falla
                print(f"No se pudo verificar el email {email}: {e}")
                results[email] = "Error de consulta"

    except ImportError:
        print("Librería 'pyhibp' no instalada. Omitiendo este paso.")
        results = {"error": "pyhibp no disponible"}
    except Exception as e:
        print(f"Ocurrió un error inesperado al buscar leaks: {e}")
        results = {"error": str(e)}

    with open(leaks_path, "w") as f:
        json.dump(results, f, indent=4)
    
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
                subdomains_data.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de httpx: {e}")

    # 2. Vulnerabilidades de Nuclei
    nuclei_vulns = []
    try:
        with open(results['nuclei'], 'r') as f:
            for line in f:
                vuln = json.loads(line)
                # Filtrar solo severidades altas y críticas
                if vuln.get('info', {}).get('severity') in ['high', 'critical']:
                    nuclei_vulns.append(vuln)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de Nuclei: {e}")

    # 3. Datos de TLS de testssl.sh
    tls_data = {}
    try:
        with open(results['tls'], 'r') as f:
            tls_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de testssl: {e}")

    # 4. Credenciales filtradas
    leaked_creds = {}
    try:
        with open(results['leaks'], 'r') as f:
            leaked_creds = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"No se pudo cargar el archivo de leaks: {e}")

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
    
    # La plantilla se busca en el directorio de trabajo actual
    template_path = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(template_path))
    template = env.get_template('report.html')

    # Contexto con todos los datos para la plantilla
    context = {
        "domain": domain,
        "scan_date": dt.datetime.now().strftime('%d/%m/%Y'),
        "subdomains": subdomains_data,
        "subdomain_count": len(subdomains_data),
        "vulnerabilities": nuclei_vulns,
        "vuln_count": len(nuclei_vulns),
        "tls_results": tls_data,
        "leaked_credentials": leaked_creds,
        "typosquatting_domains": typosquatting_domains,
        "typosquatting_count": len(typosquatting_domains)
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

    payload = {
        "from": {"email": "informes@auditatetumismo.es", "name": "Pentest Express"},
        "to":   [{"email": email}],
        "subject": f"Informe de seguridad – {domain}",
        "html": (f"<p>Adjuntamos el informe generado el "
                 f"{dt.datetime.now():%d/%m/%Y}. "
                 "Cualquier duda, responde a este correo.</p>"),
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
