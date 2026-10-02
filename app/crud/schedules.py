import sqlite3
from datetime import datetime
from typing import Any

from app.utils.db import get_db_connection, init_db


def create_schedule(name: str, hour: int, minute: int, enabled: bool = True, description: str = "", search_text: str = "", send_to_telegram: bool = True) -> int:
    init_db()
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO schedules (name, hour, minute, enabled, description, search_text, send_to_telegram)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, hour, minute, int(enabled), description, search_text, int(send_to_telegram)),
    )
    conn.commit()
    schedule_id = cursor.lastrowid
    conn.close()
    return int(schedule_id)


def list_schedules(state: str | None = None) -> list[dict[str, Any]]:
    init_db()
    conn = get_db_connection()
    query = "SELECT id, name, hour, minute, enabled, description, search_text, last_run_date, last_result, send_to_telegram FROM schedules"
    params: list[Any] = []
    if state == "active":
        query += " WHERE enabled = 1"
    elif state == "disabled":
        query += " WHERE enabled = 0"
    query += " ORDER BY hour, minute, name"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_schedule(schedule_id: int) -> dict[str, Any] | None:
    init_db()
    conn = get_db_connection()
    row = conn.execute(
        "SELECT id, name, hour, minute, enabled, description, search_text, last_run_date, last_result, send_to_telegram FROM schedules WHERE id = ?",
        (schedule_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_schedule(schedule_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    init_db()
    if not updates:
        return get_schedule(schedule_id)

    valid_fields = {"name", "hour", "minute", "enabled", "description", "search_text", "last_run_date", "last_result", "send_to_telegram"}
    unexpected = set(updates) - valid_fields
    if unexpected:
        raise ValueError(f"Campos no permitidos: {sorted(unexpected)}")

    assignments = []
    values: list[Any] = []
    for key, value in updates.items():
        if key in {"enabled", "send_to_telegram"} and isinstance(value, bool):
            value = int(value)
        assignments.append(f"{key} = ?")
        values.append(value)
    values.append(schedule_id)

    conn = get_db_connection()
    conn.execute(f"UPDATE schedules SET {', '.join(assignments)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return get_schedule(schedule_id)


def delete_schedule(schedule_id: int) -> bool:
    init_db()
    conn = get_db_connection()
    conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    conn.close()
    return True


def log_run(schedule_id: int | None, schedule_name: str, success: bool, message: str) -> None:
    init_db()
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO run_logs (schedule_id, schedule_name, executed_at, success, message) VALUES (?, ?, ?, ?, ?)",
        (schedule_id, schedule_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(success), message),
    )
    conn.commit()
    conn.close()


def list_run_logs(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id, schedule_id, schedule_name, executed_at, success, message FROM run_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


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
            send_to_telegram=bool(item.get("send_to_telegram", True)),
        )
        imported += 1
    return imported
