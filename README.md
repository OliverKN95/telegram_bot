# Web Scraper Telegram Bot

Bot de Telegram que monitorea el Diario Oficial de Yucatán, busca texto específico en los PDFs publicados y envía notificaciones automáticamente.

## Características

- 🕷️ Web scraping automático del sitio oficial de Yucatán
- 📄 Procesamiento de PDFs en memoria
- 🔍 Búsqueda de texto específico ("koyoc novelo")
- 📱 Notificaciones vía Telegram
- ⏰ Ejecución programada diaria a las 7:30 AM
- 🐳 Dockerizado para fácil despliegue

## Tecnologías utilizadas

- Python 3.12
- BeautifulSoup4 para web scraping
- PyPDF para procesamiento de PDFs
- Requests para llamadas HTTP
- Schedule para tareas programadas
- Docker para conteneirización

## Despliegue

### Local con Docker

```bash
# Construir la imagen
docker build -t telegram-bot .

# Ejecutar el contenedor
docker run -d --name telegram-bot telegram-bot
```

### Render.com

Este proyecto está configurado para desplegarse automáticamente en Render.com usando Docker.

1. Conecta tu repositorio a Render.com
2. Selecciona "Web Service"
3. Configura:
   - Build Command: `docker build -t telegram-bot .`
   - Start Command: `docker run telegram-bot`

## Configuración

El bot utiliza credenciales de Telegram hardcodeadas. Para producción, se recomienda usar variables de entorno.

## Funcionalidad

El bot ejecuta las siguientes acciones diariamente:

1. Accede al sitio web del Diario Oficial de Yucatán
2. Busca el PDF más reciente
3. Descarga y procesa el PDF en memoria
4. Busca el texto específico configurado
5. Envía un reporte vía Telegram con los resultados

## Estructura del Proyecto

```
.
├── Dockerfile              # Configuración de Docker
├── .dockerignore          # Archivos ignorados por Docker
├── pyproject.toml         # Configuración de dependencias
├── telegram_bot.py        # Código principal del bot
└── README.md             # Este archivo
```
