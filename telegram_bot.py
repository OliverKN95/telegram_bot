from bs4 import BeautifulSoup
import requests
import time
import threading
import os
from datetime import datetime
import pytz
from urllib.parse import urljoin
from pypdf import PdfReader
from http.server import HTTPServer, BaseHTTPRequestHandler


def bot_send_text(bot_message):
    bot_token = "8338579614:AAEIZXA9T5NrhBz7Jn37woiQ1oMuKGGawis"
    bot_chatID = "708040912"
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

        # Buscar texto "koyoc novelo" en el contenido del PDF
        search_text = "koyoc novelo"
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
    base_url = "https://www.yucatan.gob.mx"
    url = requests.get(f"{base_url}/gobierno/diario_oficial.php")
    # url = requests.get(f'{base_url}/gobierno/diario_oficial.php?f=2025-10-9')

    soup = BeautifulSoup(url.content, "html.parser")
    fecha_consulta_pagina = soup.find("div", {"class": "titulo verde mt-2"}).text
    # Usar zona horaria de Mérida, Yucatán, México
    merida_tz = pytz.timezone("America/Merida")
    date_now = datetime.now(merida_tz).strftime("%d/%m/%Y %H:%M:%S %Z")

    # Buscar el enlace del PDF
    pdf_element = soup.find("a", {"class": "pdf"})

    if pdf_element:
        pdf_link = pdf_element.get("href")
        print(f"Enlace del PDF encontrado: {pdf_link}")

        # Generar nombre del archivo con fecha en zona horaria de Mérida
        merida_tz = pytz.timezone("America/Merida")
        current_date = datetime.now(merida_tz).strftime("%Y-%m-%d")
        filename = f"diario_oficial_{current_date}.pdf"

        # Leer el PDF y buscar texto
        pdf_result, message = download_pdf(pdf_link, base_url, filename)

        if pdf_result:
            total_pages = pdf_result["total_pages"]
            search_text = pdf_result["search_text"]
            found_pages = pdf_result["found_pages"]

            if pdf_result["found"]:
                format_result = (
                    f"{fecha_consulta_pagina} - Hora de ejecución (Mérida, Yucatán): {date_now} - PDF procesado: {filename} - Total páginas: {total_pages} - '{search_text}' encontrado en páginas: {found_pages}"
                    + " - "
                    + message
                )
            else:
                format_result = (
                    f"{fecha_consulta_pagina} - Hora de ejecución (Mérida, Yucatán): {date_now} - PDF procesado: {filename} - Total páginas: {total_pages} - '{search_text}' NO encontrado"
                    + " - "
                    + message
                )
        else:
            format_result = f"{fecha_consulta_pagina} - Hora de ejecución (Mérida, Yucatán): {date_now} - Error procesando PDF"
    else:
        print("No se encontró enlace de PDF con clase 'pdf'")
        format_result = f"{fecha_consulta_pagina} - Hora de ejecución (Mérida, Yucatán): {date_now} - No PDF encontrado"

    return format_result


def report():
    result = diario_scraping()
    print(result)
    # Opcional: Envía el resultado al bot de Telegram
    bot_send_text(result)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "telegram-bot"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silenciar logs del servidor HTTP
        pass


def start_health_server():
    """Inicia un servidor HTTP simple para el endpoint de salud"""
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Servidor de salud iniciado en puerto {port}")
    server.serve_forever()


def should_run_at_merida_time(target_hour, target_minute):
    """Verifica si es hora de ejecutar según la zona horaria de Mérida"""
    merida_tz = pytz.timezone("America/Merida")
    now_merida = datetime.now(merida_tz)
    return now_merida.hour == target_hour and now_merida.minute == target_minute


def run_scheduler():
    """Ejecuta el scheduler en un hilo separado usando zona horaria de Mérida"""
    last_run_7_30 = None
    last_run_0_08 = None

    while True:
        merida_tz = pytz.timezone("America/Merida")
        now_merida = datetime.now(merida_tz)
        current_date = now_merida.strftime("%Y-%m-%d")

        # Verificar si es 07:30 en Mérida y no se ha ejecutado hoy
        if (
            now_merida.hour == 7
            and now_merida.minute == 30
            and last_run_7_30 != current_date
        ):
            print(f"Ejecutando reporte a las 07:30 hora de Mérida ({now_merida})")
            report()
            last_run_7_30 = current_date

        # Verificar si es 12:00 en Mérida y no se ha ejecutado hoy
        if (
            now_merida.hour == 12
            and now_merida.minute == 00
            and last_run_0_08 != current_date
        ):
            print(f"Ejecutando reporte a las 12:00 hora de Mérida ({now_merida})")
            report()
            last_run_0_08 = current_date

        time.sleep(60)  # Verificar cada minuto


if __name__ == "__main__":
    # Para testing local, descomenta la siguiente línea:
    # report()

    # Iniciar el scheduler en un hilo separado
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Iniciar el servidor de salud (esto bloquea el hilo principal)
    start_health_server()
