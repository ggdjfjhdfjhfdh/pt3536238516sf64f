#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para resolver conflictos de dependencias de Python.
Este script verifica y resuelve conflictos comunes entre paquetes.
"""

import subprocess
import sys
import pkg_resources
from packaging import version

def check_and_fix_dependencies():
    """Verifica y resuelve conflictos de dependencias."""
    print("🔧 Verificando dependencias...")
    
    # Conflictos conocidos y sus resoluciones
    known_conflicts = {
        'anyio': '>=3.7.1,<5.0.0',
        'httpx': '>=0.27.0,<1.0.0',
        'requests': '>=2.32.0',
        'urllib3': '>=2.0.0',
        'pydantic': '>=2.0.0',
        'fastapi': '>=0.115.0,<1.0.0',
        'uvicorn': '>=0.32.0,<1.0.0',
        'redis': '>=5.0.0,<6.0.0',
        'rq': '>=1.15.0,<2.0.0'
    }
    
    try:
        # Verificar paquetes instalados
        installed_packages = {pkg.project_name.lower(): pkg.version 
                            for pkg in pkg_resources.working_set}
        
        print(f"📦 Paquetes instalados: {len(installed_packages)}")
        
        # Verificar conflictos específicos
        conflicts_found = []
        
        for package, required_version in known_conflicts.items():
            if package.lower() in installed_packages:
                current_version = installed_packages[package.lower()]
                print(f"✓ {package}: {current_version}")
            else:
                print(f"⚠️  {package}: No instalado")
                conflicts_found.append(package)
        
        # Verificar conflictos de versiones
        print("\n🔍 Verificando conflictos de versiones...")
        try:
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'check'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"⚠️  Conflictos detectados:\n{result.stdout}")
            else:
                print("✅ No se detectaron conflictos")
        except Exception as e:
            print(f"❌ Error verificando conflictos: {e}")
        
        # Resolver conflictos si es necesario
        if conflicts_found:
            print(f"\n🔄 Resolviendo {len(conflicts_found)} conflictos...")
            for package in conflicts_found:
                try:
                    cmd = [sys.executable, '-m', 'pip', 'install', f'{package}{known_conflicts[package]}']
                    print(f"📦 Instalando: {package}{known_conflicts[package]}")
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    print(f"✓ Resuelto: {package}")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Error resolviendo {package}: {e}")
                    print(f"   stdout: {e.stdout}")
                    print(f"   stderr: {e.stderr}")
        
        print("✅ Verificación de dependencias completada")
        
    except Exception as e:
        print(f"❌ Error durante la verificación: {e}")
        return False
    
    return True

def upgrade_pip():
    """Actualiza pip a la última versión."""
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                      check=True, capture_output=True)
        print("✅ pip actualizado")
    except subprocess.CalledProcessError:
        print("⚠️  No se pudo actualizar pip")

def main():
    """Función principal."""
    print("🚀 Iniciando resolución de dependencias...")
    
    # Actualizar pip primero
    upgrade_pip()
    
    # Verificar y resolver dependencias
    success = check_and_fix_dependencies()
    
    if success:
        print("🎉 Resolución de dependencias exitosa")
        sys.exit(0)
    else:
        print("💥 Falló la resolución de dependencias")
        sys.exit(1)

if __name__ == '__main__':
    main()