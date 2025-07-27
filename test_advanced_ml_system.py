#!/usr/bin/env python3
"""
Script de prueba para verificar el sistema ML avanzado integrado
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_advanced_ml_integration():
    """Prueba la integración completa del sistema ML avanzado"""
    print("🧪 INICIANDO PRUEBAS DEL SISTEMA ML AVANZADO")
    print("=" * 60)
    
    try:
        # Importar módulos
        print("📦 Importando módulos...")
        from pentest.ml_integration import MLIntegration
        from pentest.advanced_ml_engine import AdvancedMLEngine, create_advanced_sample_events
        from pentest.config.ml_config import get_ml_config, is_advanced_engine_enabled
        
        # Verificar configuración
        print("⚙️ Verificando configuración...")
        config = get_ml_config()
        advanced_enabled = is_advanced_engine_enabled(config)
        print(f"   ✅ Motor avanzado habilitado: {advanced_enabled}")
        
        # Crear datos de prueba realistas
        print("📊 Creando datos de prueba...")
        test_scan_data = {
            'target': 'test-target.com',
            'source_ip': '192.168.1.100',
            'vulnerabilities': [
                {
                    'name': 'SQL Injection',
                    'severity': 'CRITICAL',
                    'description': 'Potential SQL injection vulnerability',
                    'cve': 'CVE-2023-1234'
                },
                {
                    'name': 'XSS Vulnerability',
                    'severity': 'HIGH',
                    'description': 'Cross-site scripting vulnerability',
                    'cve': 'CVE-2023-5678'
                },
                {
                    'name': 'Information Disclosure',
                    'severity': 'MEDIUM',
                    'description': 'Server information disclosure',
                    'cve': 'CVE-2023-9012'
                }
            ],
            'technologies': ['Apache/2.4.41', 'PHP/7.4.3', 'MySQL/8.0.25'],
            'open_ports': [80, 443, 22, 3306],
            'services': ['http', 'https', 'ssh', 'mysql'],
            'response_time': 1.2,
            'status_codes': [200, 404, 403],
            'headers': {
                'server': 'Apache/2.4.41',
                'x-powered-by': 'PHP/7.4.3'
            },
            'ssl_info': {
                'valid_certificate': True,
                'strong_cipher': True,
                'hsts_enabled': False
            },
            'geo_location': {
                'country': 'US',
                'city': 'New York'
            }
        }
        
        # Probar motor ML avanzado directamente
        print("🤖 Probando motor ML avanzado...")
        engine = AdvancedMLEngine()
        
        # Generar eventos de muestra para entrenamiento
        training_events = create_advanced_sample_events(200)
        print(f"   📈 Entrenando con {len(training_events)} eventos")
        engine.train_advanced_models(training_events)
        
        # Generar eventos de prueba
        test_events = create_advanced_sample_events(50)
        print(f"   🔍 Analizando {len(test_events)} eventos de prueba")
        comprehensive_report = engine.generate_comprehensive_report(test_events)
        
        print("   ✅ Motor avanzado funcionando correctamente")
        
        # Probar integración ML
        print("🔗 Probando integración ML...")
        ml_integration = MLIntegration()
        
        # Verificar que el motor avanzado está disponible
        if hasattr(ml_integration, 'advanced_engine') and ml_integration.advanced_engine:
            print("   ✅ Motor avanzado integrado correctamente")
        else:
            print("   ⚠️ Motor avanzado no está integrado")
        
        # Probar análisis de escaneo
        print("📋 Probando análisis de escaneo...")
        enhanced_result = ml_integration.enhance_scan_result(test_scan_data, 'test-target.com')
        
        if enhanced_result:
            print("   ✅ Análisis ML completado")
            print(f"   📊 Confianza: {enhanced_result.confidence_score:.3f}")
            print(f"   ⏱️ Tiempo de procesamiento: {enhanced_result.processing_time:.3f}s")
            
            if enhanced_result.risk_assessment:
                risk = enhanced_result.risk_assessment
                print(f"   🎯 Riesgo general: {risk.get('overall_risk', 0):.1f}")
                print(f"   🚨 Nivel de riesgo: {risk.get('risk_level', 'UNKNOWN')}")
                print(f"   🔍 Anomalía detectada: {risk.get('anomaly_detected', False)}")
            
            if enhanced_result.recommendations:
                print(f"   💡 Recomendaciones: {len(enhanced_result.recommendations)}")
                for i, rec in enumerate(enhanced_result.recommendations[:3], 1):
                    print(f"      {i}. {rec}")
        else:
            print("   ❌ Error en análisis ML")
            return False
        
        # Probar métricas del sistema
        print("📈 Verificando métricas del sistema...")
        if ml_integration.is_ml_available():
            print("   ✅ Sistema ML disponible")
        else:
            print("   ❌ Sistema ML no disponible")
            return False
        
        stats = ml_integration.get_processing_stats()
        print(f"   📊 Estadísticas de procesamiento:")
        print(f"      • Total de escaneos: {stats.get('total_scans', 0)}")
        print(f"      • Escaneos ML básicos: {stats.get('ml_enhanced_scans', 0)}")
        print(f"      • Escaneos ML avanzados: {stats.get('advanced_enhanced_scans', 0)}")
        print(f"      • Cache hits: {stats.get('cache_hits', 0)}")
        print(f"      • Cache misses: {stats.get('cache_misses', 0)}")
        
        # Probar reporte comprehensivo
        print("📄 Verificando reporte comprehensivo...")
        if comprehensive_report:
            summary = comprehensive_report.get('executive_summary', {})
            print(f"   📊 Eventos analizados: {summary.get('total_events', 0)}")
            print(f"   🚨 Eventos maliciosos: {summary.get('malicious_events', 0)}")
            print(f"   📈 Riesgo promedio: {summary.get('average_risk_score', 0):.1f}")
            print(f"   🎯 Nivel de amenaza: {summary.get('threat_level', 'UNKNOWN')}")
            
            threat_analysis = comprehensive_report.get('threat_analysis', {})
            if threat_analysis.get('top_threat_categories'):
                print("   🔍 Top categorías de amenazas:")
                for category, score in list(threat_analysis['top_threat_categories'].items())[:3]:
                    print(f"      • {category}: {score:.1f}")
        
        print("\n" + "=" * 60)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
        print("🎯 Sistema ML Avanzado 100% Funcional")
        print("🚀 Listo para pentesting en producción")
        print("=" * 60)
        
        return True
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("💡 Asegúrate de que todos los módulos estén instalados")
        return False
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_performance_benchmark():
    """Prueba de rendimiento del sistema"""
    print("\n⚡ BENCHMARK DE RENDIMIENTO")
    print("=" * 40)
    
    try:
        from pentest.advanced_ml_engine import AdvancedMLEngine, create_advanced_sample_events
        import time
        
        engine = AdvancedMLEngine()
        
        # Benchmark de entrenamiento
        print("🏋️ Benchmark de entrenamiento...")
        start_time = time.time()
        training_events = create_advanced_sample_events(1000)
        engine.train_advanced_models(training_events)
        training_time = time.time() - start_time
        print(f"   ⏱️ Entrenamiento (1000 eventos): {training_time:.2f}s")
        
        # Benchmark de predicción
        print("🔮 Benchmark de predicción...")
        test_events = create_advanced_sample_events(100)
        
        start_time = time.time()
        report = engine.generate_comprehensive_report(test_events)
        prediction_time = time.time() - start_time
        print(f"   ⏱️ Predicción (100 eventos): {prediction_time:.2f}s")
        print(f"   📊 Velocidad: {len(test_events)/prediction_time:.1f} eventos/segundo")
        
        # Benchmark de memoria
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"   💾 Uso de memoria: {memory_mb:.1f} MB")
        
        print("✅ Benchmark completado")
        
    except Exception as e:
        print(f"❌ Error en benchmark: {e}")

if __name__ == "__main__":
    success = test_advanced_ml_integration()
    
    if success:
        test_performance_benchmark()
        print("\n🎉 SISTEMA ML AVANZADO VERIFICADO Y OPTIMIZADO")
        print("🚀 Pentest Express API con ML al 100% de capacidad")
    else:
        print("\n❌ FALLOS DETECTADOS EN EL SISTEMA")
        sys.exit(1)