import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from io import BytesIO
from typing import Any
from urllib.parse import parse_qs, urljoin

import pytz
import requests
import uvicorn
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pypdf import PdfReader

# Cargar variables de entorno
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("telegram_bot")

# Crear aplicación FastAPI
app = FastAPI(
    title="Web Scraper Telegram Bot",
    description="API para el bot de Telegram con interfaz gráfica y corridas programadas",
    version="1.2.0",
)

security = HTTPBasic()
SESSION_COOKIE_NAME = "admin_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


def verify_basic_auth(credentials: HTTPBasicCredentials) -> bool:
    expected_user = os.getenv("ADMIN_USER", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "admin123")
    return (
        credentials.username == expected_user
        and credentials.password == expected_password
    )


def create_session_token(username: str) -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{username}:{expires_at}"
    secret = os.getenv("AUTH_SESSION_SECRET", os.getenv("ADMIN_PASSWORD", "admin123"))
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> bool:
    try:
        username, expires_at, signature = token.split(":", 2)
        if username != os.getenv("ADMIN_USER", "admin") or int(expires_at) < int(time.time()):
            return False
        payload = f"{username}:{expires_at}"
        secret = os.getenv("AUTH_SESSION_SECRET", os.getenv("ADMIN_PASSWORD", "admin123"))
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def get_db_path() -> str:
    return os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "schedules.db"))


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    try:
        conn = get_db_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                search_text TEXT,
                last_run_date TEXT,
                last_result TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER,
                schedule_name TEXT,
                executed_at TEXT NOT NULL,
                success INTEGER NOT NULL,
                message TEXT
            )
            """
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.exception("No se pudo inicializar la base de datos: %s", exc)
        raise


def create_schedule(name: str, hour: int, minute: int, enabled: bool = True, description: str = "", search_text: str = "") -> int:
    try:
        conn = get_db_connection()
        cursor = conn.execute(
            """
            INSERT INTO schedules (name, hour, minute, enabled, description, search_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, hour, minute, int(enabled), description, search_text),
        )
        conn.commit()
        schedule_id = cursor.lastrowid
        conn.close()
        return int(schedule_id)
    except Exception as exc:
        logger.exception("No se pudo crear la corrida: %s", exc)
        raise


def list_schedules(state: str | None = None) -> list[dict[str, Any]]:
    try:
        init_db()
        conn = get_db_connection()
        query = "SELECT id, name, hour, minute, enabled, description, search_text, last_run_date, last_result FROM schedules"
        params: list[Any] = []
        if state == "active":
            query += " WHERE enabled = 1"
        elif state == "disabled":
            query += " WHERE enabled = 0"
        query += " ORDER BY hour, minute, name"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.exception("No se pudo leer las corridas: %s", exc)
        return []


def export_schedules() -> list[dict[str, Any]]:
    return list_schedules()


def import_schedules(data: list[dict[str, Any]]) -> int:
    imported = 0
    for item in data:
        create_schedule(
            name=item.get("name", "Corrida importada"),
            hour=int(item.get("hour", 0)),
            minute=int(item.get("minute", 0)),
            enabled=bool(item.get("enabled", True)),
            description=item.get("description", ""),
            search_text=item.get("search_text", ""),
        )
        imported += 1
    return imported


