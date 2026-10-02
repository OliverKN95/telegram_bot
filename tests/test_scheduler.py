import os
from datetime import datetime

import pytz

from app.crud import schedules as schedule_crud
from app.utils import scheduler


def test_run_pending_schedules_executes_matching_schedule(tmp_path, monkeypatch):
    db_path = tmp_path / "scheduler-test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    schedule_crud.init_db()

    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Merida"))
    now = datetime.now(tz)

    schedule_id = schedule_crud.create_schedule(
        name="Corrida en hora",
        hour=now.hour,
        minute=now.minute,
        enabled=True,
        search_text="demo",
        send_to_telegram=False,
    )

    calls = []

    def fake_report(search_text=None, schedule_name=None, send_notifications=True):
        calls.append((search_text, schedule_name, send_notifications))
        return {"status": "success", "message": "ejecutado ok", "telegram_sent": False}

    monkeypatch.setattr(scheduler, "legacy_report", fake_report)

    scheduler.run_pending_schedules()

    assert calls == [("demo", "Corrida en hora", False)]

    updated = schedule_crud.get_schedule(schedule_id)
    assert updated["last_run_date"] == now.strftime("%Y-%m-%d")
    assert updated["last_result"] == "ejecutado ok"

    history = schedule_crud.list_run_logs()
    assert history
    assert history[0]["schedule_name"] == "Corrida en hora"
    assert history[0]["success"] == 1

    # Running again in the same day should be skipped (already executed today)
    scheduler.run_pending_schedules()
    assert len(calls) == 1


def test_run_pending_schedules_skips_disabled_or_mismatched_time(tmp_path, monkeypatch):
    db_path = tmp_path / "scheduler-test-2.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    schedule_crud.init_db()

    schedule_crud.create_schedule(name="Deshabilitada", hour=0, minute=0, enabled=False)
    schedule_crud.create_schedule(name="Otra hora", hour=23, minute=59, enabled=True)

    calls = []

    def fake_report(search_text=None, schedule_name=None, send_notifications=True):
        calls.append(schedule_name)
        return {"status": "success", "message": "ok"}

    monkeypatch.setattr(scheduler, "legacy_report", fake_report)

    scheduler.run_pending_schedules()

    assert calls == []
