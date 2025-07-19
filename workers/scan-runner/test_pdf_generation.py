#!/usr/bin/env python
"""
Prueba de integración para la generación de PDF en el proceso de escaneo.

Este script prueba el proceso completo de generación de PDF, incluyendo:
1. Creación de un HTML de informe de prueba
2. Conversión del HTML a PDF usando WeasyPrint
3. Verificación del PDF generado
4. Prueba de los mecanismos de fallback si WeasyPrint falla

Uso:
    python test_pdf_generation.py
"""

import os
import sys
import json
import tempfile
import traceback
from pathlib import Path
import shutil

# Importar funciones necesarias del script principal
# Nota: Asegúrate de que run_scan.py esté en el PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from run_scan import generate_html_report, generate_pdf_from_html, generate_pdf_with_reportlab
except ImportError:
    print("Error: No se pudo importar las funciones necesarias de run_scan.py")
    print("Asegúrate de que el archivo esté accesible en el PYTHONPATH")
    sys.exit(1)


def create_test_data():
    """Crea datos de prueba para generar un informe."""
    return {
        "domain": "example.com",
        "scan_date": "2023-01-01",
        "subdomains": [
            {"subdomain": "test1.example.com", "ip": "192.168.1.1"},
            {"subdomain": "test2.example.com", "ip": "192.168.1.2"}
        ],
        "vulnerabilities": [
            {
                "title": "Prueba de Vulnerabilidad 1",
                "severity": "high",
                "description": "Esta es una vulnerabilidad de prueba",
                "recommendation": "Actualizar el software"
            },
            {
                "title": "Prueba de Vulnerabilidad 2",
                "severity": "medium",
                "description": "Esta es otra vulnerabilidad de prueba",
                "recommendation": "Configurar correctamente el firewall"
            }
        ],
        "tls_results": {
            "supported_protocols": ["TLSv1.2", "TLSv1.3"],
            "certificate": {
                "subject": "CN=example.com",
                "issuer": "CN=Test CA",
                "not_valid_before": "2023-01-01T00:00:00",
                "not_valid_after": "2024-01-01T00:00:00",
                "serial_number": "123456789"
            },
            "tls_issues": []
        },
        "credential_leaks": [
            {"email": "test@example.com", "password": "[REDACTED]", "source": "TestBreach"}
        ],
        "typosquatting": [
            {"domain": "examp1e.com", "dns_a": "Yes", "dns_mx": "No"}
        ]
    }


def test_html_generation(temp_dir):
    """Prueba la generación del informe HTML."""
    print("\nPrueba 1: Generación de HTML")
    print("-" * 40)
    
    try:
        # Crear datos de prueba
        data = create_test_data()
        
        # Generar el HTML
        html_path = os.path.join(temp_dir, "report.html")
        generate_html_report(data, html_path)
        
        # Verificar que el archivo existe y tiene contenido
        if os.path.exists(html_path) and os.path.getsize(html_path) > 0:
            print(f"✅ HTML generado correctamente en {html_path} ({os.path.getsize(html_path)} bytes)")
            return html_path
        else:
            print(f"❌ Error: El archivo HTML no existe o está vacío")
            return None
    except Exception as e:
        print(f"❌ Error al generar el HTML: {e}")
        traceback.print_exc()
        return None


def test_weasyprint_pdf_generation(html_path, temp_dir):
    """Prueba la generación de PDF usando WeasyPrint."""
    print("\nPrueba 2: Generación de PDF con WeasyPrint")
    print("-" * 40)
    
    if not html_path:
        print("❌ No se puede continuar sin un archivo HTML válido")
        return None
    
    try:
        # Generar el PDF con WeasyPrint
        pdf_path = os.path.join(temp_dir, "report_weasyprint.pdf")
        generate_pdf_from_html(html_path, pdf_path)
        
        # Verificar que el archivo existe y tiene contenido
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            print(f"✅ PDF generado correctamente con WeasyPrint en {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
            return pdf_path
        else:
            print(f"❌ Error: El archivo PDF no existe o está vacío")
            return None
    except Exception as e:
        print(f"❌ Error al generar el PDF con WeasyPrint: {e}")
        print("Probando mecanismo de fallback...")
        return None


def test_reportlab_fallback(temp_dir, data):
    """Prueba el mecanismo de fallback usando ReportLab."""
    print("\nPrueba 3: Mecanismo de Fallback con ReportLab")
    print("-" * 40)
    
    try:
        # Generar el PDF con ReportLab
        pdf_path = os.path.join(temp_dir, "report_reportlab.pdf")
        generate_pdf_with_reportlab(data, pdf_path)
        
        # Verificar que el archivo existe y tiene contenido
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            print(f"✅ PDF generado correctamente con ReportLab en {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
            return pdf_path
        else:
            print(f"❌ Error: El archivo PDF de fallback no existe o está vacío")
            return None
    except Exception as e:
        print(f"❌ Error al generar el PDF con ReportLab: {e}")
        traceback.print_exc()
        return None


def main():
    """Función principal que ejecuta todas las pruebas."""
    print("=== Prueba de Integración: Generación de PDF ===")
    print(f"Python {sys.version} en {sys.executable}")
    print(f"Sistema operativo: {os.name} - {sys.platform}")
    print("-" * 50)
    
    # Crear un directorio temporal para los archivos de prueba
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Directorio temporal para pruebas: {temp_dir}")
        
        # Crear datos de prueba
        data = create_test_data()
        
        # Guardar los datos de prueba para referencia
        with open(os.path.join(temp_dir, "test_data.json"), "w") as f:
            json.dump(data, f, indent=2)
        
        # Ejecutar las pruebas
        html_path = test_html_generation(temp_dir)
        pdf_weasyprint_path = test_weasyprint_pdf_generation(html_path, temp_dir)
        
        # Si WeasyPrint falla, probar el fallback
        if not pdf_weasyprint_path:
            pdf_reportlab_path = test_reportlab_fallback(temp_dir, data)
            success = pdf_reportlab_path is not None
        else:
            success = True
        
        # Copiar los archivos generados a un directorio permanente si la prueba fue exitosa
        if success:
            output_dir = "pdf_test_output"
            os.makedirs(output_dir, exist_ok=True)
            
            for file in os.listdir(temp_dir):
                src = os.path.join(temp_dir, file)
                dst = os.path.join(output_dir, file)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
            
            print(f"\n✅ Archivos de prueba copiados a {os.path.abspath(output_dir)}")
    
    print("\n" + "-" * 50)
    if success:
        print("✅ Prueba de integración completada con éxito.")
        sys.exit(0)
    else:
        print("❌ La prueba de integración falló. Revisa los errores anteriores.")
        sys.exit(1)


if __name__ == "__main__":
    main()