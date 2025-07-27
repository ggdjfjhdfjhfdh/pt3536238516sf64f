# Resumen de Correcciones - Sistema de Detección WAF

## Problema Original

El sistema de detección de WAF estaba fallando con el error:
```
ERROR:ScanPipeline:🛡️ [WAF] Error detectando WAF para sesecpro.es: 'confidence'
```

## Causa del Problema

El error se debía a un acceso incorrecto al campo `confidence` en la estructura de datos devuelta por el sistema de detección de WAF. El código intentaba acceder directamente a `waf_info['confidence']` cuando el campo real estaba anidado en `waf_info['detection_details']['confidence']`.

## Archivos Modificados

### 1. `pentest/waf_integration.py`

**Línea 47:** Corregido el acceso al campo confidence
```python
# ANTES:
log.info(f"WAF detectado: {waf_info['waf_type']} (confianza: {waf_info['confidence']}%)")

# DESPUÉS:
confidence = waf_info.get('detection_details', {}).get('confidence', 0)
log.info(f"WAF detectado: {waf_info['waf_type']} (confianza: {confidence}%)")
```

### 2. `pentest/core.py`

**Línea 513:** Corregido el acceso al campo confidence en la preparación del resultado
```python
# ANTES:
"confidence": waf_info.get("confidence", 0) if waf_info else 0,

# DESPUÉS:
"confidence": waf_info.get("detection_details", {}).get("confidence", 0) if waf_info else 0,
```

## Estructura Correcta de Datos WAF

La estructura correcta devuelta por `detect_waf_for_domain()` es:

```python
{
    "domain": "example.com",
    "waf_type": "none",  # o el tipo de WAF detectado
    "detection_details": {
        "detected_patterns": [],
        "confidence": 0,  # ← Campo confidence está aquí
        "evidence": {}
    },
    "evasion_config": {
        "user_agents": [...],
        "headers": {},
        "delays": {...},
        "max_requests_per_minute": 15
    }
}
```

## Verificación de las Correcciones

Se creó y ejecutó un script de prueba que verificó:

1. ✅ **Función `detect_waf_for_domain`**: Funciona correctamente y devuelve la estructura esperada
2. ✅ **Clase `WAFIntegratedScanner.detect_waf`**: Funciona correctamente sin errores de acceso a campos
3. ✅ **Acceso al campo `confidence`**: Se accede correctamente usando la ruta anidada
4. ✅ **Manejo de estructuras vacías**: Se maneja correctamente cuando no hay datos de WAF

## Resultado

Todas las correcciones se implementaron exitosamente. El sistema de detección de WAF ahora:

- ✅ Accede correctamente al campo `confidence` desde `detection_details`
- ✅ Maneja casos donde no hay información de WAF disponible
- ✅ Registra correctamente la información de confianza en los logs
- ✅ Prepara correctamente los resultados para el pipeline de escaneo

## Impacto

Estas correcciones resuelven el error `'confidence'` que impedía la correcta ejecución del paso de detección de WAF en el pipeline de escaneo, permitiendo que el proceso continúe sin interrupciones.