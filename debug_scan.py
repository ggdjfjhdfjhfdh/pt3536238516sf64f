#!/usr/bin/env python3
"""Script de diagnóstico para debuggear el problema del escaneo."""

import logging
import sys
import tempfile
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Importar módulos del pentest
from pentest.recon import recon
from pentest.fingerprint import fingerprint
from pentest.nuclei_scan import nuclei_scan

def debug_scan_pipeline(domain: str):
    """Debuggea el pipeline de escaneo paso a paso."""
    print(f"🔍 Debuggeando pipeline para dominio: {domain}")
    
    with tempfile.TemporaryDirectory(prefix=f"debug_{domain}_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        print(f"📁 Directorio temporal: {tmp_dir}")
        
        # Paso 1: Reconocimiento
        print("\n=== PASO 1: RECONOCIMIENTO ===")
        try:
            subdomains_file = recon(domain, tmp_dir)
            print(f"✅ Archivo de subdominios: {subdomains_file}")
            
            if subdomains_file.exists():
                content = subdomains_file.read_text().strip()
                print(f"📄 Contenido del archivo de subdominios:")
                print(content)
                print(f"📊 Total de líneas: {len(content.splitlines()) if content else 0}")
            else:
                print("❌ El archivo de subdominios no existe")
                return
                
        except Exception as e:
            print(f"❌ Error en reconocimiento: {e}")
            return
        
        # Paso 2: Fingerprinting
        print("\n=== PASO 2: FINGERPRINTING ===")
        try:
            httpx_file = fingerprint(subdomains_file, tmp_dir)
            print(f"✅ Archivo httpx: {httpx_file}")
            
            if httpx_file.exists():
                content = httpx_file.read_text().strip()
                print(f"📄 Contenido del archivo httpx:")
                print(content)
                
                import json
                try:
                    data = json.loads(content)
                    print(f"📊 Total de hosts activos: {len(data) if isinstance(data, list) else 0}")
                    
                    if isinstance(data, list) and data:
                        print("🌐 URLs encontradas:")
                        for item in data:
                            if 'url' in item:
                                print(f"  - {item['url']}")
                except json.JSONDecodeError as e:
                    print(f"❌ Error al parsear JSON: {e}")
            else:
                print("❌ El archivo httpx no existe")
                return
                
        except Exception as e:
            print(f"❌ Error en fingerprinting: {e}")
            return
        
        # Paso 3: Nuclei scan
        print("\n=== PASO 3: NUCLEI SCAN ===")
        try:
            nuclei_file = nuclei_scan(httpx_file, tmp_dir, full_scan=False)
            print(f"✅ Archivo nuclei: {nuclei_file}")
            
            if nuclei_file.exists():
                content = nuclei_file.read_text().strip()
                print(f"📄 Contenido del archivo nuclei:")
                print(content)
                
                import json
                try:
                    data = json.loads(content)
                    print(f"📊 Total de vulnerabilidades: {len(data) if isinstance(data, list) else 0}")
                except json.JSONDecodeError as e:
                    print(f"❌ Error al parsear JSON de nuclei: {e}")
            else:
                print("❌ El archivo nuclei no existe")
                
        except Exception as e:
            print(f"❌ Error en nuclei scan: {e}")
            return
        
        print("\n✅ Diagnóstico completado")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python debug_scan.py <dominio>")
        sys.exit(1)
    
    domain = sys.argv[1]
    debug_scan_pipeline(domain)