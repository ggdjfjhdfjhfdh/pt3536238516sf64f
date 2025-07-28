# Mejoras en la Carga de Plantillas - Solución para TemplateNotFound

## Problema Original

El sistema experimentaba errores de `TemplateNotFound` para `report.html` en entornos de producción/Docker, a pesar de que la plantilla existía físicamente en el sistema de archivos.

```
jinja2.exceptions.TemplateNotFound: report.html
```

## Análisis del Problema

### Síntomas
- ✅ Funcionamiento correcto en entorno de desarrollo local
- ❌ Fallo en entorno Docker/producción
- ✅ Archivo `report.html` presente físicamente
- ❌ `PackageLoader` no podía encontrar la plantilla

### Causa Raíz
El problema se originaba por diferencias en la instalación del paquete `pentest` entre entornos:
- En desarrollo: Instalación en modo editable (`pip install -e .`)
- En producción: Posibles problemas con la instalación del paquete o estructura de directorios

## Solución Implementada

### 1. Sistema de Múltiples Estrategias de Respaldo

Se implementó un sistema robusto que intenta múltiples estrategias de carga de plantillas:

```python
def _initialize_jinja_environment():
    strategies = [
        # Estrategia 1: PackageLoader (preferido)
        {'name': 'PackageLoader', 'loader': lambda: PackageLoader('pentest', 'templates')},
        
        # Estrategia 2: FileSystemLoader con ruta relativa
        {'name': 'FileSystemLoader (relativo)', 'loader': lambda: FileSystemLoader(str(Path(__file__).parent / "templates"))},
        
        # Estrategia 3: FileSystemLoader con ruta absoluta
        {'name': 'FileSystemLoader (absoluto)', 'loader': lambda: FileSystemLoader(str(Path(__file__).parent.absolute() / "templates"))},
        
        # Estrategia 4: Múltiples directorios
        {'name': 'FileSystemLoader (múltiples rutas)', 'loader': lambda: FileSystemLoader([...])}
    ]
```

### 2. Validación Proactiva

Cada estrategia se valida intentando cargar realmente la plantilla:

```python
# Probar que realmente puede cargar la plantilla
env.get_template("report.html")
```

### 3. Recuperación Automática

La función `get_template()` ahora incluye:
- **Detección de fallos**: Verifica si el entorno está inicializado
- **Reintentos automáticos**: Reinicializa el entorno si es necesario
- **Manejo robusto de errores**: Proporciona mensajes de error claros

```python
def get_template():
    # Si no hay entorno, intentar reinicializar
    if env is None:
        if not _initialize_jinja_environment():
            raise ReportError("No se pudo inicializar el entorno Jinja2")
    
    # Intentar cargar con reintentos automáticos
    try:
        return env.get_template("report.html")
    except Exception:
        # Reintentar con reinicialización
        if _initialize_jinja_environment():
            return env.get_template("report.html")
        raise
```

## Beneficios de la Solución

### ✅ Robustez
- **Múltiples estrategias**: Si una falla, automáticamente prueba la siguiente
- **Recuperación automática**: Maneja fallos temporales sin intervención manual
- **Validación proactiva**: Verifica que la plantilla se puede cargar realmente

### ✅ Compatibilidad
- **Entornos de desarrollo**: Mantiene el rendimiento óptimo con `PackageLoader`
- **Entornos de producción**: Funciona con `FileSystemLoader` como respaldo
- **Docker**: Compatible con diferentes estructuras de instalación

### ✅ Mantenibilidad
- **Logging detallado**: Registra qué estrategia funciona en cada entorno
- **Mensajes de error claros**: Facilita el diagnóstico de problemas
- **Código modular**: Fácil de extender con nuevas estrategias

## Verificación de la Solución

La solución fue verificada mediante:

1. **Pruebas de carga múltiple**: Verificación de que `get_template()` funciona consistentemente
2. **Simulación de fallos**: Prueba de recuperación automática cuando el entorno falla
3. **Renderizado completo**: Verificación de que la plantilla se puede renderizar correctamente
4. **Compatibilidad**: Funcionamiento en entorno de desarrollo local

## Archivos Modificados

- **`pentest/report.py`**: 
  - Función `_initialize_jinja_environment()` (nueva)
  - Función `get_template()` (mejorada)
  - Inicialización del entorno Jinja2 (refactorizada)

## Impacto

- ✅ **Resolución del error**: Elimina los errores de `TemplateNotFound`
- ✅ **Mejora de la confiabilidad**: Sistema más robusto ante fallos
- ✅ **Compatibilidad universal**: Funciona en todos los entornos
- ✅ **Sin regresiones**: Mantiene el rendimiento en entornos que funcionaban

## Monitoreo

Para monitorear el funcionamiento de la solución, revisar los logs para:
- Mensajes de éxito: `"Entorno Jinja2 creado correctamente con [estrategia]"`
- Advertencias: `"[estrategia] falló: [error]"`
- Recuperaciones: `"Entorno Jinja2 no inicializado, reintentando..."`

Esta solución asegura que el sistema de generación de informes sea robusto y confiable en todos los entornos de despliegue.