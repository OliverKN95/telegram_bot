# Web Scraper Telegram Bot

Bot de Telegram que monitorea el Diario Oficial de Yucatán, busca texto específico en los PDFs publicados y envía notificaciones automáticamente.

## Características

- 🕷️ Web scraping automático del sitio oficial de Yucatán
- 📄 Procesamiento de PDFs en memoria
- 🔍 Búsqueda de texto específico (configurable)
- 📱 Notificaciones vía Telegram
- 📎 **Envío automático de PDFs cuando se encuentra el texto buscado**
- 📤 **Endpoint para envío manual de PDFs**
- ⏰ Ejecución programada diaria (horarios configurables)
- 🔧 Configuración completa via archivos .env
- 🐳 Dockerizado para fácil despliegue
- 🌍 Soporte para múltiples zonas horarias
- 🚀 **API FastAPI con endpoints de control**

## Tecnologías utilizadas

- Python 3.12
- BeautifulSoup4 para web scraping
- PyPDF para procesamiento de PDFs
- Requests para llamadas HTTP
- python-dotenv para manejo de configuración
- PyTZ para manejo de zonas horarias
- Docker para conteneirización

## Configuración Inicial

### 1. Configurar variables de entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar con tus valores
nano .env
```

### 2. Configurar credenciales de Telegram

1. Crea un bot con @BotFather en Telegram
2. Obtén tu token del bot
3. Obtén tu chat ID (puedes usar @userinfobot)
4. Actualiza las variables en `.env`:

```env
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui
```

### 3. Probar configuración

```bash
python test_config.py
```

## Despliegue

### Local con Python

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python telegram_bot.py
```

### Local con Docker

```bash
# Construir la imagen
docker build -t telegram-bot .

# Ejecutar el contenedor con variables de entorno
docker run -d --name telegram-bot --env-file .env telegram-bot
```

### Render.com

Este proyecto está configurado para desplegarse automáticamente en Render.com usando Docker.

1. Conecta tu repositorio a Render.com
2. Selecciona "Web Service"
3. Configura las variables de entorno en el dashboard de Render
4. El despliegue será automático

## Configuración Avanzada

Consulta `CONFIG.md` para una descripción completa de todas las variables de entorno disponibles.

### Variables principales:

- `TELEGRAM_BOT_TOKEN`: Token del bot
- `TELEGRAM_CHAT_ID`: ID del chat
- `SEARCH_TEXT`: Texto a buscar en PDFs
- `SEND_PDF_WHEN_FOUND`: Enviar PDF automáticamente cuando se encuentra el texto (true/false)
- `TIMEZONE`: Zona horaria (ej: America/Merida)
- `SCHEDULE_HOUR_1/SCHEDULE_MINUTE_1`: Primer horario de ejecución
- `SCHEDULE_HOUR_2/SCHEDULE_MINUTE_2`: Segundo horario de ejecución

## Funcionalidad

El bot ejecuta las siguientes acciones diariamente:

1. Accede al sitio web del Diario Oficial de Yucatán
2. Busca el PDF más reciente
3. Descarga y procesa el PDF en memoria
4. Busca el texto específico configurado
5. Envía un reporte vía Telegram con los resultados
6. **Si encuentra el texto y está habilitado, envía automáticamente el PDF al chat**

### API Endpoints

El bot también expone los siguientes endpoints HTTP:

- `GET /health` - Health check del servicio
- `GET /status` - Estado actual del servicio y configuración
- `POST /run-report` - Ejecuta manualmente el reporte
- `POST /send-pdf` - **Descarga y envía manualmente el PDF del día**

### Control del envío de PDFs

- **Automático**: Configura `SEND_PDF_WHEN_FOUND=true` para enviar PDFs automáticamente cuando se encuentra el texto
- **Manual**: Usa el endpoint `POST /send-pdf` para enviar el PDF bajo demanda
- **Deshabilitado**: Configura `SEND_PDF_WHEN_FOUND=false` para solo recibir notificaciones de texto

## Estructura del Proyecto

```
.
├── Dockerfile              # Configuración de Docker
├── .dockerignore          # Archivos ignorados por Docker
├── pyproject.toml         # Configuración de dependencias
├── telegram_bot.py        # Código principal del bot
└── README.md             # Este archivo
```
