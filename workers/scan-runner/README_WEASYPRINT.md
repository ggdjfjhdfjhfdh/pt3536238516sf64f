# Guía de Solución de Problemas para WeasyPrint

Este documento proporciona información sobre cómo diagnosticar y resolver problemas comunes con WeasyPrint en el proceso de generación de informes PDF.

## Pruebas de Diagnóstico

Se han incluido dos scripts de prueba para ayudar a diagnosticar problemas con WeasyPrint:

### 1. Test Básico de WeasyPrint

Este script verifica la instalación básica de WeasyPrint y sus dependencias:

```bash
python test_weasyprint.py
```

Este test intentará:
- Importar WeasyPrint
- Generar un PDF simple
- Verificar las dependencias del sistema

### 2. Prueba de Integración de Generación de PDF

Este script prueba el proceso completo de generación de PDF, incluyendo los mecanismos de fallback:

```bash
python test_pdf_generation.py
```

Este test intentará:
- Generar un informe HTML de prueba
- Convertir el HTML a PDF usando WeasyPrint
- Probar el mecanismo de fallback con ReportLab si WeasyPrint falla

## Dependencias de Sistema para WeasyPrint

WeasyPrint requiere varias bibliotecas del sistema para funcionar correctamente. En entornos Debian/Ubuntu, estas son:

```bash
apt-get update && apt-get install -y \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    libfontconfig1 \
    libcairo2
```

En el Dockerfile, estas dependencias ya están incluidas.

## Problemas Comunes y Soluciones

### Error: `libgobject-2.0.so.0: cannot open shared object file`

**Solución**: Instalar `libglib2.0-0` que proporciona este archivo:

```bash
apt-get install -y libglib2.0-0
```

### Error: `CryptographyDeprecationWarning: Certificate.not_valid_before and Certificate.not_valid_after`

**Solución**: Este problema ha sido corregido en el código. Se han actualizado las propiedades obsoletas a `not_valid_before_utc` y `not_valid_after_utc` con fallback a las propiedades antiguas para compatibilidad.

### Error: `InsecureRequestWarning: Unverified HTTPS request is being made`

**Solución**: Este problema ha sido corregido en el código. Se ha añadido la supresión de advertencias para las llamadas específicas que lo requieren y se ha habilitado la verificación de certificados en las llamadas a la API de MailerSend.

## Mecanismos de Fallback

El sistema incluye varios mecanismos de fallback en caso de que WeasyPrint falle:

1. **Fallback a ReportLab**: Si WeasyPrint no puede generar el PDF, el sistema intentará usar ReportLab para crear un PDF básico.

2. **Fallback a Archivo de Texto**: Si tanto WeasyPrint como ReportLab fallan, el sistema generará un informe en formato de texto plano.

3. **Fallback en Notificaciones**: Si el PDF no se puede generar o es demasiado grande, el sistema enviará un correo electrónico con un resumen básico sin adjunto.

## Recomendaciones para Desarrollo

1. **Pruebas Locales**: Ejecutar los scripts de prueba en el entorno de desarrollo local antes de hacer cambios en el código relacionado con la generación de PDF.

2. **Pruebas en Docker**: Probar la generación de PDF dentro del contenedor Docker para asegurarse de que todas las dependencias estén correctamente instaladas.

3. **Logs Detallados**: En caso de problemas, habilitar logs detallados añadiendo `debug=True` en las llamadas a WeasyPrint.

## Recursos Adicionales

- [Documentación oficial de WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/)
- [Guía de instalación de WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)
- [Solución de problemas de WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting)