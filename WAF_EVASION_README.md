# 🛡️ Sistema Avanzado de Evasión WAF

Este documento describe las nuevas funcionalidades implementadas para manejar y evadir Web Application Firewalls (WAF) durante las pruebas de penetración.

## 📋 Características Principales

### 🔍 Detección Automática de WAF
- **Cloudflare**: Detección por headers `cf-ray`, cookies `__cfduid`, patrones en contenido
- **AWS WAF**: Identificación por headers `x-amzn-requestid`, patrones específicos
- **Akamai**: Detección por `x-akamai-transformed`, patrones de bloqueo
- **Incapsula**: Identificación por cookies `incap_ses`, headers `x-iinfo`
- **Barracuda**: Detección por headers de servidor específicos
- **F5 Big-IP**: Identificación por cookies `BIGipServer`, headers característicos
- **Sucuri**: Detección por headers `cloudproxy`, patrones de contenido

### ⚙️ Técnicas de Evasión Específicas

Cada tipo de WAF tiene configuraciones optimizadas:

#### Cloudflare
- **User-Agents**: Bots legítimos (Googlebot, Bingbot, Facebookbot)
- **Headers especiales**: `CF-Connecting-IP`, `CF-IPCountry`, `X-Forwarded-For`
- **Throttling**: Máximo 10 peticiones/minuto con delays de 2-5 segundos

#### AWS WAF
- **User-Agents**: Bots de búsqueda y herramientas estándar
- **Headers**: `X-Forwarded-For`, `X-Real-IP`
- **Throttling**: Máximo 20 peticiones/minuto con delays de 1-3 segundos

#### Akamai
- **Headers específicos**: `Akamai-Origin-Hop`
- **Throttling agresivo**: Máximo 8 peticiones/minuto con delays de 3-6 segundos

## 🚀 Módulos Implementados

### 1. `waf_handler.py`
**Funcionalidades principales:**
- `WAFDetector`: Clase para detectar tipos de WAF
- `WAFEvasionTechniques`: Configuraciones específicas por WAF
- `WAFAwareHTTPClient`: Cliente HTTP inteligente que se adapta al WAF
- `make_waf_aware_request()`: Función de conveniencia para peticiones

### 2. `waf_integration.py`
**Funcionalidades principales:**
- `WAFIntegratedScanner`: Scanner con evasión WAF integrada
- `create_waf_aware_pipeline()`: Pipeline completo de pentesting
- Funciones mejoradas para dir_brute, security_config y fingerprinting

### 3. `dir_brute.py` (Actualizado)
**Mejoras implementadas:**
- Detección automática de WAF por host
- Configuración dinámica de delays y headers
- Detección de bloqueos por WAF
- Throttling inteligente basado en el tipo de WAF

## 🧪 Script de Pruebas

### `test_waf_evasion.py`
Script completo para probar las funcionalidades:

```bash
# Detección de WAF únicamente
python test_waf_evasion.py https://example.com detect

# Prueba de petición con evasión
python test_waf_evasion.py https://example.com request

# Directory bruteforce mejorado
python test_waf_evasion.py https://example.com dirbrute

# Pipeline completo
python test_waf_evasion.py https://example.com pipeline
```

## 📊 Uso en el Sistema Existente

### Integración Automática
Los módulos existentes han sido actualizados para usar automáticamente las nuevas capacidades:

1. **Directory Bruteforce**: Ahora detecta WAF y ajusta estrategias
2. **Security Config**: Usa peticiones con evasión WAF
3. **Fingerprinting**: Adapta técnicas según el WAF detectado

### Uso Manual
```python
from pentest.waf_handler import make_waf_aware_request, detect_waf_for_domain
from pentest.waf_integration import WAFIntegratedScanner

# Detectar WAF
waf_info = detect_waf_for_domain('example.com')
print(f"WAF detectado: {waf_info['waf_type']}")

# Petición con evasión
response = make_waf_aware_request('https://example.com/admin')

# Scanner integrado
scanner = WAFIntegratedScanner()
results = scanner.enhanced_dir_brute('https://example.com', ['admin', 'login'])
```

## 🔧 Configuración Avanzada

