#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path
from pentest.report import build_pdf

def create_test_files(tmp_dir):
    """Crear archivos de prueba con diferentes estructuras JSON"""
    
    # Nuclei con estructura nueva (findings)
    nuclei_data = {
        "findings": [
            {
                "template-id": "missing-csp-header",
                "info": {
                    "name": "Missing Content-Security-Policy Header",
                    "severity": "medium"
                },
                "matched-at": "https://google.com"
            },
            {
                "template-id": "ssl-tls-version",
                "info": {
                    "name": "TLS Version Check",
                    "severity": "low"
                },
                "matched-at": "https://google.com"
            }
        ]
    }
    
    # Dir brute con estructura de diccionario
    dir_brute_data = {
        "directories": [
            {"path": "/admin", "status": 200, "size": 1024},
            {"path": "/backup", "status": 403, "size": 512}
        ]
    }
    
    # Security config con estructura de diccionario
    security_config_data = {
        "results": [
            {"check": "HTTPS Redirect", "status": "fail", "description": "No HTTPS redirect found"},
            {"check": "HSTS Header", "status": "pass", "description": "HSTS header present"}
        ]
    }
    
    # CVEs con estructura de diccionario
    cves_data = {
        "cves": [
            {"id": "CVE-2023-1234", "severity": "high", "description": "Remote code execution"},
            {"id": "CVE-2023-5678", "severity": "medium", "description": "SQL injection"}
        ]
    }
    
    # CISA KEV con estructura de diccionario
    cisa_kev_data = {
        "vulnerabilities": [
            {"cve": "CVE-2023-9999", "vendor": "Apache", "product": "HTTP Server"}
        ]
    }
    
    # Leaks con estructura de diccionario
    leaks_data = {
        "breaches": [
            {"source": "breach1.com", "email": "test@google.com", "password": "hashed"},
            {"source": "breach2.com", "email": "admin@google.com", "password": "hashed"}
        ]
    }
    
    # Typosquats con estructura de diccionario
    typosquats_data = {
        "typosquats": [
            {"domain": "g00gle.com", "similarity": 0.95},
            {"domain": "googIe.com", "similarity": 0.98}
        ]
    }
    
    # Nmap con estructura de lista (ya funciona)
    nmap_data = [
        {"port": 80, "state": "open", "service": "http"},
        {"port": 443, "state": "open", "service": "https"},
        {"port": 22, "state": "closed", "service": "ssh"}
    ]
    
    # GreyNoise con estructura de diccionario
    greynoise_data = {
        "ip": "8.8.8.8",
        "classification": "benign",
        "noise": False,
        "riot": True
    }
    
    # HTTPx con estructura de lista (ya funciona)
    httpx_data = [
        {"url": "https://google.com", "status_code": 200, "title": "Google"},
        {"url": "https://www.google.com", "status_code": 200, "title": "Google"}
    ]
    
    # Crear archivos
    files = {
        "nuclei.json": nuclei_data,
        "dir_brute.json": dir_brute_data,
        "security_config.json": security_config_data,
        "cves.json": cves_data,
        "cisa_kev.json": cisa_kev_data,
        "leaks.json": leaks_data,
        "typosquats.json": typosquats_data,
        "nmap.json": nmap_data,
        "greynoise.json": greynoise_data,
        "httpx.json": httpx_data
    }
    
    file_paths = {}
    for filename, data in files.items():
        file_path = tmp_dir / filename
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        file_paths[filename.replace('.json', '_file')] = file_path
    
    # Crear archivo de subdominios
    subdomains_file = tmp_dir / "subdomains.txt"
    with open(subdomains_file, 'w') as f:
        f.write("www.google.com\nmaps.google.com\ndrive.google.com\n")
    
    return file_paths

def main():
    print("🧪 Probando la carga de datos del informe...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_dir = Path(temp_dir)
        
        # Crear archivos de prueba
        file_paths = create_test_files(tmp_dir)
        
        print("\n📁 Archivos creados:")
        for name, path in file_paths.items():
            print(f"  - {name}: {path.name}")
        
        try:
            # Generar informe PDF
            print("\n📊 Generando informe PDF...")
            pdf_path = build_pdf(
                domain="google.com",
                tmp_dir=tmp_dir,
                httpx_file=file_paths['httpx_file'],
                nuclei_file=file_paths['nuclei_file'],
                leaks_file=file_paths['leaks_file'],
                typosquats_file=file_paths['typosquats_file'],
                cves_file=file_paths['cves_file'],
                nmap_file=file_paths['nmap_file'],
                security_config_file=file_paths['security_config_file'],
                dir_brute_file=file_paths['dir_brute_file'],
                cisa_kev_file=file_paths['cisa_kev_file'],
                greynoise_file=file_paths['greynoise_file']
            )
            
            print(f"\n✅ Informe generado exitosamente: {pdf_path}")
            print(f"📄 Tamaño del archivo: {pdf_path.stat().st_size} bytes")
            
            # Verificar que el archivo HTML también se generó
            html_path = tmp_dir / f"report_google.com.html"
            if html_path.exists():
                print(f"📄 Archivo HTML generado: {html_path}")
                print(f"📄 Tamaño del HTML: {html_path.stat().st_size} bytes")
                
                # Mostrar un fragmento del HTML para verificar contenido
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                    
                print("\n🔍 Verificando contenido del HTML:")
                checks = [
                    ("Nuclei findings", "Missing Content-Security-Policy" in html_content),
                    ("Dir brute results", "/admin" in html_content),
                    ("Security config", "HTTPS Redirect" in html_content),
                    ("CVEs", "CVE-2023-1234" in html_content),
                    ("CISA KEV", "CVE-2023-9999" in html_content),
                    ("Leaks", "breach1.com" in html_content),
                    ("Typosquats", "g00gle.com" in html_content),
                    ("Nmap ports", "port" in html_content.lower()),
                    ("GreyNoise", "8.8.8.8" in html_content)
                ]
                
                for check_name, result in checks:
                    status = "✅" if result else "❌"
                    print(f"  {status} {check_name}: {'Presente' if result else 'Ausente'}")
            
        except Exception as e:
            print(f"\n❌ Error al generar el informe: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()