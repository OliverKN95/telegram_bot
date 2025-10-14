# Guía de Despliegue en Render.com

## Pasos para desplegar el bot en Render.com

### 1. Preparación del repositorio

Asegúrate de que tu repositorio tenga todos estos archivos:
- `Dockerfile` - Configuración de Docker
- `telegram_bot.py` - Código principal del bot
- `pyproject.toml` - Dependencias del proyecto
- `start.sh` - Script de inicio
- `render.yaml` - Configuración de Render
- `.dockerignore` - Archivos ignorados por Docker

### 2. Crear cuenta en Render.com

1. Ve a [render.com](https://render.com)
2. Regístrate con tu cuenta de GitHub
3. Conecta tu repositorio

### 3. Configurar el servicio

1. Haz clic en "New +" → "Web Service"
2. Conecta tu repositorio de GitHub
3. Configura los siguientes ajustes:

**Configuración básica:**
- Name: `telegram-bot-scraper` (o el nombre que prefieras)
- Environment: `Docker`
- Plan: `Free` (para empezar)

**Configuración de Docker:**
- Dockerfile Path: `./Dockerfile`
- Docker Command: (dejar vacío, usa el CMD del Dockerfile)

**Configuración avanzada:**
- Health Check Path: `/health`
- Port: `8000`

### 4. Variables de entorno (opcional)

Si quieres hacer el bot más seguro, puedes configurar variables de entorno:

1. En la configuración del servicio, ve a "Environment"
2. Añade las siguientes variables:
   - `BOT_TOKEN` - Token de tu bot de Telegram
   - `CHAT_ID` - ID del chat donde enviar mensajes
   - `PORT` - 8000 (ya configurado automáticamente)

### 5. Desplegar

1. Haz clic en "Create Web Service"
2. Render automáticamente:
   - Clonará tu repositorio
   - Construirá la imagen Docker
   - Desplegará el servicio
   - Asignará una URL pública

### 6. Verificar el despliegue

Una vez desplegado:
- El bot se ejecutará automáticamente
- Puedes verificar el estado visitando: `https://tu-servicio.onrender.com/health`
- Los logs estarán disponibles en el dashboard de Render
- El bot enviará reportes diarios a las 7:30 AM (horario del servidor)

### 7. Monitoreo

- **Logs**: Ve a tu servicio → "Logs" para ver la actividad
- **Health Check**: Render verificará `/health` periódicamente
- **Restart**: Si hay problemas, puedes reiniciar desde el dashboard

### Notas importantes:

1. **Plan gratuito**: El servicio puede dormirse después de 15 minutos de inactividad
2. **Reinicio**: Los servicios gratuitos se reinician cada 24 horas
3. **Zona horaria**: Los servidores de Render usan UTC, ajusta el horario si es necesario
4. **Persistencia**: No hay almacenamiento persistente en el plan gratuito

### Troubleshooting

**Si el despliegue falla:**
1. Revisa los logs de construcción
2. Verifica que todos los archivos estén en el repositorio
3. Asegúrate de que el `Dockerfile` sea correcto

**Si el bot no envía mensajes:**
1. Verifica el token del bot de Telegram
2. Confirma que el chat_id sea correcto
3. Revisa los logs del servicio

**Si el health check falla:**
1. Verifica que el puerto 8000 esté expuesto
2. Confirma que el endpoint `/health` responda
3. Revisa la configuración del health check path
