#!/usr/bin/env python3
"""
Script de instalación para herramientas de detección de tecnologías

Este script automatiza la instalación y configuración de las herramientas
externas necesarias para el sistema mejorado de detección de tecnologías.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path


class TechDetectionInstaller:
    """Instalador para herramientas de detección de tecnologías"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.errors = []
        self.installed_tools = []
        
    def log(self, message, level="INFO"):
        """Log con formato"""
        print(f"[{level}] {message}")
        
    def run_command(self, command, shell=True, check=True):
        """Ejecutar comando del sistema"""
        try:
            self.log(f"Ejecutando: {command}")
            result = subprocess.run(
                command, 
                shell=shell, 
                check=check, 
                capture_output=True, 
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Error ejecutando comando: {e}", "ERROR")
            self.errors.append(f"Comando falló: {command} - {e}")
            return None
            
    def check_tool_installed(self, tool_name, command):
        """Verificar si una herramienta está instalada"""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                self.log(f"✓ {tool_name} ya está instalado")
                return True
            else:
                self.log(f"✗ {tool_name} no está instalado")
                return False
        except Exception as e:
            self.log(f"✗ Error verificando {tool_name}: {e}", "ERROR")
            return False
            
    def install_node_and_npm(self):
        """Instalar Node.js y npm si no están disponibles"""
        self.log("\n=== Verificando Node.js y npm ===")
        
        # Verificar Node.js
        if not self.check_tool_installed("Node.js", "node --version"):
            self.log("Node.js es requerido para Wappalyzer CLI")
            
            if self.system == "windows":
                self.log("Por favor, descarga e instala Node.js desde: https://nodejs.org/")
                self.log("Después de instalar, reinicia este script")
                return False
            elif self.system == "darwin":  # macOS
                if self.check_tool_installed("Homebrew", "brew --version"):
                    self.run_command("brew install node")
                else:
                    self.log("Por favor, instala Homebrew primero: https://brew.sh/")
                    return False
            elif self.system == "linux":
                # Intentar con diferentes gestores de paquetes
                if shutil.which("apt-get"):
                    self.run_command("sudo apt-get update")
                    self.run_command("sudo apt-get install -y nodejs npm")
                elif shutil.which("yum"):
                    self.run_command("sudo yum install -y nodejs npm")
                elif shutil.which("dnf"):
                    self.run_command("sudo dnf install -y nodejs npm")
                else:
                    self.log("Gestor de paquetes no soportado. Instala Node.js manualmente.")
                    return False
        
        # Verificar npm
        if not self.check_tool_installed("npm", "npm --version"):
            self.log("npm no está disponible después de instalar Node.js")
            return False
            
        return True
        
    def install_wappalyzer(self):
        """Instalar Wappalyzer CLI"""
        self.log("\n=== Instalando Wappalyzer CLI ===")
        
        if self.check_tool_installed("Wappalyzer", "wappalyzer --version"):
            self.installed_tools.append("Wappalyzer")
            return True
            
        # Instalar Node.js primero si es necesario
        if not self.install_node_and_npm():
            return False
            
        # Instalar Wappalyzer globalmente
        result = self.run_command("npm install -g wappalyzer")
        if result and result.returncode == 0:
            self.log("✓ Wappalyzer CLI instalado correctamente")
            self.installed_tools.append("Wappalyzer")
            return True
        else:
            self.log("✗ Error instalando Wappalyzer CLI", "ERROR")
            return False
            
    def install_whatweb(self):
        """Instalar WhatWeb"""
        self.log("\n=== Instalando WhatWeb ===")
        
        if self.check_tool_installed("WhatWeb", "whatweb --version"):
            self.installed_tools.append("WhatWeb")
            return True
            
        if self.system == "windows":
            self.log("Para Windows, descarga WhatWeb desde:")
            self.log("https://github.com/urbanadventurer/WhatWeb")
            self.log("O usa WSL (Windows Subsystem for Linux)")
            return False
        elif self.system == "darwin":  # macOS
            if self.check_tool_installed("Homebrew", "brew --version"):
                result = self.run_command("brew install whatweb")
                if result and result.returncode == 0:
                    self.log("✓ WhatWeb instalado correctamente")
                    self.installed_tools.append("WhatWeb")
                    return True
            else:
                self.log("Por favor, instala Homebrew primero: https://brew.sh/")
                return False
        elif self.system == "linux":
            # Intentar con diferentes gestores de paquetes
            if shutil.which("apt-get"):
                self.run_command("sudo apt-get update")
                result = self.run_command("sudo apt-get install -y whatweb")
            elif shutil.which("yum"):
                result = self.run_command("sudo yum install -y whatweb")
            elif shutil.which("dnf"):
                result = self.run_command("sudo dnf install -y whatweb")
            else:
                # Instalar desde código fuente
                self.log("Instalando WhatWeb desde código fuente...")
                commands = [
                    "git clone https://github.com/urbanadventurer/WhatWeb.git /tmp/whatweb",
                    "cd /tmp/whatweb && sudo make install"
                ]
                for cmd in commands:
                    result = self.run_command(cmd)
                    if not result or result.returncode != 0:
                        return False
                        
            if result and result.returncode == 0:
                self.log("✓ WhatWeb instalado correctamente")
                self.installed_tools.append("WhatWeb")
                return True
                
        self.log("✗ Error instalando WhatWeb", "ERROR")
        return False
        
    def verify_python_dependencies(self):
        """Verificar dependencias de Python"""
        self.log("\n=== Verificando dependencias de Python ===")
        
        required_packages = [
            "requests",
            "httpx",
            "PyYAML",
            "urllib3"
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.lower().replace("-", "_"))
                self.log(f"✓ {package} está disponible")
            except ImportError:
                self.log(f"✗ {package} no está disponible")
                missing_packages.append(package)
                
        if missing_packages:
            self.log(f"Instalando paquetes faltantes: {', '.join(missing_packages)}")
            pip_cmd = f"{sys.executable} -m pip install {' '.join(missing_packages)}"
            result = self.run_command(pip_cmd)
            
            if result and result.returncode == 0:
                self.log("✓ Dependencias de Python instaladas")
                return True
            else:
                self.log("✗ Error instalando dependencias de Python", "ERROR")
                return False
        else:
            self.log("✓ Todas las dependencias de Python están disponibles")
            return True
            
    def create_config_files(self):
        """Crear archivos de configuración por defecto"""
        self.log("\n=== Creando archivos de configuración ===")
        
        # Crear directorio de configuración si no existe
        config_dir = Path("pentest/config")
        config_dir.mkdir(exist_ok=True)
        
        # Archivo de configuración para herramientas
        tools_config = {
            "wappalyzer": {
                "enabled": "wappalyzer" in [tool.lower() for tool in self.installed_tools],
                "timeout": 30,
                "user_agent": "Mozilla/5.0 (compatible; TechDetector/1.0)"
            },
            "whatweb": {
                "enabled": "whatweb" in [tool.lower() for tool in self.installed_tools],
                "aggression": 3,
                "timeout": 25
            },
            "httpx": {
                "enabled": True,
                "tech_detect": True,
                "follow_redirects": True,
                "timeout": 20
            }
        }
        
        config_file = config_dir / "tech_detection_tools.yaml"
        try:
            import yaml
            with open(config_file, 'w') as f:
                yaml.dump(tools_config, f, default_flow_style=False)
            self.log(f"✓ Configuración creada en: {config_file}")
        except ImportError:
            self.log("PyYAML no disponible, creando configuración en formato JSON")
            import json
            config_file = config_dir / "tech_detection_tools.json"
            with open(config_file, 'w') as f:
                json.dump(tools_config, f, indent=2)
            self.log(f"✓ Configuración creada en: {config_file}")
            
    def run_tests(self):
        """Ejecutar pruebas básicas de las herramientas instaladas"""
        self.log("\n=== Ejecutando pruebas básicas ===")
        
        test_url = "https://httpbin.org/html"
        
        # Probar Wappalyzer
        if "Wappalyzer" in self.installed_tools:
            self.log("Probando Wappalyzer...")
            result = self.run_command(f"wappalyzer {test_url}", check=False)
            if result and result.returncode == 0:
                self.log("✓ Wappalyzer funciona correctamente")
            else:
                self.log("⚠ Wappalyzer puede tener problemas", "WARNING")
                
        # Probar WhatWeb
        if "WhatWeb" in self.installed_tools:
            self.log("Probando WhatWeb...")
            result = self.run_command(f"whatweb --quiet {test_url}", check=False)
            if result and result.returncode == 0:
                self.log("✓ WhatWeb funciona correctamente")
            else:
                self.log("⚠ WhatWeb puede tener problemas", "WARNING")
                
        # Probar httpx
        try:
            import httpx
            self.log("Probando httpx...")
            # Prueba básica sin hacer petición real
            client = httpx.Client(timeout=5)
            client.close()
            self.log("✓ httpx funciona correctamente")
        except Exception as e:
            self.log(f"⚠ httpx puede tener problemas: {e}", "WARNING")
            
    def generate_report(self):
        """Generar reporte de instalación"""
        self.log("\n" + "="*50)
        self.log("REPORTE DE INSTALACIÓN")
        self.log("="*50)
        
        self.log(f"Sistema operativo: {platform.system()} {platform.release()}")
        self.log(f"Python: {sys.version}")
        
        self.log("\nHerramientas instaladas:")
        if self.installed_tools:
            for tool in self.installed_tools:
                self.log(f"  ✓ {tool}")
        else:
            self.log("  ✗ Ninguna herramienta nueva instalada")
            
        if self.errors:
            self.log("\nErrores encontrados:")
            for error in self.errors:
                self.log(f"  ✗ {error}")
        else:
            self.log("\n✓ Instalación completada sin errores")
            
        self.log("\nPróximos pasos:")
        self.log("1. Ejecuta 'python pentest/example_enhanced_usage.py' para probar")
        self.log("2. Revisa la configuración en 'pentest/config/'")
        self.log("3. Consulta 'pentest/README_MEJORAS_TECNOLOGIAS.md' para más información")
        
    def install_all(self):
        """Ejecutar instalación completa"""
        self.log("Iniciando instalación de herramientas de detección de tecnologías...")
        self.log(f"Sistema detectado: {self.system}")
        
        # Verificar dependencias de Python
        self.verify_python_dependencies()
        
        # Instalar herramientas externas
        self.install_wappalyzer()
        self.install_whatweb()
        
        # Crear configuración
        self.create_config_files()
        
        # Ejecutar pruebas
        self.run_tests()
        
        # Generar reporte
        self.generate_report()


def main():
    """Función principal"""
    print("🔧 Instalador de Herramientas de Detección de Tecnologías")
    print("=" * 60)
    
    installer = TechDetectionInstaller()
    
    try:
        installer.install_all()
    except KeyboardInterrupt:
        print("\n\n⚠ Instalación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error inesperado: {e}")
        sys.exit(1)
        
    if installer.errors:
        print("\n⚠ Instalación completada con errores. Revisa el reporte anterior.")
        sys.exit(1)
    else:
        print("\n✅ Instalación completada exitosamente!")
        sys.exit(0)


if __name__ == "__main__":
    main()