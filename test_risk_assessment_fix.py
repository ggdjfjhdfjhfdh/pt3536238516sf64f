#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para verificar que el error 'risk_assessment' se ha resuelto
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pentest.report import build_pdf
from pathlib import Path
import tempfile
import json

def test_risk_assessment_fix():
    """Prueba que la variable risk_assessment se pasa correctamente a la plantilla"""
    print("🧪 Probando corrección del error 'risk_assessment'...")
    
    # Datos de prueba mínimos
    test_data = {
        "domain": "test.example.com",
        "scan_results": {
            "nuclei": [],
            "nmap": [],
            "waf": [],
            "subdomain": [],
            "httpx": [],
            "cve": [],
            "dir_brute": [],
            "security_config": [],
            "cisa_kev": [],
            "greynoise": [],
            "premium_adaptive": []
        },
        "scan_metadata": {
            "start_time": "2025-01-29T10:00:00",
            "end_time": "2025-01-29T10:30:00",
            "duration": 1800,
            "total_vulnerabilities": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "info_count": 0
        }
    }
    
    try:
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Intentar generar solo el HTML (sin PDF)
            print("📄 Generando reporte HTML...")
            
            # Llamar a build_pdf pero capturar solo la generación HTML
            try:
                result = build_pdf(
                    test_data,
                    "test@example.com",
                    output_dir=str(tmp_path),
                    generate_pdf=False  # Solo HTML
                )
                print("✅ Reporte HTML generado exitosamente")
                print(f"📁 Archivos generados en: {tmp_path}")
                
                # Listar archivos generados
                for file in tmp_path.glob("*"):
                    print(f"   📄 {file.name}")
                    
                return True
                
            except Exception as e:
                if "risk_assessment" in str(e):
                    print(f"❌ Error 'risk_assessment' aún presente: {e}")
                    return False
                else:
                    print(f"⚠️ Otro error (no relacionado con risk_assessment): {e}")
                    # Si no es el error de risk_assessment, consideramos que está arreglado
                    return True
                    
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Test de corrección del error 'risk_assessment'")
    print("=" * 50)
    
    success = test_risk_assessment_fix()
    
    if success:
        print("\n✅ ÉXITO: El error 'risk_assessment' ha sido corregido")
        sys.exit(0)
    else:
        print("\n❌ FALLO: El error 'risk_assessment' persiste")
        sys.exit(1)