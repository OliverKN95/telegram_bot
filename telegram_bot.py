from bs4 import BeautifulSoup
import requests
import time
import threading
import os
from datetime import datetime
import pytz
from urllib.parse import urljoin
from pypdf import PdfReader
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

# Cargar variables de entorno
load_dotenv()

# Crear aplicación FastAPI
app = FastAPI(
    title="Web Scraper Telegram Bot",
    description="API para el bot de Telegram que hace scraping del diario oficial",
    version="1.0.0"
)


def bot_send_text(bot_message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    bot_chatID = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not bot_chatID:
        raise ValueError("TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID deben estar configurados en el archivo .env")
    
    send_text = (
        "https://api.telegram.org/bot"
        + bot_token
        + "/sendMessage?chat_id="
        + bot_chatID
        + "&parse_mode=Markdown&text="
        + bot_message
    )

    response = requests.get(send_text)

    return response.json()


def bot_send_document(pdf_content, filename, caption=""):
    """
    Envía un documento PDF al chat de Telegram
    
    Args:
        pdf_content: El contenido del PDF en bytes
        filename: Nombre del archivo PDF
        caption: Descripción opcional del documento
    
    Returns:
        dict: Respuesta de la API de Telegram
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    bot_chatID = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not bot_chatID:
        raise ValueError("TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID deben estar configurados en el archivo .env")
    
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    
    files = {
        'document': (filename, pdf_content, 'application/pdf')
    }
    
    data = {
        'chat_id': bot_chatID,
        'caption': caption
    }
    
    response = requests.post(url, files=files, data=data)
    
    return response.json()


def download_pdf(pdf_link, base_url, filename=None):
    """
    Descarga un PDF, lo lee en memoria y busca texto específico

    Args:
        pdf_link: El enlace del PDF (puede ser relativo o absoluto)
        base_url: La URL base del sitio web
        filename: Nombre del archivo (opcional, solo para logging)

    Returns:
        dict: Información del PDF incluyendo páginas totales y resultados de búsqueda, o None si hay error
    """
    try:
        # Si el enlace es relativo, convertirlo a absoluto
        if pdf_link.startswith("/") or not pdf_link.startswith("http"):
            full_url = urljoin(base_url, pdf_link)
        else:
            full_url = pdf_link

        # Descargar el PDF
        response = requests.get(full_url)
        response.raise_for_status()  # Lanza excepción si hay error HTTP

        # Generar nombre del archivo si no se proporciona
        if not filename:
            filename = pdf_link.split("/")[-1]
            if not filename.endswith(".pdf"):
                filename += ".pdf"

        # Leer el PDF directamente desde memoria
        from io import BytesIO

        pdf_stream = BytesIO(response.content)
        reader = PdfReader(pdf_stream)
        total_pages = len(reader.pages)

        # Buscar texto en el contenido del PDF
        search_text = os.getenv("SEARCH_TEXT", "koyoc novelo")
        found_pages = []
        full_text = ""

        for page_num, page in enumerate(reader.pages, 1):
            try:
                page_text = page.extract_text().lower()
                full_text += page_text + "\n"

                if search_text.lower() in page_text:
                    found_pages.append(page_num)
                    print(f"'{search_text}' encontrado en la página {page_num}")
            except Exception as e:
                print(f"Error extrayendo texto de la página {page_num}: {e}")

        result = {
            "total_pages": total_pages,
            "search_text": search_text,
            "found_pages": found_pages,
            "found": len(found_pages) > 0,
            "pdf_content": response.content,
            "filename": filename
        }

        print(f"PDF leído en memoria - Total de páginas: {total_pages}")
        if found_pages:
            return (
                result,
                f"Texto '{search_text}' encontrado en {len(found_pages)} página(s): {found_pages}",
            )

        return (result, f"Texto '{search_text}' NO encontrado en el PDF")

    except Exception as e:
        print(f"Error descargando PDF: {e}")
        return None


def diario_scraping():
    base_url = os.getenv("BASE_URL", "https://www.yucatan.gob.mx")
    diario_path = os.getenv("DIARIO_URL_PATH", "/gobierno/diario_oficial.php")
    url = requests.get(f"{base_url}{diario_path}")
    # url = requests.get(f'{base_url}{diario_path}?f=2025-10-9')

    soup = BeautifulSoup(url.content, "html.parser")
    fecha_consulta_pagina = soup.find("div", {"class": "titulo verde mt-2"}).text
    # Usar zona horaria configurada
    timezone = os.getenv("TIMEZONE", "America/Merida")
    merida_tz = pytz.timezone(timezone)
    date_now = datetime.now(merida_tz).strftime("%d/%m/%Y %H:%M:%S %Z")

    # Buscar el enlace del PDF
    pdf_element = soup.find("a", {"class": "pdf"})

    if pdf_element:
        pdf_link = pdf_element.get("href")
        print(f"Enlace del PDF encontrado: {pdf_link}")

        # Generar nombre del archivo con fecha en zona horaria configurada
        timezone = os.getenv("TIMEZONE", "America/Merida")
        tz = pytz.timezone(timezone)
        current_date = datetime.now(tz).strftime("%Y-%m-%d")
        filename = f"diario_oficial_{current_date}.pdf"

        # Leer el PDF y buscar texto
        pdf_result, message = download_pdf(pdf_link, base_url, filename)

        if pdf_result:
            total_pages = pdf_result["total_pages"]
            search_text = pdf_result["search_text"]
            found_pages = pdf_result["found_pages"]

            if pdf_result["found"]:
                timezone_name = os.getenv("TIMEZONE", "America/Merida").split("/")[-1]
                format_result = (
                    f"✅ {fecha_consulta_pagina} - Hora de ejecución ({timezone_name}): {date_now} - PDF procesado: {filename} - Total páginas: {total_pages} - '{search_text}' encontrado en páginas: {found_pages}"
                    + " - "
                    + message
                )
                return format_result, pdf_result  # Devolver también la información del PDF
            else:
                timezone_name = os.getenv("TIMEZONE", "America/Merida").split("/")[-1]
                format_result = (
                    f"❌ {fecha_consulta_pagina} - Hora de ejecución ({timezone_name}): {date_now} - PDF procesado: {filename} - Total páginas: {total_pages} - '{search_text}' NO encontrado"
                    + " - "
                    + message
                )
        else:
            timezone_name = os.getenv("TIMEZONE", "America/Merida").split("/")[-1]
            format_result = f"‼️ {fecha_consulta_pagina} - Hora de ejecución ({timezone_name}): {date_now} - Error procesando PDF"
    else:
        print("No se encontró enlace de PDF con clase 'pdf'")
        timezone_name = os.getenv("TIMEZONE", "America/Merida").split("/")[-1]
        format_result = f"⚠️ {fecha_consulta_pagina} - Hora de ejecución ({timezone_name}): {date_now} - No PDF encontrado"

    return format_result, None  # Devolver None cuando no hay PDF para enviar


def report():
    """Ejecuta el reporte de scraping y envía el resultado al bot de Telegram"""
    result, pdf_data = diario_scraping()
    print(result)
    
    # Envía el resultado al bot de Telegram
    bot_send_text(result)
    
    # Verificar si se debe enviar el PDF automáticamente
    send_pdf = os.getenv("SEND_PDF_WHEN_FOUND", "true").lower() == "true"
    
    # Si se encontró el texto, hay datos del PDF y está habilitado el envío automático
    if pdf_data and pdf_data["found"] and send_pdf:
        try:
            caption = f"📄 PDF del Diario Oficial - Texto '{pdf_data['search_text']}' encontrado en páginas: {pdf_data['found_pages']}"
            bot_send_document(
                pdf_content=pdf_data["pdf_content"],
                filename=pdf_data["filename"],
                caption=caption
            )
            print(f"PDF enviado exitosamente: {pdf_data['filename']}")
        except Exception as e:
            print(f"Error enviando PDF: {e}")
            bot_send_text(f"⚠️ Error enviando PDF: {str(e)}")
    elif pdf_data and pdf_data["found"] and not send_pdf:
        print(f"Texto encontrado pero envío de PDF deshabilitado. Archivo: {pdf_data['filename']}")


# Endpoints de FastAPI
@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {"status": "healthy", "service": "telegram-bot"}


@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "message": "Web Scraper Telegram Bot API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "run_report": "/run-report",
            "send_pdf": "/send-pdf",
            "status": "/status"
        }
    }


@app.post("/run-report")
async def run_report_endpoint():
    """Ejecuta manualmente el reporte de scraping"""
    try:
        result, pdf_data = diario_scraping()
        bot_send_text(result)
        
        # Si se encontró el texto y hay datos del PDF, enviar el PDF también
        if pdf_data and pdf_data["found"]:
            try:
                caption = f"📄 PDF del Diario Oficial - Texto '{pdf_data['search_text']}' encontrado en páginas: {pdf_data['found_pages']}"
                bot_send_document(
                    pdf_content=pdf_data["pdf_content"],
                    filename=pdf_data["filename"],
                    caption=caption
                )
                return {
                    "status": "success",
                    "message": "Reporte ejecutado exitosamente y PDF enviado",
                    "result": result,
                    "pdf_sent": True,
                    "pdf_filename": pdf_data["filename"]
                }
            except Exception as e:
                bot_send_text(f"⚠️ Error enviando PDF: {str(e)}")
                return {
                    "status": "partial_success",
                    "message": "Reporte ejecutado pero error enviando PDF",
                    "result": result,
                    "pdf_error": str(e)
                }
        else:
            return {
                "status": "success",
                "message": "Reporte ejecutado exitosamente",
                "result": result,
                "pdf_sent": False
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error ejecutando reporte: {str(e)}"
        }


@app.post("/send-pdf")
async def send_pdf_endpoint():
    """Descarga y envía manualmente el PDF del día al chat de Telegram"""
    try:
        result, pdf_data = diario_scraping()
        
        if pdf_data and pdf_data.get("pdf_content"):
            try:
                # Determinar el caption basado en si se encontró el texto o no
                if pdf_data["found"]:
                    caption = f"📄 PDF del Diario Oficial - Texto '{pdf_data['search_text']}' encontrado en páginas: {pdf_data['found_pages']}"
                else:
                    caption = f"📄 PDF del Diario Oficial - Envío manual (Texto '{pdf_data['search_text']}' no encontrado)"
                
                bot_send_document(
                    pdf_content=pdf_data["pdf_content"],
                    filename=pdf_data["filename"],
                    caption=caption
                )
                return {
                    "status": "success",
                    "message": "PDF enviado exitosamente",
                    "filename": pdf_data["filename"],
                    "text_found": pdf_data["found"],
                    "found_pages": pdf_data.get("found_pages", [])
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error enviando PDF: {str(e)}"
                }
        else:
            return {
                "status": "error",
                "message": "No se pudo obtener el PDF del sitio web"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error procesando solicitud: {str(e)}"
        }


@app.get("/status")
async def get_status():
    """Obtiene el estado actual del servicio"""
    timezone = os.getenv("TIMEZONE", "America/Merida")
    tz = pytz.timezone(timezone)
    current_time = datetime.now(tz)
    
    return {
        "status": "running",
        "current_time": current_time.isoformat(),
        "timezone": timezone,
        "schedules": {
            "schedule_1": f"{os.getenv('SCHEDULE_HOUR_1', '7')}:{os.getenv('SCHEDULE_MINUTE_1', '30')}",
            "schedule_2": f"{os.getenv('SCHEDULE_HOUR_2', '12')}:{os.getenv('SCHEDULE_MINUTE_2', '0')}"
        }
    }


def should_run_at_merida_time(target_hour, target_minute):
    """Verifica si es hora de ejecutar según la zona horaria de Mérida"""
    merida_tz = pytz.timezone("America/Merida")
    now_merida = datetime.now(merida_tz)
    return now_merida.hour == target_hour and now_merida.minute == target_minute


def run_scheduler():
    """Ejecuta el scheduler en un hilo separado usando zona horaria configurada"""
    last_run_schedule_1 = None
    last_run_schedule_2 = None
    
    # Obtener configuración de horarios desde variables de entorno
    schedule_hour_1 = int(os.getenv("SCHEDULE_HOUR_1", "7"))
    schedule_minute_1 = int(os.getenv("SCHEDULE_MINUTE_1", "30"))
    schedule_hour_2 = int(os.getenv("SCHEDULE_HOUR_2", "12"))
    schedule_minute_2 = int(os.getenv("SCHEDULE_MINUTE_2", "0"))
    timezone = os.getenv("TIMEZONE", "America/Merida")

    while True:
        tz = pytz.timezone(timezone)
        now_tz = datetime.now(tz)
        current_date = now_tz.strftime("%Y-%m-%d")

        # Verificar primer horario configurado
        if (
            now_tz.hour == schedule_hour_1
            and now_tz.minute == schedule_minute_1
            and last_run_schedule_1 != current_date
        ):
            timezone_name = timezone.split("/")[-1]
            print(f"Ejecutando reporte a las {schedule_hour_1:02d}:{schedule_minute_1:02d} hora de {timezone_name} ({now_tz})")
            report()
            last_run_schedule_1 = current_date

        # Verificar segundo horario configurado
        if (
            now_tz.hour == schedule_hour_2
            and now_tz.minute == schedule_minute_2
            and last_run_schedule_2 != current_date
        ):
            timezone_name = timezone.split("/")[-1]
            print(f"Ejecutando reporte a las {schedule_hour_2:02d}:{schedule_minute_2:02d} hora de {timezone_name} ({now_tz})")
            report()
            last_run_schedule_2 = current_date

        time.sleep(60)  # Verificar cada minuto


# Variable global para el hilo del scheduler
scheduler_thread = None


@app.on_event("startup")
async def startup_event():
    """Evento que se ejecuta al iniciar la aplicación FastAPI"""
    global scheduler_thread
    
    print("Ejecutando reporte al iniciar servicio FastAPI")
    report()
    
    # Iniciar el scheduler en un hilo separado
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("Scheduler iniciado en hilo separado")


if __name__ == "__main__":
    # Para testing local, descomenta la siguiente línea:
    # report()
    
    port = int(os.getenv("PORT", 8080))
    print(f"Iniciando servidor FastAPI en puerto {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