def get_schedule(schedule_id: int) -> dict[str, Any] | None:
    try:
        init_db()
        conn = get_db_connection()
        row = conn.execute(
            "SELECT id, name, hour, minute, enabled, description, search_text, last_run_date, last_result FROM schedules WHERE id = ?",
            (schedule_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as exc:
        logger.exception("No se pudo consultar la corrida %s: %s", schedule_id, exc)
        return None


def update_schedule(schedule_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    try:
        init_db()
        if not updates:
            return get_schedule(schedule_id)

        valid_fields = {"name", "hour", "minute", "enabled", "description", "search_text", "last_run_date", "last_result"}
        unexpected = set(updates) - valid_fields
        if unexpected:
            raise ValueError(f"Campos no permitidos: {sorted(unexpected)}")

        assignments = []
        values: list[Any] = []
        for key, value in updates.items():
            if key == "enabled" and isinstance(value, bool):
                value = int(value)
            assignments.append(f"{key} = ?")
            values.append(value)
        values.append(schedule_id)

        conn = get_db_connection()
        conn.execute(f"UPDATE schedules SET {', '.join(assignments)} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return get_schedule(schedule_id)
    except Exception as exc:
        logger.exception("No se pudo actualizar la corrida %s: %s", schedule_id, exc)
        raise


def delete_schedule(schedule_id: int) -> bool:
    try:
        init_db()
        conn = get_db_connection()
        conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        logger.exception("No se pudo eliminar la corrida %s: %s", schedule_id, exc)
        raise


def log_run(schedule_id: int | None, schedule_name: str, success: bool, message: str) -> None:
    try:
        init_db()
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO run_logs (schedule_id, schedule_name, executed_at, success, message) VALUES (?, ?, ?, ?, ?)",
            (schedule_id, schedule_name, datetime.now().isoformat(), int(success), message),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.exception("No se pudo registrar el historial de ejecución: %s", exc)


def list_run_logs(limit: int = 20) -> list[dict[str, Any]]:
    try:
        init_db()
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT id, schedule_id, schedule_name, executed_at, success, message FROM run_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.exception("No se pudo leer el historial: %s", exc)
        return []


def bot_send_text(bot_message: str) -> dict[str, Any]:
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        bot_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not bot_token or not bot_chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID deben estar configurados en el archivo .env")

        send_text = (
            "https://api.telegram.org/bot"
            + bot_token
            + "/sendMessage?chat_id="
            + bot_chat_id
            + "&parse_mode=Markdown&text="
            + bot_message
        )

        response = requests.get(send_text, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.exception("No se pudo enviar el mensaje a Telegram: %s", exc)
        return {"ok": False, "error": str(exc)}


def bot_send_document(pdf_content: bytes, filename: str, caption: str = "") -> dict[str, Any]:
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        bot_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not bot_token or not bot_chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID deben estar configurados en el archivo .env")

        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        files = {"document": (filename, pdf_content, "application/pdf")}
        data = {"chat_id": bot_chat_id, "caption": caption}
        response = requests.post(url, files=files, data=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.exception("No se pudo enviar el PDF a Telegram: %s", exc)
        return {"ok": False, "error": str(exc)}


def download_pdf(pdf_link: str, base_url: str, filename: str | None = None, search_text: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    try:
        if pdf_link.startswith("/") or not pdf_link.startswith("http"):
            full_url = urljoin(base_url, pdf_link)
        else:
            full_url = pdf_link

        response = requests.get(full_url, timeout=30)
        response.raise_for_status()

        if not filename:
            filename = pdf_link.split("/")[-1]
            if not filename.endswith(".pdf"):
                filename += ".pdf"

        pdf_stream = BytesIO(response.content)
        reader = PdfReader(pdf_stream)
        total_pages = len(reader.pages)
        search_text_value = search_text or os.getenv("SEARCH_TEXT", "koyoc novelo")
        found_pages: list[int] = []

        for page_num, page in enumerate(reader.pages, 1):
            try:
                page_text = page.extract_text().lower()
                if search_text_value.lower() in page_text:
                    found_pages.append(page_num)
                logger.debug("Página %s revisada", page_num)
            except Exception as exc:
                logger.exception("Error extrayendo texto de la página %s: %s", page_num, exc)

        result = {
            "total_pages": total_pages,
            "search_text": search_text_value,
            "found_pages": found_pages,
            "found": len(found_pages) > 0,
            "pdf_content": response.content,
            "filename": filename,
        }
        if found_pages:
            return result, f"Texto '{search_text_value}' encontrado en {len(found_pages)} página(s): {found_pages}"
        return result, f"Texto '{search_text_value}' NO encontrado en el PDF"
    except Exception as exc:
        logger.exception("Error descargando PDF: %s", exc)
        return None, str(exc)


def diario_scraping(search_text: str | None = None) -> tuple[str, dict[str, Any] | None]:
    try:
        base_url = os.getenv("BASE_URL", "https://www.yucatan.gob.mx")
        diario_path = os.getenv("DIARIO_URL_PATH", "/gobierno/diario_oficial.php")
        url = f"{base_url}{diario_path}"
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        fecha_consulta_pagina = soup.find("div", {"class": "titulo verde mt-2"})
        fecha_consulta_text = fecha_consulta_pagina.text if fecha_consulta_pagina else "Diario Oficial"

        timezone = os.getenv("TIMEZONE", "America/Merida")
        merida_tz = pytz.timezone(timezone)
        date_now = datetime.now(merida_tz).strftime("%d/%m/%Y %H:%M:%S %Z")
        pdf_element = soup.find("a", {"class": "pdf"})

        if pdf_element:
            pdf_link = pdf_element.get("href")
            current_date = datetime.now(merida_tz).strftime("%Y-%m-%d")
            filename = f"diario_oficial_{current_date}.pdf"
            pdf_result, message = download_pdf(pdf_link, base_url, filename, search_text=search_text)

            if pdf_result:
                total_pages = pdf_result["total_pages"]
                search_text_value = pdf_result["search_text"]
                found_pages = pdf_result["found_pages"]
                timezone_name = timezone.split("/")[-1]
                if pdf_result["found"]:
                    format_result = (
                        f"✅ {fecha_consulta_text} - Hora de ejecución ({timezone_name}): {date_now} - PDF procesado: {filename} - Total páginas: {total_pages} - '{search_text_value}' encontrado en páginas: {found_pages} - {message}"
                    )
                    return format_result, pdf_result
                format_result = (
                    f"❌ {fecha_consulta_text} - Hora de ejecución ({timezone_name}): {date_now} - PDF procesado: {filename} - Total páginas: {total_pages} - '{search_text_value}' NO encontrado - {message}"
                )
                return format_result, pdf_result

            timezone_name = timezone.split("/")[-1]
            format_result = f"‼️ {fecha_consulta_text} - Hora de ejecución ({timezone_name}): {date_now} - Error procesando PDF"
            return format_result, None

        timezone_name = timezone.split("/")[-1]
        format_result = f"⚠️ {fecha_consulta_text} - Hora de ejecución ({timezone_name}): {date_now} - No PDF encontrado"
        return format_result, None
    except Exception as exc:
        logger.exception("Error general en diario_scraping: %s", exc)
        return f"⚠️ Error general de scraping: {exc}", None


def report(
    search_text: str | None = None,
    schedule_name: str | None = None,
    send_notifications: bool = True,
    send_pdf: bool | None = None,
) -> dict[str, Any]:
    try:
        result, pdf_data = diario_scraping(search_text=search_text)
        logger.info(result)

        send_pdf_enabled = send_pdf if send_pdf is not None else os.getenv("SEND_PDF_WHEN_FOUND", "true").lower() == "true"
        telegram_sent = False

        if send_notifications:
            send_text_response = bot_send_text(result)
            telegram_sent = bool(send_text_response.get("ok", True))
            if not send_text_response.get("ok", True):
                logger.warning("No se pudo notificar a Telegram: %s", send_text_response.get("error"))

        if pdf_data and pdf_data["found"] and send_pdf_enabled and send_notifications:
            caption = f"📄 PDF del Diario Oficial - Texto '{pdf_data['search_text']}' encontrado en páginas: {pdf_data['found_pages']}"
            pdf_response = bot_send_document(pdf_content=pdf_data["pdf_content"], filename=pdf_data["filename"], caption=caption)
            if pdf_response.get("ok", True):
                logger.info("PDF enviado exitosamente: %s", pdf_data["filename"])
            else:
                logger.warning("No se pudo enviar el PDF: %s", pdf_response.get("error"))
        elif pdf_data and pdf_data["found"] and not send_pdf_enabled:
            logger.info("Texto encontrado pero envío de PDF deshabilitado. Archivo: %s", pdf_data["filename"])

        return {
            "status": "success",
            "message": result,
            "schedule_name": schedule_name,
            "telegram_sent": telegram_sent,
            "pdf_sent": bool(pdf_data and pdf_data["found"] and send_pdf_enabled and send_notifications),
        }
    except Exception as exc:
        logger.exception("Error ejecutando el reporte: %s", exc)
        return {"status": "error", "message": str(exc), "schedule_name": schedule_name, "telegram_sent": False, "pdf_sent": False}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "telegram-bot"}


def auth_required(request: Request) -> None:
    if os.getenv("ENABLE_AUTH", "true").lower() != "true":
        return
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token and verify_session_token(session_token):
        return
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Autenticación requerida")
    try:
        scheme, encoded = auth_header.split(" ", 1)
        if scheme.lower() != "basic":
            raise ValueError
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        if not verify_basic_auth(HTTPBasicCredentials(username=username, password=password)):
            raise ValueError
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Credenciales inválidas") from exc


def render_login(error: bool = False) -> HTMLResponse:
    error_message = '<p class="error">Usuario o contraseña incorrectos.</p>' if error else ""
    return HTMLResponse(
        f"""<!doctype html>
        <html lang="es"><head>
            <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Iniciar sesión</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 24px; font-family: Arial, sans-serif; color: #172033; background: linear-gradient(135deg, #eff6ff, #f8fafc 55%, #e0e7ff); }}
                main {{ width: min(100%, 420px); padding: 36px; border: 1px solid #e2e8f0; border-radius: 20px; background: white; box-shadow: 0 24px 70px #0f172a1a; }}
                h1 {{ margin: 0 0 8px; font-size: 26px; }} p {{ color: #64748b; line-height: 1.5; }}
                form {{ display: grid; gap: 14px; margin-top: 24px; }}
                label {{ display: grid; gap: 7px; color: #334155; font-size: 14px; font-weight: 600; }}
                input, button {{ width: 100%; padding: 12px 14px; border: 1px solid #cbd5e1; border-radius: 10px; font: inherit; }}
                input:focus {{ outline: 3px solid #bfdbfe; border-color: #3b82f6; }}
                button {{ border: 0; color: white; background: #2563eb; font-weight: 700; cursor: pointer; }}
                button:hover {{ background: #1d4ed8; }} .error {{ margin: 0; padding: 10px 12px; border-radius: 8px; color: #b91c1c; background: #fef2f2; }}
            </style>
        </head><body><main>
            <h1>Iniciar sesión</h1><p>Ingresa tus credenciales de administrador para abrir el panel.</p>
            {error_message}
            <form method="post" action="/login">
                <label>Usuario<input name="username" autocomplete="username" required autofocus></label>
                <label>Contraseña<input name="password" type="password" autocomplete="current-password" required></label>
                <button type="submit">Entrar al panel</button>
            </form>
        </main></body></html>""",
        status_code=401 if error else 200,
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    try:
        auth_required(request)
        return RedirectResponse("/", status_code=303)
    except HTTPException:
        return render_login()


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request) -> Response:
    if os.getenv("ENABLE_AUTH", "true").lower() != "true":
        return RedirectResponse("/", status_code=303)
    form = parse_qs((await request.body()).decode("utf-8"))
    username = form.get("username", [""])[0]
    password = form.get("password", [""])[0]
    if not verify_basic_auth(HTTPBasicCredentials(username=username, password=password)):
        return render_login(error=True)

    response = RedirectResponse("/", status_code=303)
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(username),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=forwarded_proto == "https",
        samesite="lax",
        path="/",
    )
    return response


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> Response:
    try:
        auth_required(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    count = len(list_schedules())
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang=\"es\">
        <head>
            <meta charset=\"utf-8\">
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
            <title>Panel de corridas</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; background: #f3f5f9; color: #1f2937; }}
                main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
                .card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); margin-bottom: 20px; }}
                h1, h2 {{ margin-top: 0; }}
                form {{ display: grid; gap: 12px; }}
                input, textarea, button {{ padding: 10px; border-radius: 8px; border: 1px solid #d1d5db; font-size: 14px; }}
                button {{ cursor: pointer; background: #2563eb; color: white; border: none; }}
                button.secondary {{ background: #6b7280; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
                .schedule {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; margin-bottom: 10px; }}
                .muted {{ color: #6b7280; font-size: 13px; }}
                .actions button {{ margin-right: 6px; margin-top: 8px; }}
                .result {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 8px; margin-top: 10px; white-space: pre-wrap; }}
                .history-item {{ border-top: 1px solid #e5e7eb; padding: 8px 0; }}
                .toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }}
                .toolbar button {{ background: #111827; }}
                select {{ padding: 10px; border-radius: 8px; border: 1px solid #d1d5db; font-size: 14px; }}
            </style>
        </head>
        <body>
            <main>
                <section class=\"card\">
                    <h1>Panel de corridas</h1>
                    <p class=\"muted\">Configura varias ejecuciones diarias, guárdalas en SQLite y prueba el scraping sin enviar Telegram.</p>
                    <div class=\"grid\">
                        <div><strong>Corridas activas:</strong> {count}</div>
                        <div><strong>Zona horaria:</strong> {os.getenv('TIMEZONE', 'America/Merida')}</div>
                    </div>
                </section>

                <section class=\"card\">
                    <h2>Crear o editar corrida</h2>
                    <form id=\"schedule-form\">
                        <input id=\"schedule-id\" type=\"hidden\">
                        <input id=\"name\" placeholder=\"Nombre de la corrida\" required>
                        <div class=\"grid\">
                            <input id=\"hour\" type=\"number\" min=\"0\" max=\"23\" placeholder=\"Hora\" required>
                            <input id=\"minute\" type=\"number\" min=\"0\" max=\"59\" placeholder=\"Minuto\" required>
                        </div>
                        <textarea id=\"description\" placeholder=\"Descripción\"></textarea>
                        <input id=\"search_text\" placeholder=\"Texto a buscar (opcional)\">
                        <label><input id=\"enabled\" type=\"checkbox\" checked> Habilitada</label>
                        <button type=\"submit\" id=\"submit-button\">Guardar corrida</button>
                    </form>
                    <div id=\"result-box\" class=\"result\">Listo para crear o editar una corrida.</div>
                </section>

                <section class=\"card\">
                    <h2>Corridas programadas</h2>
                    <div class=\"toolbar\">
                        <select id=\"state-filter\">
                            <option value=\"all\">Todas</option>
                            <option value=\"active\">Activas</option>
                            <option value=\"disabled\">Desactivadas</option>
                        </select>
                        <button onclick=\"exportSchedules()\">Exportar JSON</button>
                        <button onclick=\"document.getElementById('import-file').click()\" class=\"secondary\">Importar JSON</button>
                        <input id=\"import-file\" type=\"file\" accept=\"application/json\" hidden>
                    </div>
                    <div id=\"schedule-list\">Cargando...</div>
                </section>

                <section class=\"card\">
                    <h2>Historial de ejecuciones</h2>
                    <div id=\"history-list\">Cargando...</div>
                </section>
            </main>

            <script>
                const list = document.getElementById('schedule-list');
                const historyList = document.getElementById('history-list');
                const form = document.getElementById('schedule-form');
                const resultBox = document.getElementById('result-box');
                const submitButton = document.getElementById('submit-button');
                const scheduleIdInput = document.getElementById('schedule-id');
                const stateFilter = document.getElementById('state-filter');
                const importFile = document.getElementById('import-file');

                function resetForm() {{
                    form.reset();
                    scheduleIdInput.value = '';
                    submitButton.textContent = 'Guardar corrida';
                    resultBox.textContent = 'Listo para crear o editar una corrida.';
                }}

                async function loadSchedules() {{
                    const state = stateFilter.value;
                    const response = await fetch(`/api/schedules${{state === 'all' ? '' : `?state=${{state}}`}}`);
                    const schedules = await response.json();
                    if (!schedules.length) {{
                        list.innerHTML = '<p class=\"muted\">Aún no hay corridas. Crea la primera.</p>'; 
                        return;
                    }}
                    list.innerHTML = schedules.map(schedule => `
                        <div class=\"schedule\">
                            <strong>${{schedule.name}}</strong>
                            <div class=\"muted\">${{String(schedule.hour).padStart(2, '0')}}:${{String(schedule.minute).padStart(2, '0')}} · ${{schedule.enabled ? 'Activa' : 'Desactivada'}}</div>
                            <div class=\"muted\">${{schedule.description || 'Sin descripción'}}</div>
                            <div class=\"muted\">Texto: ${{schedule.search_text || 'Predeterminado'}}</div>
                            <div class=\"muted\">Última ejecución: ${{schedule.last_result || 'Sin resultados aún'}}</div>
                            <div class=\"actions\">
                                <button onclick=\"runSchedule(${{schedule.id}})\">Ejecutar ahora</button>
                                <button onclick=\"testSchedule(${{schedule.id}})\" class=\"secondary\">Probar sin Telegram</button>
                                <button onclick=\"editSchedule(${{schedule.id}})\" class=\"secondary\">Editar</button>
                                <button onclick=\"deleteSchedule(${{schedule.id}})\">Eliminar</button>
                            </div>
                        </div>
                    `).join('');
                }}

                async function loadHistory() {{
                    const response = await fetch('/api/history');
                    const history = await response.json();
                    if (!history.length) {{
                        historyList.innerHTML = '<p class=\"muted\">No hay ejecuciones registradas todavía.</p>'; 
                        return;
                    }}
                    historyList.innerHTML = history.map(item => `
                        <div class=\"history-item\">
                            <strong>${{item.schedule_name || 'Corrida sin nombre'}}</strong>
                            <div class=\"muted\">${{item.executed_at}} · ${{item.success ? 'Éxito' : 'Falló'}}</div>
                            <div class=\"muted\">${{item.message || 'Sin detalle'}}</div>
                        </div>
                    `).join('');
                }}

                async function runSchedule(id) {{
                    const response = await fetch(`/api/schedules/${{id}}/run`, {{method: 'POST'}});
                    const data = await response.json();
                    resultBox.textContent = data.detail?.message || JSON.stringify(data, null, 2);
                    loadSchedules();
                    loadHistory();
                }}

                async function testSchedule(id) {{
                    const response = await fetch(`/api/schedules/${{id}}/test`, {{method: 'POST'}});
                    const data = await response.json();
                    resultBox.textContent = data.detail?.message || JSON.stringify(data, null, 2);
                    loadHistory();
                }}

                async function deleteSchedule(id) {{
                    if (!confirm('¿Deseas eliminar esta corrida?')) return;
                    await fetch(`/api/schedules/${{id}}`, {{method: 'DELETE'}});
                    resultBox.textContent = 'Corrida eliminada.';
                    loadSchedules();
                    loadHistory();
                }}

                async function editSchedule(id) {{
                    const response = await fetch(`/api/schedules/${{id}}`);
                    const schedule = await response.json();
                    document.getElementById('schedule-id').value = schedule.id;
                    document.getElementById('name').value = schedule.name || '';
                    document.getElementById('hour').value = schedule.hour || '';
                    document.getElementById('minute').value = schedule.minute || '';
                    document.getElementById('description').value = schedule.description || '';
                    document.getElementById('search_text').value = schedule.search_text || '';
                    document.getElementById('enabled').checked = Boolean(schedule.enabled);
                    submitButton.textContent = 'Actualizar corrida';
                    resultBox.textContent = 'Editando corrida: ' + schedule.name;
                }}

                form.addEventListener('submit', async (event) => {{
                    event.preventDefault();
                    const id = scheduleIdInput.value;
                    const payload = {{
                        name: document.getElementById('name').value,
                        hour: Number(document.getElementById('hour').value),
                        minute: Number(document.getElementById('minute').value),
                        description: document.getElementById('description').value,
                        search_text: document.getElementById('search_text').value,
                        enabled: document.getElementById('enabled').checked,
                    }};
                    const method = id ? 'PUT' : 'POST';
                    const url = id ? `/api/schedules/${{id}}` : '/api/schedules';
                    const response = await fetch(url, {{method, headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(payload)}});
                    const data = await response.json();
                    resultBox.textContent = data.status === 'updated' ? 'Corrida actualizada.' : 'Corrida guardada.';
                    resetForm();
                    loadSchedules();
                    loadHistory();
                }});

                async function exportSchedules() {{
                    const response = await fetch('/api/schedules/export');
                    const data = await response.json();
                    const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'schedules.json';
                    a.click();
                    URL.revokeObjectURL(url);
                }}

                importFile.addEventListener('change', async (event) => {{
                    const file = event.target.files[0];
                    if (!file) return;
                    const text = await file.text();
                    const payload = JSON.parse(text);
                    const response = await fetch('/api/schedules/import', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(payload)}});
                    const data = await response.json();
                    resultBox.textContent = `{{data.status}}: ${{data.imported}} corridas importadas.`;
                    loadSchedules();
                    loadHistory();
                    importFile.value = '';
                }});

                stateFilter.addEventListener('change', loadSchedules);

                resetForm();
                loadSchedules();
                loadHistory();
            </script>
        </body>
        </html>
        """
    )


@app.get("/api/schedules")
async def get_schedules(request: Request, state: str | None = None) -> JSONResponse:
    try:
        auth_required(request)
        return JSONResponse(content=list_schedules(state=state))
    except Exception as exc:
        logger.exception("Error al leer las corridas: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudieron cargar las corridas") from exc


@app.get("/api/schedules/{schedule_id}")
async def get_schedule_endpoint(schedule_id: int) -> JSONResponse:
    try:
        schedule = get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Corrida no encontrada")
        return JSONResponse(content=schedule)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error consultando la corrida: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo consultar la corrida") from exc


@app.post("/api/schedules")
async def create_schedule_endpoint(request: Request) -> JSONResponse:
    try:
        auth_required(request)
        payload = await request.json()
        schedule_id = create_schedule(
            name=payload.get("name", "Corrida nueva"),
            hour=int(payload.get("hour", 0)),
            minute=int(payload.get("minute", 0)),
            enabled=bool(payload.get("enabled", True)),
            description=payload.get("description", ""),
            search_text=payload.get("search_text", ""),
        )
        return JSONResponse(content={"id": schedule_id, "status": "created"})
    except Exception as exc:
        logger.exception("Error creando la corrida: %s", exc)
        raise HTTPException(status_code=400, detail="No se pudo crear la corrida") from exc


@app.put("/api/schedules/{schedule_id}")
async def update_schedule_endpoint(schedule_id: int, request: Request) -> JSONResponse:
    try:
        auth_required(request)
        payload = await request.json()
        updated = update_schedule(schedule_id, payload)
        return JSONResponse(content={"status": "updated", "schedule": updated})
    except Exception as exc:
        logger.exception("Error actualizando la corrida: %s", exc)
        raise HTTPException(status_code=400, detail="No se pudo actualizar la corrida") from exc


@app.delete("/api/schedules/{schedule_id}")
async def delete_schedule_endpoint(schedule_id: int, request: Request) -> JSONResponse:
    try:
        auth_required(request)
        delete_schedule(schedule_id)
        return JSONResponse(content={"status": "deleted"})
    except Exception as exc:
        logger.exception("Error eliminando la corrida: %s", exc)
        raise HTTPException(status_code=400, detail="No se pudo eliminar la corrida") from exc


@app.post("/api/schedules/{schedule_id}/run")
async def run_schedule_endpoint(schedule_id: int, request: Request) -> JSONResponse:
    try:
        auth_required(request)
        schedule = get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Corrida no encontrada")
        execution = report(search_text=schedule.get("search_text") or None, schedule_name=schedule.get("name"))
        update_schedule(schedule_id, {"last_run_date": datetime.now().strftime("%Y-%m-%d"), "last_result": execution.get("message", "")})
        log_run(schedule_id, schedule.get("name"), execution.get("status") == "success", execution.get("message", ""))
        return JSONResponse(content={"status": "executed", "detail": execution})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error ejecutando la corrida: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo ejecutar la corrida") from exc


@app.post("/api/schedules/{schedule_id}/test")
async def test_schedule_endpoint(schedule_id: int, request: Request) -> JSONResponse:
    try:
        auth_required(request)
        schedule = get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Corrida no encontrada")
        execution = report(
            search_text=schedule.get("search_text") or None,
            schedule_name=schedule.get("name"),
            send_notifications=False,
            send_pdf=False,
        )
        return JSONResponse(content={"status": "tested", "detail": execution})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error probando la corrida: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo probar la corrida") from exc


@app.get("/api/history")
async def get_history(request: Request) -> JSONResponse:
    try:
        auth_required(request)
        return JSONResponse(content=list_run_logs())
    except Exception as exc:
        logger.exception("Error consultando el historial: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo cargar el historial") from exc


@app.get("/api/schedules/export")
async def export_schedules_endpoint(request: Request) -> JSONResponse:
    try:
        auth_required(request)
        return JSONResponse(content=export_schedules())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error exportando corridas: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudieron exportar las corridas") from exc


@app.post("/api/schedules/import")
async def import_schedules_endpoint(request: Request) -> JSONResponse:
    try:
        auth_required(request)
        payload = await request.json()
        imported = import_schedules(payload if isinstance(payload, list) else [payload])
        return JSONResponse(content={"status": "imported", "imported": imported})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error importando corridas: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudieron importar las corridas") from exc


@app.get("/status")
async def get_status() -> dict[str, Any]:
    timezone = os.getenv("TIMEZONE", "America/Merida")
    tz = pytz.timezone(timezone)
    current_time = datetime.now(tz)
    return {
        "status": "running",
        "current_time": current_time.isoformat(),
        "timezone": timezone,
        "schedules": list_schedules(),
    }


def should_run_at_merida_time(target_hour: int, target_minute: int) -> bool:
    merida_tz = pytz.timezone("America/Merida")
    now_merida = datetime.now(merida_tz)
    return now_merida.hour == target_hour and now_merida.minute == target_minute


def run_scheduler() -> None:
    try:
        init_db()
        while True:
            try:
                schedules = list_schedules()
                now_tz = datetime.now(pytz.timezone(os.getenv("TIMEZONE", "America/Merida")))
                current_date = now_tz.strftime("%Y-%m-%d")

                for schedule in schedules:
                    if not schedule.get("enabled"):
                        continue
                    if schedule.get("last_run_date") == current_date:
                        continue
                    if now_tz.hour != int(schedule.get("hour", 0)) or now_tz.minute != int(schedule.get("minute", 0)):
                        continue

                    logger.info("Ejecutando corrida programada: %s", schedule.get("name"))
                    execution = report(search_text=schedule.get("search_text") or None, schedule_name=schedule.get("name"))
                    update_schedule(schedule["id"], {"last_run_date": current_date, "last_result": execution.get("message", "")})
                    log_run(schedule["id"], schedule.get("name"), execution.get("status") == "success", execution.get("message", ""))
            except Exception as exc:
                logger.exception("Error en el ciclo del scheduler: %s", exc)
            time.sleep(60)
    except Exception as exc:
        logger.exception("El scheduler se detuvo por un error: %s", exc)


scheduler_thread: threading.Thread | None = None


@app.on_event("startup")
async def startup_event() -> None:
    global scheduler_thread
    init_db()
    try:
        logger.info("Ejecutando reporte de inicio")
        report()
    except Exception as exc:
        logger.exception("El reporte de inicio falló: %s", exc)

    if scheduler_thread is None or not scheduler_thread.is_alive():
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("Scheduler iniciado en hilo separado")


def start_health_server(port: int | None = None) -> None:
    try:
        port_value = int(port or os.getenv("PORT", "8000"))
        logger.info("Iniciando servidor FastAPI en puerto %s", port_value)
        uvicorn.run(app, host="0.0.0.0", port=port_value, log_level="warning")
    except Exception as exc:
        logger.exception("No se pudo iniciar el servidor: %s", exc)


if __name__ == "__main__":
    start_health_server(int(os.getenv("PORT", "8080")))
