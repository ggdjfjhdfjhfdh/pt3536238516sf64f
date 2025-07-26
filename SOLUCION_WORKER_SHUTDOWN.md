# Solución: Worker se cierra después de dir_brute

## 🔍 Problema Identificado

El worker de RQ se cierra después de completar el paso `dir_brute` porque:

1. **Redis remoto no disponible**: El worker intenta conectarse a `red-d20a0bvgi27c73cbmk3g:6379` (servidor de Render.com)
2. **Configuración de producción en desarrollo**: `REDIS_URL` apunta a un servidor remoto no accesible localmente
3. **Pérdida de conexión**: El worker se cierra automáticamente al no poder mantener la conexión con Redis

## 💡 Soluciones Disponibles

### Opción 1: Redis con Docker (Recomendado)

1. **Iniciar Redis localmente:**
   ```bash
   # Ejecutar el script incluido
   start_redis_docker.bat
   
   # O manualmente:
   docker run -d --name redis-local -p 6379:6379 redis:alpine
   ```

2. **Ejecutar worker patcheado:**
   ```bash
   python worker_patched.py
   ```

3. **Probar escaneo:**
   ```bash
   # Desde la API o directamente
   python test_pipeline_direct.py sesecpro.es
   ```

### Opción 2: Prueba Directa (Sin Worker)

**Ejecutar pipeline directamente sin RQ:**
```bash
python test_pipeline_direct.py sesecpro.es
```

Esta opción:
- ✅ Evita problemas de Redis/RQ
- ✅ Conserva archivos temporales para debug
- ✅ Ejecuta todos los pasos del pipeline
- ✅ Genera el reporte PDF completo

### Opción 3: Configuración Local Permanente

1. **Modificar variables de entorno:**
   ```bash
   set REDIS_URL=redis://localhost:6379
   ```

2. **Usar configuración local:**
   ```python
   # Importar al inicio de scripts
   import local_config
   ```

## 📋 Archivos Creados

- `worker_patched.py` - Worker RQ con manejo robusto de errores
- `start_redis_docker.bat` - Script para iniciar Redis con Docker
- `test_pipeline_direct.py` - Prueba del pipeline sin RQ
- `local_config.py` - Configuración local de desarrollo
- `fix_worker_shutdown.py` - Script de diagnóstico completo

## 🚀 Pasos Recomendados

1. **Iniciar Redis:**
   ```bash
   start_redis_docker.bat
   ```

2. **Probar pipeline directamente:**
   ```bash
   python test_pipeline_direct.py sesecpro.es
   ```

3. **Si funciona, ejecutar worker:**
   ```bash
   python worker_patched.py
   ```

4. **Verificar que el worker permanece activo:**
   - El worker debe mostrar "Escuchando trabajos..."
   - No debe cerrarse después de dir_brute
   - Debe completar todo el pipeline

## 🔧 Verificación

**Para confirmar que el problema está resuelto:**

1. El worker debe permanecer activo durante todo el escaneo
2. Todos los pasos del pipeline deben ejecutarse:
   - ✅ recon
   - ✅ fingerprint
   - ✅ dir_brute
   - ✅ nuclei_scan (debe continuar después de dir_brute)
   - ✅ cve_scan
   - ✅ threat_intel
   - ✅ generate_pdf

3. El reporte PDF debe generarse correctamente
4. No debe aparecer el mensaje "warm shut down requested"

## 📞 Soporte

Si el problema persiste:

1. Ejecutar diagnóstico completo:
   ```bash
   python fix_worker_shutdown.py --analyze
   ```

2. Revisar logs del worker para errores específicos

3. Verificar que Redis esté ejecutándose:
   ```bash
   docker logs redis-local
   ```