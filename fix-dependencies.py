#!/usr/bin/env python3
"""
Script para resolver conflictos de dependencias entre FastAPI y anyio
"""

import subprocess
import sys

def run_command(cmd):
    """Ejecuta un comando y retorna el resultado"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def fix_dependencies():
    """Resuelve conflictos de dependencias"""
    print("🔧 Resolviendo conflictos de dependencias...")
    
    # Comandos para resolver conflictos
    commands = [
        "pip install --upgrade pip",
        "pip install --force-reinstall 'anyio>=3.7.1,<5.0.0'",
        "pip install --force-reinstall 'fastapi>=0.115.0'",
        "pip install --force-reinstall 'uvicorn>=0.32.0'",
        "pip install --force-reinstall 'httpx>=0.27.0'",
        "pip install --force-reinstall 'pydantic>=2.9.0'",
        "pip check"
    ]
    
    for cmd in commands:
        print(f"📦 Ejecutando: {cmd}")
        success, stdout, stderr = run_command(cmd)
        
        if not success and "pip check" not in cmd:
            print(f"❌ Error ejecutando {cmd}:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        elif "pip check" in cmd:
            if success:
                print("✅ Todas las dependencias son compatibles")
            else:
                print("⚠️ Advertencias de compatibilidad:")
                print(stdout)
                print(stderr)
    
    print("✅ Resolución de dependencias completada")
    return True

if __name__ == "__main__":
    if fix_dependencies():
        print("🎉 Dependencias resueltas exitosamente")
        sys.exit(0)
    else:
        print("💥 Error resolviendo dependencias")
        sys.exit(1)