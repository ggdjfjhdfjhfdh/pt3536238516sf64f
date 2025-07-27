# Solución para el Error de Plantilla report.html

## Problema Identificado

El error `jinja2.exceptions.TemplateNotFound: report.html` ocurría en el entorno de producción (Docker) porque:

1. El `.dockerignore` no incluía explícitamente todos los archivos necesarios del paquete `pentest`
2. El `Dockerfile` no instalaba el paquete `pentest` correctamente, causando que las plantillas no estuvieran disponibles para `PackageLoader`

## Solución Implementada

### 1. Actualización del .dockerignore

```diff
# Permitir archivos en la raíz necesarios para scan-runner
!run_scan.py
!requirements.txt
!Dockerfile.scan-runner
!setup.py
+!MANIFEST.in
!pentest/
+!pentest/**
!templates/
!fix-dependencies.py
```

### 2. Mejora del Dockerfile

```diff
+# Copiar archivos del proyecto
COPY services/api-fastapi/app services/api-fastapi/app
COPY . .
+
+# Instalar el paquete pentest para asegurar que las plantillas estén disponibles
+RUN pip install -e .
+
ENV PYTHONPATH=/app
```

### 3. Mejora en report.py

Se implementó un sistema de respaldo que intenta `PackageLoader` primero y luego `FileSystemLoader`:

```python
try:
    # Intentar con PackageLoader primero (recomendado)
    env = Environment(loader=PackageLoader('pentest', 'templates'))
except (ImportError, ModuleNotFoundError):
    # Respaldo con FileSystemLoader para entornos de producción
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir))
```

## Archivos Modificados

- `.dockerignore` - Incluye explícitamente archivos del paquete pentest
- `Dockerfile` - Instala el paquete pentest con `pip install -e .`
- `pentest/report.py` - Sistema de respaldo para carga de plantillas

## Archivos de Test Creados

- `test_template_fix.py` - Test básico de carga de plantillas
- `test_production_template.py` - Simulación del entorno de producción
- `verify_package_install.py` - Verificación de instalación del paquete

## Instrucciones para Despliegue

### 1. Reconstruir la Imagen Docker

```bash
# Detener contenedores existentes
docker-compose down

# Reconstruir la imagen
docker-compose build --no-cache

# Iniciar los servicios
docker-compose up -d
```

### 2. Verificar la Solución

```bash
# Ejecutar tests localmente
python test_template_fix.py
python test_production_template.py
python verify_package_install.py

# Verificar logs del contenedor
docker-compose logs scan-runner
```

## Verificación de la Solución

✅ **Test Local**: `test_template_fix.py` - EXITOSO  
✅ **Test Producción**: `test_production_template.py` - EXITOSO  
✅ **Verificación Paquete**: `verify_package_install.py` - EXITOSO  

## Beneficios de la Solución

1. **Robustez**: Sistema de respaldo que funciona en cualquier entorno
2. **Compatibilidad**: Mantiene la funcionalidad tanto en desarrollo como en producción
3. **Mantenibilidad**: El paquete se instala correctamente con todas sus dependencias
4. **Escalabilidad**: La solución es compatible con futuras actualizaciones

## Notas Técnicas

- El `PackageLoader` es la opción preferida cuando el paquete está correctamente instalado
- El `FileSystemLoader` actúa como respaldo para casos edge
- El `setup.py` ya estaba correctamente configurado con `include_package_data=True`
- El `MANIFEST.in` incluye correctamente los archivos de plantillas

---

**Estado**: ✅ SOLUCIONADO  
**Fecha**: $(date)  
**Versión**: 1.0.0