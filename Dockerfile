# Usar Python 3.12 slim como imagen base
FROM python:3.12-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para web scraping
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de configuración de Poetry
COPY pyproject.toml ./

# Instalar Poetry
RUN pip install poetry

# Configurar Poetry para no crear entorno virtual (ya estamos en Docker)
RUN poetry config virtualenvs.create false

# Instalar dependencias del proyecto
RUN poetry install --only=main --no-root

# Copiar el código de la aplicación
COPY telegram_bot.py ./
COPY start.sh ./

# Hacer el script ejecutable
RUN chmod +x start.sh

# Crear un usuario no-root para ejecutar la aplicación
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Variables de entorno por defecto (pueden ser sobrescritas en runtime)
ENV PORT=8000
ENV TIMEZONE=America/Merida
ENV BASE_URL=https://www.yucatan.gob.mx
ENV DIARIO_URL_PATH=/gobierno/diario_oficial.php
ENV SEARCH_TEXT="koyoc novelo"
ENV SCHEDULE_HOUR_1=7
ENV SCHEDULE_MINUTE_1=30
ENV SCHEDULE_HOUR_2=12
ENV SCHEDULE_MINUTE_2=0

# Exponer el puerto para el endpoint de salud
EXPOSE 8000

# Comando por defecto para ejecutar la aplicación
CMD ["./start.sh"]
