import logging
import os
import threading
from datetime import datetime

import pytz

from app.crud import schedules as schedule_crud

try:
    from telegram_bot import report as legacy_report
except Exception:  # pragma: no cover - fallback when the legacy module is unavailable
    legacy_report = None

logger = logging.getLogger("telegram_bot.scheduler")

_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _get_timezone() -> pytz.BaseTzInfo:
    return pytz.timezone(os.getenv("TIMEZONE", "America/Merida"))


def run_pending_schedules() -> None:
    if legacy_report is None:
        logger.warning("No se pudo ejecutar el scheduler: motor de scraping no disponible")
        return

    now_tz = datetime.now(_get_timezone())
    current_date = now_tz.strftime("%Y-%m-%d")

    for schedule in schedule_crud.list_schedules():
        if not schedule.get("enabled"):
            continue
        if schedule.get("last_run_date") == current_date:
            continue
        if now_tz.hour != int(schedule.get("hour", 0)) or now_tz.minute != int(schedule.get("minute", 0)):
            continue

        schedule_id = schedule["id"]
        schedule_name = schedule.get("name")
        logger.info("Ejecutando corrida programada: %s", schedule_name)
        try:
            execution = legacy_report(
                search_text=schedule.get("search_text") or None,
                schedule_name=schedule_name,
                send_notifications=bool(schedule.get("send_to_telegram", True)),
            )
        except Exception as exc:
            logger.exception("Error ejecutando la corrida %s: %s", schedule_id, exc)
            execution = {"status": "error", "message": str(exc)}

        schedule_crud.update_schedule(
            schedule_id,
            {"last_run_date": current_date, "last_result": execution.get("message", "")},
        )
        schedule_crud.log_run(
            schedule_id,
            schedule_name,
            execution.get("status") == "success",
            execution.get("message", ""),
        )


def _scheduler_loop(poll_interval: int) -> None:
    logger.info("Scheduler en background iniciado (poll cada %s s)", poll_interval)
    while not _stop_event.is_set():
        try:
            run_pending_schedules()
        except Exception as exc:
            logger.exception("Error en el ciclo del scheduler: %s", exc)
        _stop_event.wait(poll_interval)


def start_scheduler(poll_interval: int = 30) -> None:
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, args=(poll_interval,), daemon=True)
    _scheduler_thread.start()


def stop_scheduler() -> None:
    _stop_event.set()
