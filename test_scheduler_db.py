import importlib
import os


def test_create_and_manage_schedules(tmp_path, monkeypatch):
    db_path = tmp_path / "schedules.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import telegram_bot

    telegram_bot = importlib.reload(telegram_bot)
    telegram_bot.init_db()

    schedule_id = telegram_bot.create_schedule(
        name="Corrida matutina",
        hour=8,
        minute=15,
        enabled=True,
        description="Prueba de programación",
        search_text="koyoc novelo",
    )

    schedules = telegram_bot.list_schedules()
    assert len(schedules) == 1
    assert schedules[0]["name"] == "Corrida matutina"
    assert schedules[0]["hour"] == 8
    assert schedules[0]["minute"] == 15

    updated = telegram_bot.update_schedule(schedule_id, {"enabled": 0, "description": "Actualizado"})
    assert updated["enabled"] == 0
    assert updated["description"] == "Actualizado"

    deleted = telegram_bot.delete_schedule(schedule_id)
    assert deleted is True
    assert telegram_bot.list_schedules() == []


def test_filter_export_and_import_schedules(tmp_path, monkeypatch):
    db_path = tmp_path / "schedules.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    import telegram_bot

    telegram_bot = importlib.reload(telegram_bot)
    telegram_bot.init_db()
    telegram_bot.create_schedule("Activa", 9, 0, True, "desc", "uno")
    telegram_bot.create_schedule("Inactiva", 10, 0, False, "desc", "dos")

    active = telegram_bot.list_schedules(state="active")
    disabled = telegram_bot.list_schedules(state="disabled")

    assert len(active) == 1
    assert active[0]["name"] == "Activa"
    assert len(disabled) == 1
    assert disabled[0]["name"] == "Inactiva"

    exported = telegram_bot.export_schedules()
    assert len(exported) == 2

    telegram_bot.delete_schedule(1)
    telegram_bot.delete_schedule(2)
    imported = telegram_bot.import_schedules(exported)
    assert imported == 2
    assert len(telegram_bot.list_schedules()) == 2
