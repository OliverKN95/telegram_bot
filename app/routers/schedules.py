import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPBasicCredentials

from app.crud import schedules as schedule_crud
from app.schemas.schedules import ScheduleCreate, ScheduleUpdate
from app.utils.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    auth_required,
    create_session_token,
    verify_basic_auth,
)

try:
    from telegram_bot import report as legacy_report
except Exception:  # pragma: no cover - fallback when the legacy module is unavailable
    legacy_report = None

router = APIRouter()
logger = logging.getLogger("telegram_bot.routes")


def render_login(error: bool = False) -> HTMLResponse:
    error_message = '<p class="error">Usuario o contraseña incorrectos.</p>' if error else ""
    return HTMLResponse(
        f"""<!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Iniciar sesión</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 24px; font-family: Arial, sans-serif; color: #172033; background: linear-gradient(135deg, #eff6ff, #f8fafc 55%, #e0e7ff); }}
                main {{ width: min(100%, 420px); padding: 36px; border: 1px solid #e2e8f0; border-radius: 20px; background: white; box-shadow: 0 24px 70px #0f172a1a; }}
                h1 {{ margin: 0 0 8px; font-size: 26px; }}
                p {{ color: #64748b; line-height: 1.5; }}
                form {{ display: grid; gap: 14px; margin-top: 24px; }}
                label {{ display: grid; gap: 7px; color: #334155; font-size: 14px; font-weight: 600; }}
                input, button {{ width: 100%; padding: 12px 14px; border: 1px solid #cbd5e1; border-radius: 10px; font: inherit; }}
                input:focus {{ outline: 3px solid #bfdbfe; border-color: #3b82f6; }}
                button {{ border: 0; color: white; background: #2563eb; font-weight: 700; cursor: pointer; }}
                button:hover {{ background: #1d4ed8; }}
                .error {{ margin: 0; padding: 10px 12px; border-radius: 8px; color: #b91c1c; background: #fef2f2; }}
            </style>
        </head>
        <body><main>
            <h1>Iniciar sesión</h1>
            <p>Ingresa tus credenciales de administrador para abrir el panel.</p>
            {error_message}
            <form method="post" action="/login">
                <label>Usuario<input name="username" autocomplete="username" required autofocus></label>
                <label>Contraseña<input name="password" type="password" autocomplete="current-password" required></label>
                <button type="submit">Entrar al panel</button>
            </form>
        </main></body></html>""",
        status_code=401 if error else 200,
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    try:
        auth_required(request)
        return RedirectResponse("/", status_code=303)
    except HTTPException:
        return render_login()


@router.post("/login", response_class=HTMLResponse)
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


@router.get("/", response_class=HTMLResponse)
async def root(request: Request) -> Response:
    try:
        auth_required(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    count = len(schedule_crud.list_schedules())
    return HTMLResponse(
        f"""
        <!DOCTYPE html>
        <html lang=\"es\">
        <head>
            <meta charset=\"utf-8\">
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
            <title>Panel de corridas</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f7fb; color: #111827; }}
                main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
                .card {{ background: white; border-radius: 16px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); margin-bottom: 20px; }}
                h1, h2 {{ margin-top: 0; }}
                form {{ display: grid; gap: 12px; }}
                input, textarea, button, select {{ padding: 10px; border-radius: 8px; border: 1px solid #d1d5db; font-size: 14px; }}
                button {{ cursor: pointer; background: #2563eb; color: white; border: none; }}
                button.secondary {{ background: #6b7280; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
                .toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }}
                .schedule {{ border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; margin-bottom: 10px; }}
                .muted {{ color: #6b7280; font-size: 13px; }}
                .actions button {{ margin-right: 6px; margin-top: 8px; }}
                .result {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 8px; margin-top: 10px; white-space: pre-wrap; }}
                .history-item {{ border-top: 1px solid #e5e7eb; padding: 8px 0; }}
                .switch {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 999px; background: #f9fafb; }}
                .switch input {{ display: none; }}
                .switch .slider {{ width: 40px; height: 22px; border-radius: 999px; background: #cbd5e1; position: relative; transition: background 0.2s ease; }}
                .switch .slider::after {{ content: ''; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%; background: white; transition: transform 0.2s ease; }}
                .switch input:checked + .slider {{ background: #2563eb; }}
                .switch input:checked + .slider::after {{ transform: translateX(18px); }}
            </style>
        </head>
        <body>
            <main>
                <section class=\"card\">
                    <h1>Panel de corridas</h1>
                    <p class=\"muted\">Gestión modular de corridas con filtros, importación/exportación y pruebas rápidas.</p>
                    <div class=\"grid\">
                        <div><strong>Corridas activas:</strong> {count}</div>
                        <div><strong>Zona horaria:</strong> {"America/Merida"}</div>
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
                        <label><input id=\"enabled\" type=\"checkbox\" checked> Habilitada</label>                        <label class="switch">
                            <input id="form-send-to-telegram-toggle" type="checkbox" checked>
                            <span class="slider"></span>
                            <span>Enviar a Telegram</span>
                        </label>                        <button type=\"submit\" id=\"submit-button\">Guardar corrida</button>
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
                        <label class="switch">
                            <input id="send-to-telegram-toggle" type="checkbox" checked>
                            <span class="slider"></span>
                            <span>Enviar a Telegram</span>
                        </label>
                        <button onclick="exportSchedules()">Exportar JSON</button>
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
                const sendToTelegramToggle = document.getElementById('send-to-telegram-toggle');
                const formSendToTelegramToggle = document.getElementById('form-send-to-telegram-toggle');
                async function fetchJson(url, options = {{}}) {{
                    const response = await fetch(url, options);
                    if (!response.ok) {{
                        throw new Error(`Error ${{response.status}}: ${{response.statusText}}`);
                    }}
                    return response.json();
                }}

                function resetForm() {{
                    form.reset();
                    scheduleIdInput.value = '';
                    submitButton.textContent = 'Guardar corrida';
                    resultBox.textContent = 'Listo para crear o editar una corrida.';
                    formSendToTelegramToggle.checked = true;
                    sendToTelegramToggle.checked = true;
                }}

                async function loadSchedules() {{
                    try {{
                        const state = stateFilter.value;
                    const schedules = await fetchJson(`/api/schedules${{state === 'all' ? '' : `?state=${{state}}`}}`);
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
                            <div class=\"muted\">Telegram: ${{schedule.send_to_telegram ? 'Sí' : 'No'}}</div>
                            <div class=\"muted\">Última ejecución: ${{schedule.last_result || 'Sin resultados aún'}}</div>
                            <div class=\"actions\">
                                <button onclick=\"runSchedule(${{schedule.id}})\">Ejecutar ahora</button>
                                <button onclick=\"editSchedule(${{schedule.id}})\" class=\"secondary\">Editar</button>
                                <button onclick=\"deleteSchedule(${{schedule.id}})\">Eliminar</button>
                            </div>
                        </div>
                    `).join('');
                    }} catch (error) {{
                        list.innerHTML = `<p class="muted">No se pudo cargar la lista de corridas. ${{error.message}}</p>`;
                    }}
                }}

                async function loadHistory() {{
                    try {{
                        const history = await fetchJson('/api/history');
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
                    }} catch (error) {{
                        historyList.innerHTML = `<p class="muted">No se pudo cargar el historial. ${{error.message}}</p>`;
                    }}
                }}

                async function runSchedule(id) {{
                    const sendToTelegram = sendToTelegramToggle.checked;
                    const data = await fetchJson(`/api/schedules/${{id}}/run?send_to_telegram=${{sendToTelegram}}`, {{method: 'POST'}});
                    const message = data.detail?.message || JSON.stringify(data, null, 2);
                    const telegramStatus = sendToTelegram
                        ? (data.detail?.telegram_sent ? '\\n📣 Mensaje enviado a Telegram.' : '\\n⚠️ No se pudo enviar el mensaje a Telegram.')
                        : '\\n🛑 Envío a Telegram desactivado para esta prueba.';
                    resultBox.textContent = `${{message}}${{telegramStatus}}`;
                    loadSchedules();
                    loadHistory();
                }}

                async function deleteSchedule(id) {{
                    if (!confirm('¿Deseas eliminar esta corrida?')) return;
                    await fetchJson(`/api/schedules/${{id}}`, {{method: 'DELETE'}});
                    resultBox.textContent = 'Corrida eliminada.';
                    loadSchedules();
                    loadHistory();
                }}

                async function editSchedule(id) {{
                    const schedule = await fetchJson(`/api/schedules/${{id}}`);
                    document.getElementById('schedule-id').value = schedule.id;
                    document.getElementById('name').value = schedule.name || '';
                    document.getElementById('hour').value = schedule.hour || '';
                    document.getElementById('minute').value = schedule.minute || '';
                    document.getElementById('description').value = schedule.description || '';
                    document.getElementById('search_text').value = schedule.search_text || '';
                    document.getElementById('enabled').checked = Boolean(schedule.enabled);
                    formSendToTelegramToggle.checked = schedule.send_to_telegram !== false;
                    sendToTelegramToggle.checked = schedule.send_to_telegram !== false;
                    submitButton.textContent = 'Actualizar corrida';
                    resultBox.textContent = 'Editando corrida: ' + schedule.name;
                }}

                async function exportSchedules() {{
                    const data = await fetchJson('/api/schedules/export');
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
                    const data = await fetchJson('/api/schedules/import', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(payload)}});
                    resultBox.textContent = `${{data.status}}: ${{data.imported}} corridas importadas.`;
                    loadSchedules();
                    loadHistory();
                    importFile.value = '';
                }});

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
                        send_to_telegram: formSendToTelegramToggle.checked,
                    }};
                    const method = id ? 'PUT' : 'POST';
                    const url = id ? `/api/schedules/${{id}}` : '/api/schedules';
                    const data = await fetchJson(url, {{method, headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(payload)}});
                    resultBox.textContent = data.status === 'updated' ? 'Corrida actualizada.' : 'Corrida guardada.';
                    resetForm();
                    loadSchedules();
                    loadHistory();
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


@router.get("/api/schedules")
async def get_schedules(request: Request, state: str | None = None) -> JSONResponse:
    auth_required(request)
    return JSONResponse(content=schedule_crud.list_schedules(state=state))


@router.get("/api/schedules/{schedule_id}")
async def get_schedule_detail(schedule_id: int, request: Request) -> JSONResponse:
    auth_required(request)
    schedule = schedule_crud.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Corrida no encontrada")
    return JSONResponse(content=schedule)


@router.post("/api/schedules", status_code=201)
async def create_schedule(request: Request, payload: ScheduleCreate) -> JSONResponse:
    auth_required(request)
    schedule_id = schedule_crud.create_schedule(
        name=payload.name,
        hour=payload.hour,
        minute=payload.minute,
        enabled=payload.enabled,
        description=payload.description,
        search_text=payload.search_text,
        send_to_telegram=payload.send_to_telegram,
    )
    return JSONResponse(content={"id": schedule_id, "status": "created"})


@router.put("/api/schedules/{schedule_id}")
async def update_schedule(schedule_id: int, request: Request, payload: ScheduleUpdate) -> JSONResponse:
    auth_required(request)
    updates = payload.model_dump(exclude_unset=True)
    updated = schedule_crud.update_schedule(schedule_id, updates)
    return JSONResponse(content={"status": "updated", "schedule": updated})


@router.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, request: Request) -> JSONResponse:
    auth_required(request)
    schedule_crud.delete_schedule(schedule_id)
    return JSONResponse(content={"status": "deleted"})


@router.post("/api/schedules/{schedule_id}/run")
async def run_schedule(schedule_id: int, request: Request, send_to_telegram: bool | None = None) -> JSONResponse:
    auth_required(request)
    schedule = schedule_crud.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Corrida no encontrada")

    if legacy_report is None:
        return JSONResponse(content={"status": "executed", "detail": {"status": "success", "message": "Sin motor de scraping disponible", "schedule_name": schedule.get("name")}})

    try:
        send_notifications = bool(schedule.get("send_to_telegram", True)) if send_to_telegram is None else send_to_telegram
        execution = legacy_report(
            search_text=schedule.get("search_text") or None,
            schedule_name=schedule.get("name"),
            send_notifications=send_notifications,
        )
        schedule_crud.update_schedule(
            schedule_id,
            {
                "last_run_date": datetime.now().strftime("%Y-%m-%d"),
                "last_result": execution.get("message", ""),
            },
        )
        schedule_crud.log_run(
            schedule_id,
            schedule.get("name"),
            execution.get("status") == "success",
            execution.get("message", ""),
        )
        return JSONResponse(content={"status": "executed", "detail": execution})
    except Exception as exc:
        logger.exception("Error ejecutando la corrida %s: %s", schedule_id, exc)
        raise HTTPException(status_code=500, detail="No se pudo ejecutar la corrida") from exc


@router.get("/api/history")
async def get_history(request: Request) -> JSONResponse:
    auth_required(request)
    return JSONResponse(content=schedule_crud.list_run_logs())


@router.get("/api/schedules/export")
async def export_schedules(request: Request) -> JSONResponse:
    auth_required(request)
    return JSONResponse(content=schedule_crud.export_schedules())


@router.post("/api/schedules/import")
async def import_schedules(request: Request) -> JSONResponse:
    auth_required(request)
    payload = await request.json()
    imported = schedule_crud.import_schedules(payload if isinstance(payload, list) else [payload])
    return JSONResponse(content={"status": "imported", "imported": imported})
