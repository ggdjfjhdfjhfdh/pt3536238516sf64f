# 🔄 Solución para Manejo de Redirecciones 301 y AbandonedJobError

## 📋 Problema Identificado

El escaneo de `sesecpro.es` se detuvo debido a:

1. **Redirecciones 301**: URLs como `dump.sql.aspx`, `dump.sql.zip` y `export.aspx` devolvían redirecciones permanentes
2. **AbandonedJobError**: El trabajo `c8f9b32c-42bc-4036-8f7b-30976a2fec8f` se movió al `FailedJobRegistry` debido a timeout
3. **Timeout insuficiente**: El job_timeout de 1 hora era insuficiente para escaneos con muchas redirecciones

## 🛠️ Soluciones Implementadas

### 1. Manejo Mejorado de Redirecciones en dir_brute.py

**Cambios realizados:**
- Agregado manejo específico para códigos de estado 301/302
- Las redirecciones ahora se reportan como hallazgos válidos
- Se captura la URL de destino de la redirección

```python
# Manejar redirecciones 301/302 como hallazgos potenciales
if response.status_code in [301, 302]:
    location = response.headers.get('location', '')
    log.debug(f"[+] Redirección encontrada: {test_url} -> {location} (Status: {response.status_code})")
    return {
        "url": test_url,
        "status_code": response.status_code,
        "description": f"Redirección encontrada: {test_url} -> {location}",
        "redirect_location": location
    }
```

### 2. Aumento del Timeout de Trabajos RQ

**Cambios en main.py:**
- Aumentado `job_timeout` de 1 hora a 2 horas
- Mantenido `result_ttl` en 24 horas

```python
job = q.enqueue(
    'pentest.core._run_scan_job', 
    dominio, 
    email,
    job_timeout=2 * 60 * 60,  # 2 horas (aumentado para manejar redirecciones)
    result_ttl=24 * 60 * 60   # 24 horas
)
```

### 3. Manejo Mejorado de Excepciones

**Mejoras en el manejo de errores:**
- Separación específica de `TimeoutException` y `ConnectError`
- Logging más granular (debug vs warning)
- Mejor resilencia a errores de red

```python
except httpx.TimeoutException as e:
    log.debug(f"Timeout al escanear {test_url}: {e}")
    return None
except httpx.ConnectError as e:
    log.debug(f"Error de conexión al escanear {test_url}: {e}")
    return None
except httpx.RequestError as e:
    log.debug(f"Error de petición al escanear {test_url}: {e}")
    return None
```

## 🎯 Beneficios de la Solución

### ✅ Resolución de Problemas
1. **Redirecciones 301/302**: Ahora se manejan como hallazgos válidos en lugar de ser ignoradas
2. **AbandonedJobError**: El timeout aumentado reduce la probabilidad de trabajos abandonados
3. **Logging mejorado**: Mejor visibilidad de errores de red y timeouts

### 📈 Mejoras de Rendimiento
1. **Continuidad del escaneo**: Las redirecciones no detienen el proceso
2. **Información valiosa**: Se captura la URL de destino de las redirecciones
3. **Resilencia**: Mejor manejo de errores de red temporales

## 🔍 Archivos Modificados

1. **`pentest/dir_brute.py`**:
   - Manejo de redirecciones 301/302
   - Mejora en el manejo de excepciones
   - Logging más granular

2. **`services/api-fastapi/app/main.py`**:
   - Aumento del `job_timeout` a 2 horas
   - Configuración explícita de `result_ttl`

## 🧪 Verificación de la Solución

### Casos de Prueba
1. **Redirecciones**: URLs que devuelven 301/302 se reportan correctamente
2. **Timeouts**: Trabajos largos no se abandonan prematuramente
3. **Errores de red**: El escaneo continúa a pesar de errores temporales

### Métricas de Éxito
- ✅ Redirecciones capturadas como hallazgos
- ✅ Trabajos completados sin AbandonedJobError
- ✅ Logs más informativos y menos verbosos

## 🚀 Próximos Pasos

1. **Monitoreo**: Observar el comportamiento en escaneos futuros
2. **Optimización**: Ajustar timeouts según patrones observados
3. **Documentación**: Actualizar guías de troubleshooting

---

**Fecha de implementación**: 2025-01-28  
**Versión**: 1.0  
**Estado**: ✅ Implementado y listo para pruebas