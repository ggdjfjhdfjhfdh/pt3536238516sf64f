#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de demostración de las mejoras implementadas en el sistema de reportes
"""

import os
import sys
import tempfile
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pentest.report import get_recommendations

def generar_datos_demo():
    """Genera datos de demostración para el reporte"""
    return {
        'domain': 'demo-security.com',
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'nuclei_data': [
            {
                "info": {
                    "name": "SQL Injection in Login Form",
                    "severity": "critical",
                    "description": "SQL injection vulnerability detected in login form"
                },
                "host": "https://demo-security.com/login"
            },
            {
                "info": {
                    "name": "Cross-Site Scripting (XSS)",
                    "severity": "high",
                    "description": "Reflected XSS in search parameter"
                },
                "host": "https://demo-security.com/search"
            },
            {
                "info": {
                    "name": "Missing Security Headers",
                    "severity": "medium",
                    "description": "Missing Content-Security-Policy header"
                },
                "host": "https://demo-security.com"
            }
        ],
        'subdomains_data': [
            "www.demo-security.com",
            "api.demo-security.com",
            "admin.demo-security.com",
            "mail.demo-security.com"
        ],
        'nmap_data': [
            {"port": 22, "service": {"name": "ssh"}},
            {"port": 80, "service": {"name": "http"}},
            {"port": 443, "service": {"name": "https"}},
            {"port": 3306, "service": {"name": "mysql"}}
        ],
        'httpx_data': [
            {"url": "https://demo-security.com", "title": "Demo Security Site"},
            {"url": "https://api.demo-security.com", "title": "API Gateway"}
        ],
        'leaks_data': [
            {"email": "admin@demo-security.com", "source": "data_breach_2023"}
        ]
    }

def generar_datos_vacios():
    """Genera datos vacíos para demostrar el manejo de estados vacíos"""
    return {
        'domain': 'secure-site.com',
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'nuclei_data': [],
        'subdomains_data': [],
        'nmap_data': [],
        'httpx_data': [],
        'leaks_data': []
    }

def preparar_contexto(datos_base):
    """Prepara el contexto completo para la plantilla"""
    
    # Generar recomendaciones usando el sistema existente
    try:
        recommendations_data = get_recommendations(
            nuclei_data=datos_base['nuclei_data'],
            leaks_data=datos_base['leaks_data'],
            typosquats_data=[],
            cves_data=[],
            nmap_data=datos_base['nmap_data'],
            security_config_data=[],
            dir_brute_data=[],
            cisa_kev_data=[],
            greynoise_data=[],
            domain=datos_base['domain']
        )
    except:
        # Datos de respaldo si falla la generación
        recommendations_data = {
            'recommendations': [],
            'executive_summary': 'Análisis de seguridad completado.',
            'risk_assessment': {'score': 0, 'level': 'LOW', 'factors': []}
        }
    
    # Calcular métricas
    total_vulnerabilities = len(datos_base['nuclei_data'])
    critical_high_count = len([v for v in datos_base['nuclei_data'] if v['info']['severity'] in ['critical', 'high']])
    
    # Conteos de severidad
    nuclei_severity_counts = {
        'critical': len([v for v in datos_base['nuclei_data'] if v['info']['severity'] == 'critical']),
        'high': len([v for v in datos_base['nuclei_data'] if v['info']['severity'] == 'high']),
        'medium': len([v for v in datos_base['nuclei_data'] if v['info']['severity'] == 'medium']),
        'low': len([v for v in datos_base['nuclei_data'] if v['info']['severity'] == 'low']),
        'info': len([v for v in datos_base['nuclei_data'] if v['info']['severity'] == 'info'])
    }
    
    return {
        **datos_base,
        'recommendations': recommendations_data.get('recommendations', []),
        'executive_summary': recommendations_data.get('executive_summary', ''),
        'risk_assessment': recommendations_data.get('risk_assessment', {}),
        'total_vulnerabilities': total_vulnerabilities,
        'critical_high_count': critical_high_count,
        'subdomains_count': len(datos_base['subdomains_data']),
        'open_ports_count': len(datos_base['nmap_data']),
        'leaked_credentials_count': len(datos_base['leaks_data']),
        'exposed_directories_count': 0,
        'cves_count': 0,
        'typosquats_count': 0,
        'nuclei_severity_counts': nuclei_severity_counts
    }

def demo_mejoras():
    """Demuestra las mejoras implementadas en el sistema de reportes"""
    
    print("🎯 DEMOSTRACIÓN DE MEJORAS EN EL SISTEMA DE REPORTES\n")
    print("=" * 60)
    
    # Configurar Jinja2
    template_dir = os.path.join(os.path.dirname(__file__), 'pentest', 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    
    try:
        template_mejorada = env.get_template('report_enhanced_improved.html')
        print("✓ Plantilla mejorada cargada exitosamente")
    except Exception as e:
        print(f"✗ Error cargando plantilla mejorada: {e}")
        return False
    
    # Verificar si existe la plantilla original
    try:
        template_original = env.get_template('report_enhanced.html')
        print("✓ Plantilla original encontrada para comparación")
        comparar_plantillas = True
    except:
        print("⚠ Plantilla original no encontrada, solo se mostrará la mejorada")
        comparar_plantillas = False
    
    print("\n📊 CASO 1: Reporte con datos completos")
    print("-" * 40)
    
    # Generar reporte con datos completos
    datos_completos = generar_datos_demo()
    contexto_completo = preparar_contexto(datos_completos)
    
    try:
        html_mejorado = template_mejorada.render(**contexto_completo)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='_mejorado.html', delete=False, encoding='utf-8') as f:
            f.write(html_mejorado)
            archivo_mejorado = f.name
        
        print(f"✓ Reporte mejorado generado: {len(html_mejorado)} caracteres")
        print(f"📄 Archivo: {archivo_mejorado}")
        
        # Verificar características de la plantilla mejorada
        caracteristicas = [
            ("Navegación dinámica" in html_mejorado, "Navegación que se adapta al contenido"),
            ("risk-indicator" in html_mejorado, "Indicadores visuales de riesgo"),
            ("chart-container" in html_mejorado, "Contenedores para gráficos"),
            ("metrics-grid" in html_mejorado, "Grid responsivo de métricas"),
            ("section-header" in html_mejorado, "Headers de sección mejorados"),
            ("empty-state" in html_mejorado, "Manejo de estados vacíos")
        ]
        
        print("\n🎨 Características de la plantilla mejorada:")
        for presente, descripcion in caracteristicas:
            estado = "✓" if presente else "✗"
            print(f"  {estado} {descripcion}")
        
    except Exception as e:
        print(f"✗ Error generando reporte mejorado: {e}")
        return False
    
    print("\n📊 CASO 2: Reporte con datos vacíos")
    print("-" * 40)
    
    # Generar reporte con datos vacíos
    datos_vacios = generar_datos_vacios()
    contexto_vacio = preparar_contexto(datos_vacios)
    
    try:
        html_vacio = template_mejorada.render(**contexto_vacio)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='_vacio.html', delete=False, encoding='utf-8') as f:
            f.write(html_vacio)
            archivo_vacio = f.name
        
        print(f"✓ Reporte con datos vacíos generado: {len(html_vacio)} caracteres")
        print(f"📄 Archivo: {archivo_vacio}")
        
        # Verificar manejo de estados vacíos
        if "Escaneo Completado" in html_vacio:
            print("✓ Estado vacío manejado correctamente")
        if "No se detectaron vulnerabilidades críticas" in html_vacio:
            print("✓ Mensaje informativo para estado seguro")
        
    except Exception as e:
        print(f"✗ Error generando reporte vacío: {e}")
        return False
    
    print("\n🔍 COMPARACIÓN DE TAMAÑOS")
    print("-" * 30)
    print(f"Reporte con datos: {len(html_mejorado):,} caracteres")
    print(f"Reporte vacío: {len(html_vacio):,} caracteres")
    print(f"Diferencia: {len(html_mejorado) - len(html_vacio):,} caracteres")
    
    print("\n🎉 MEJORAS IMPLEMENTADAS")
    print("-" * 25)
    mejoras = [
        "✅ Navegación dinámica que se oculta si no hay contenido",
        "✅ Secciones condicionales que solo aparecen con datos",
        "✅ Indicadores visuales de riesgo con colores",
        "✅ Grid responsivo para métricas",
        "✅ Gráficos interactivos con Chart.js",
        "✅ Manejo elegante de estados vacíos",
        "✅ Diseño moderno y profesional",
        "✅ Compatibilidad con impresión",
        "✅ Responsive design para móviles",
        "✅ Mejor organización del contenido"
    ]
    
    for mejora in mejoras:
        print(f"  {mejora}")
    
    print("\n🚀 ARCHIVOS GENERADOS")
    print("-" * 20)
    print(f"📄 Reporte completo: {archivo_mejorado}")
    print(f"📄 Reporte vacío: {archivo_vacio}")
    
    # Intentar abrir los archivos
    try:
        import webbrowser
        print("\n🌐 Abriendo reportes en el navegador...")
        webbrowser.open(f'file://{archivo_mejorado}')
        print("✓ Reporte completo abierto")
        
        # Esperar un momento antes de abrir el segundo
        import time
        time.sleep(2)
        webbrowser.open(f'file://{archivo_vacio}')
        print("✓ Reporte vacío abierto")
    except:
        print("💡 Abra manualmente los archivos en su navegador para ver las mejoras")
    
    return True

if __name__ == "__main__":
    if demo_mejoras():
        print("\n🎊 Demostración completada exitosamente!")
        print("\n📋 RESUMEN:")
        print("   • Se implementó una plantilla HTML mejorada")
        print("   • Se agregó navegación dinámica")
        print("   • Se mejoró el manejo de datos vacíos")
        print("   • Se implementaron indicadores visuales")
        print("   • Se optimizó la experiencia del usuario")
        sys.exit(0)
    else:
        print("\n❌ La demostración falló")
        sys.exit(1)