### Variables de Entorno
```bash
# Configurar delays personalizados
export WAF_MIN_DELAY=2
export WAF_MAX_DELAY=5

# Configurar límites de peticiones
export WAF_MAX_REQUESTS_PER_MINUTE=10

# Habilitar logging detallado
export WAF_DEBUG=true
```

### Configuración en `config.py`
Las configuraciones existentes en `WAF_EVASION_CONFIG` se mantienen compatibles y se complementan con las nuevas funcionalidades.

## 📈 Métricas y Monitoreo

### Información Recopilada
- **Tipo de WAF detectado** con nivel de confianza
- **Número de peticiones bloqueadas** vs exitosas
- **Tiempo de respuesta promedio** por tipo de WAF
- **Efectividad de técnicas de evasión** por WAF

### Archivos de Salida
Cada escaneo genera:
- `waf_detection.json`: Información del WAF detectado
- `pipeline_results.json`: Resultados completos del pipeline
- Archivos específicos por módulo (dir_brute.json, security_config.json, etc.)

## 🛠️ Solución de Problemas

### Problemas Comunes

#### 1. Muchas peticiones bloqueadas
**Síntomas**: Alto número en `blocked_attempts`
**Solución**: 
- Aumentar delays en la configuración
- Reducir concurrencia
- Verificar User-Agents utilizados

#### 2. WAF no detectado correctamente
**Síntomas**: WAF tipo `UNKNOWN` o `NONE`
**Solución**:
- Verificar conectividad al target
- Revisar logs de detección
- Probar con diferentes endpoints

#### 3. Timeouts frecuentes
**Síntomas**: Errores de timeout en peticiones
**Solución**:
- Aumentar `max_time` en configuración
- Reducir concurrencia
- Verificar estabilidad de la red

### Logging y Debug
```python
import logging
logging.getLogger('pentest.waf_handler').setLevel(logging.DEBUG)
logging.getLogger('pentest.waf_integration').setLevel(logging.DEBUG)
```

## 🔄 Compatibilidad

### Retrocompatibilidad
- Todos los módulos existentes siguen funcionando sin cambios
- Las configuraciones anteriores se mantienen válidas
- Los archivos de salida mantienen el formato original con campos adicionales

### Migración
Para aprovechar las nuevas funcionalidades:
1. Usar `test_waf_evasion.py` para probar el target
2. Revisar logs para verificar detección de WAF
3. Ajustar configuraciones según resultados
4. Usar pipeline completo para escaneos de producción

## 📚 Referencias

### Documentación Técnica
- [OWASP WAF Evasion](https://owasp.org/www-community/attacks/Web_Application_Firewall_Evasion)
- [Cloudflare Security Features](https://developers.cloudflare.com/security/)
- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/)

### Herramientas Relacionadas
- [wafw00f](https://github.com/EnableSecurity/wafw00f): Herramienta de detección WAF
- [bypass-firewalls-by-DNS-history](https://github.com/vincentcox/bypass-firewalls-by-DNS-history)
- [CloudFlair](https://github.com/christophetd/CloudFlair): Bypass Cloudflare

---

## 🎯 Casos de Uso Específicos

### Cloudflare con Rate Limiting Agresivo
```python
# Configuración específica para Cloudflare estricto
from pentest.waf_integration import create_waf_aware_pipeline

# Pipeline con configuración conservadora
results = create_waf_aware_pipeline(
    'https://target-with-cloudflare.com',
    './cloudflare_scan'
)
```

### Múltiples Dominios con Diferentes WAF
```python
from pentest.waf_handler import save_waf_analysis

domains = ['site1.com', 'site2.com', 'site3.com']
waf_analysis = save_waf_analysis(domains, Path('./waf_analysis.json'))
```

### Escaneo Stealth para Evasión Máxima
```python
from pentest.waf_integration import WAFIntegratedScanner

scanner = WAFIntegratedScanner()
# El scanner automáticamente ajusta la agresividad según el WAF
results = scanner.enhanced_dir_brute(
    'https://heavily-protected-site.com',
    ['admin', 'login']  # Wordlist mínima para stealth
)
```

Este sistema proporciona una solución completa y automatizada para manejar WAFs durante pruebas de penetración, mejorando significativamente la efectividad de los escaneos mientras reduce la probabilidad de detección.