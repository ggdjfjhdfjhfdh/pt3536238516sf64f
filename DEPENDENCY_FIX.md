# Resolución de Conflictos de Dependencias

## Problema Identificado

Se detectó un conflicto de dependencias durante el build de Docker:

```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
fastapi 0.104.1 requires anyio<4.0.0,>=3.7.1, but you have anyio 4.9.0 which is incompatible.
```

## Causa Raíz

El problema se originaba por:

1. **FastAPI 0.104.1** requería `anyio<4.0.0,>=3.7.1`
2. Otras dependencias instalaban **anyio 4.9.0**
3. Múltiples archivos `requirements.txt` con versiones no especificadas

## Solución Implementada

### 1. Actualización de Versiones

**requirements.txt principal:**
- FastAPI: `0.104.1` → `0.115.0` (compatible con anyio 4.x)
- Uvicorn: `0.24.0` → `0.32.0`
- Pydantic: `2.5.0` → `2.9.0`
- httpx: `==0.27.0` → `>=0.27.0,<1.0.0`
- Añadido: `anyio>=3.7.1,<5.0.0`

**services/api-fastapi/requirements.txt:**
- Especificación de rangos de versiones compatibles
- Añadido control explícito de anyio

### 2. Script de Resolución Automática

Creado `fix-dependencies.py` que:
- Actualiza pip a la última versión
- Instala anyio con versión compatible primero
- Reinstala dependencias críticas
- Verifica compatibilidad final

### 3. Dockerfiles Actualizados

Ambos Dockerfiles ahora:
1. Instalan anyio con versión compatible primero
2. Instalan requirements en orden específico
3. Ejecutan script de verificación
4. Validan compatibilidad final

## Verificación

Para verificar que la solución funciona:

```bash
# Build local
docker build -t pentest-api .

# Build scan-runner
docker build -f Dockerfile.scan-runner -t pentest-scanner .

# Verificar dependencias manualmente
python fix-dependencies.py
```

## Prevención Futura

1. **Siempre especificar rangos de versiones** en lugar de versiones exactas
2. **Probar builds localmente** antes de deploy
3. **Usar el script fix-dependencies.py** para validación
4. **Mantener FastAPI y dependencias actualizadas**

## Dependencias Críticas Monitoreadas

- `fastapi` ↔ `anyio`
- `uvicorn` ↔ `anyio`
- `httpx` ↔ `anyio`
- `pydantic` ↔ `fastapi`

Estas dependencias deben mantenerse sincronizadas para evitar conflictos futuros.