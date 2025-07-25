#!/usr/bin/env python3
"""Script para verificar la disponibilidad de herramientas en el entorno de Render."""

import logging
import os
import sys
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Añadir el directorio actual al PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

try:
    from pentest.runners import run_cmd
except ImportError as e:
    log.error("❌ Error al importar pentest.runners: %s", e)
    sys.exit(1)

def test_tool_availability(tool_name: str, version_cmd: list, description: str):
    """Prueba la disponibilidad de una herramienta específica."""
    log.info("🔧 [TEST] Probando %s (%s)", tool_name, description)
    log.info("🔧 [TEST] Comando: %s", " ".join(version_cmd))
    
    try:
        output = run_cmd(version_cmd, ignore=True, timeout=30)
        if output.strip():
            log.info("🔧 [TEST] ✅ %s está disponible", tool_name)
            log.info("🔧 [TEST] Salida: %s", output.strip()[:200])
            return True
        else:
            log.warning("🔧 [TEST] ⚠️ %s ejecutó pero no devolvió salida", tool_name)
            return False
    except Exception as e:
        log.error("🔧 [TEST] ❌ %s no está disponible: %s", tool_name, e)
        return False

def test_environment():
    """Prueba el entorno general."""
    log.info("🔧 [ENV] Información del entorno:")
    log.info("🔧 [ENV] Python: %s", sys.version)
    log.info("🔧 [ENV] Plataforma: %s", sys.platform)
    log.info("🔧 [ENV] Directorio actual: %s", os.getcwd())
    log.info("🔧 [ENV] PATH: %s", os.environ.get('PATH', 'No definido')[:300] + '...')
    log.info("🔧 [ENV] HOME: %s", os.environ.get('HOME', 'No definido'))
    log.info("🔧 [ENV] USER: %s", os.environ.get('USER', 'No definido'))
    log.info("🔧 [ENV] SHELL: %s", os.environ.get('SHELL', 'No definido'))
    
    # Verificar comandos básicos
    basic_tools = [
        ("which", ["which", "python3"], "Localizar Python"),
        ("ls", ["ls", "-la", "/usr/bin"], "Listar binarios del sistema"),
        ("echo", ["echo", "test"], "Comando básico echo"),
    ]
    
    for tool_name, cmd, desc in basic_tools:
        test_tool_availability(tool_name, cmd, desc)

def test_pentest_tools():
    """Prueba las herramientas específicas de pentesting."""
    tools = [
        ("subfinder", ["subfinder", "-version"], "Herramienta de reconocimiento de subdominios"),
        ("amass", ["amass", "version"], "Herramienta de reconocimiento de subdominios"),
        ("httpx", ["httpx", "-version"], "Herramienta de fingerprinting HTTP"),
        ("nuclei", ["nuclei", "-version"], "Escáner de vulnerabilidades"),
        ("nmap", ["nmap", "--version"], "Escáner de puertos"),
        ("wkhtmltopdf", ["wkhtmltopdf", "--version"], "Generador de PDF"),
    ]
    
    results = {}
    for tool_name, cmd, desc in tools:
        results[tool_name] = test_tool_availability(tool_name, cmd, desc)
    
    return results

def test_python_dependencies():
    """Prueba las dependencias de Python."""
    log.info("🔧 [DEPS] Probando dependencias de Python:")
    
    dependencies = [
        "redis",
        "rq", 
        "requests",
        "jinja2",
        "weasyprint",
        "pdfkit",
        "defusedxml",
        "PyYAML"
    ]
    
    results = {}
    for dep in dependencies:
        try:
            __import__(dep)
            log.info("🔧 [DEPS] ✅ %s está disponible", dep)
            results[dep] = True
        except ImportError as e:
            log.error("🔧 [DEPS] ❌ %s no está disponible: %s", dep, e)
            results[dep] = False
    
    return results

def test_file_permissions():
    """Prueba los permisos de archivos y directorios."""
    log.info("🔧 [PERMS] Probando permisos de archivos:")
    
    # Probar crear directorio temporal
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            log.info("🔧 [PERMS] ✅ Directorio temporal creado: %s", tmp_path)
            
            # Probar escribir archivo
            test_file = tmp_path / "test.txt"
            test_file.write_text("test content")
            log.info("🔧 [PERMS] ✅ Archivo de prueba escrito: %s", test_file)
            
            # Probar leer archivo
            content = test_file.read_text()
            log.info("🔧 [PERMS] ✅ Archivo de prueba leído: %s", content)
            
            return True
    except Exception as e:
        log.error("🔧 [PERMS] ❌ Error con permisos de archivos: %s", e)
        return False

def main():
    """Función principal."""
    log.info("🚀 Iniciando pruebas de herramientas y entorno")
    
    # Probar entorno
    test_environment()
    
    # Probar dependencias de Python
    python_results = test_python_dependencies()
    
    # Probar permisos de archivos
    file_perms = test_file_permissions()
    
    # Probar herramientas de pentesting
    tool_results = test_pentest_tools()
    
    # Resumen
    log.info("🔧 [RESUMEN] Resultados de las pruebas:")
    log.info("🔧 [RESUMEN] Dependencias Python:")
    for dep, available in python_results.items():
        status = "✅" if available else "❌"
        log.info("🔧 [RESUMEN]   %s %s", status, dep)
    
    log.info("🔧 [RESUMEN] Permisos de archivos: %s", "✅" if file_perms else "❌")
    
    log.info("🔧 [RESUMEN] Herramientas de pentesting:")
    for tool, available in tool_results.items():
        status = "✅" if available else "❌"
        log.info("🔧 [RESUMEN]   %s %s", status, tool)
    
    # Determinar si el entorno está listo
    critical_tools = ["subfinder", "amass", "httpx", "nuclei"]
    critical_deps = ["requests", "redis", "rq"]
    
    missing_tools = [tool for tool in critical_tools if not tool_results.get(tool, False)]
    missing_deps = [dep for dep in critical_deps if not python_results.get(dep, False)]
    
    if missing_tools or missing_deps or not file_perms:
        log.error("🔧 [RESUMEN] ❌ El entorno NO está listo para ejecutar escaneos")
        if missing_tools:
            log.error("🔧 [RESUMEN] ❌ Herramientas faltantes: %s", missing_tools)
        if missing_deps:
            log.error("🔧 [RESUMEN] ❌ Dependencias faltantes: %s", missing_deps)
        if not file_perms:
            log.error("🔧 [RESUMEN] ❌ Problemas con permisos de archivos")
        return 1
    else:
        log.info("🔧 [RESUMEN] ✅ El entorno está listo para ejecutar escaneos")
        return 0

if __name__ == "__main__":
    sys.exit(main())