import os
import sqlite3


def get_db_path() -> str:
    return os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "schedules.db"))


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
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
            last_result TEXT,
            send_to_telegram INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(schedules)").fetchall()}
    if "send_to_telegram" not in columns:
        conn.execute("ALTER TABLE schedules ADD COLUMN send_to_telegram INTEGER NOT NULL DEFAULT 1")
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
