# Configuración del Bot de Telegram Web Scraper

Este proyecto utiliza archivos `.env` para manejar la configuración. A continuación se describen todas las variables de entorno disponibles:

## Variables de Entorno

### Configuración del Bot de Telegram (Requeridas)
- `TELEGRAM_BOT_TOKEN`: Token del bot de Telegram obtenido de @BotFather
- `TELEGRAM_CHAT_ID`: ID del chat donde se enviarán los mensajes

### Configuración del Servidor
- `PORT`: Puerto en el que se ejecutará el servidor de salud (default: 8000)

### Configuración de Búsqueda
- `SEARCH_TEXT`: Texto a buscar en los PDFs (default: "koyoc novelo")
- `SEND_PDF_WHEN_FOUND`: Si debe enviar el PDF automáticamente cuando se encuentra el texto (default: true)

### URLs del Sitio Web
- `BASE_URL`: URL base del sitio web (default: "https://www.yucatan.gob.mx")
- `DIARIO_URL_PATH`: Ruta del diario oficial (default: "/gobierno/diario_oficial.php")

### Configuración de Zona Horaria
- `TIMEZONE`: Zona horaria para la ejecución (default: "America/Merida")

### Horarios de Ejecución Programada
- `SCHEDULE_HOUR_1`: Hora del primer reporte diario (formato 24h, default: 7)
- `SCHEDULE_MINUTE_1`: Minuto del primer reporte diario (default: 30)
- `SCHEDULE_HOUR_2`: Hora del segundo reporte diario (formato 24h, default: 12)
- `SCHEDULE_MINUTE_2`: Minuto del segundo reporte diario (default: 0)

## Configuración Inicial

1. Copia el archivo `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edita el archivo `.env` con tus valores específicos:
   ```bash
   nano .env
   ```

3. Asegúrate de que el archivo `.env` esté en tu `.gitignore` para no compartir credenciales.

## Seguridad

- **Nunca** subas el archivo `.env` a tu repositorio
- El archivo `.env.example` sirve como template y no contiene valores reales
- Usa variables de entorno del sistema en producción cuando sea posible
