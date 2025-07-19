#!/usr/bin/env python
"""
Test script para verificar la correcta instalación y funcionamiento de WeasyPrint
y sus dependencias.

Este script intenta generar un PDF simple usando WeasyPrint y reporta cualquier error
que ocurra durante el proceso.

Uso:
    python test_weasyprint.py
"""

import os
import sys
import traceback

def test_weasyprint():
    """Prueba la funcionalidad básica de WeasyPrint."""
    print("Iniciando prueba de WeasyPrint...")
    
    try:
        # Intentar importar WeasyPrint
        print("Importando WeasyPrint...")
        from weasyprint import HTML, CSS
        print("✅ WeasyPrint importado correctamente")
        
        # Verificar la versión
        import weasyprint
        print(f"Versión de WeasyPrint: {weasyprint.__version__}")
        
        # Crear un HTML simple
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test WeasyPrint</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 2cm; }
                h1 { color: #1a237e; }
                .box { border: 1px solid #ccc; padding: 1em; margin: 1em 0; }
            </style>
        </head>
        <body>
            <h1>Test de WeasyPrint</h1>
            <p>Este es un documento de prueba para verificar que WeasyPrint funciona correctamente.</p>
            <div class="box">
                <p>Si puedes ver este PDF, WeasyPrint está funcionando correctamente.</p>
            </div>
        </body>
        </html>
        """
        
        # Crear un archivo temporal para el PDF
        output_path = "test_weasyprint_output.pdf"
        
        # Generar el PDF
        print(f"Generando PDF en {output_path}...")
        HTML(string=html_content).write_pdf(output_path)
        
        # Verificar que el archivo existe y tiene contenido
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"✅ PDF generado correctamente en {output_path} ({os.path.getsize(output_path)} bytes)")
            return True
        else:
            print(f"❌ Error: El archivo PDF no existe o está vacío")
            return False
            
    except ImportError as e:
        print(f"❌ Error al importar WeasyPrint: {e}")
        print("Asegúrate de que WeasyPrint esté instalado correctamente.")
        print("Puedes instalarlo con: pip install weasyprint")
        return False
    except Exception as e:
        print(f"❌ Error al generar el PDF: {e}")
        print("Detalles del error:")
        traceback.print_exc()
        return False

def check_dependencies():
    """Verifica las dependencias del sistema para WeasyPrint."""
    print("\nVerificando dependencias del sistema...")
    
    try:
        # Intentar importar las bibliotecas de CFFI necesarias
        import cffi
        print(f"✅ CFFI instalado (versión {cffi.__version__})")
    except ImportError:
        print("❌ CFFI no está instalado. Es necesario para WeasyPrint.")
    
    # Verificar bibliotecas del sistema
    libraries = [
        "libglib-2.0.so.0",
        "libgobject-2.0.so.0",
        "libpango-1.0.so.0",
        "libpangoft2-1.0.so.0",
        "libharfbuzz.so.0",
        "libfontconfig.so.1"
    ]
    
    import ctypes
    import ctypes.util
    
    for lib in libraries:
        try:
            lib_path = ctypes.util.find_library(lib.split('.')[0])
            if lib_path:
                ctypes.CDLL(lib_path)
                print(f"✅ {lib} encontrado y cargado correctamente")
            else:
                print(f"❌ {lib} no encontrado en el sistema")
        except Exception as e:
            print(f"❌ Error al cargar {lib}: {e}")

def main():
    """Función principal."""
    print("=== Test de WeasyPrint y sus dependencias ===")
    print(f"Python {sys.version} en {sys.executable}")
    print(f"Sistema operativo: {os.name} - {sys.platform}")
    print("-" * 50)
    
    success = test_weasyprint()
    check_dependencies()
    
    print("\n" + "-" * 50)
    if success:
        print("✅ Prueba completada con éxito. WeasyPrint está funcionando correctamente.")
        sys.exit(0)
    else:
        print("❌ La prueba falló. Revisa los errores anteriores.")
        sys.exit(1)

if __name__ == "__main__":
    main()