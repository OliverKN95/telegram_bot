import base64
import os

import pytest
from fastapi.testclient import TestClient

from app.crud import schedules as schedule_crud
from app.main import app


def get_auth_header() -> dict[str, str]:
    token = base64.b64encode(b"admin:admin123").decode("utf-8")
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "schedules-test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("ENABLE_AUTH", "true")
    schedule_crud.init_db()
    with TestClient(app) as test_client:
        yield test_client


def test_ui_endpoints_load_without_auth_headers(client):
    schedule_id = schedule_crud.create_schedule(
        name="Prueba",
        hour=8,
        minute=30,
        enabled=True,
        description="desc",
        search_text="demo",
    )

    response = client.get("/", headers=get_auth_header())
    assert response.status_code == 200

    response = client.get("/api/schedules", headers=get_auth_header())
    assert response.status_code == 200
    payload = response.json()
    assert any(item["id"] == schedule_id for item in payload)


def test_login_redirects_to_panel_and_session_authenticates_api(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "httponly" in response.headers["set-cookie"].lower()

    response = client.get("/")
    assert response.status_code == 200
    assert "Panel de corridas" in response.text
    assert client.get("/api/schedules").status_code == 200


def test_login_rejects_invalid_credentials(client):
    response = client.post(
        "/login",
        data={"username": "admin", "password": "incorrecta"},
    )
    assert response.status_code == 401
    assert "Usuario o contraseña incorrectos" in response.text


def test_history_endpoint_returns_saved_run_logs(client):
    schedule_crud.create_schedule(name="Historial", hour=9, minute=15, enabled=True)
    schedule_crud.log_run(schedule_id=1, schedule_name="Historial", success=True, message="ok")

    response = client.get("/api/history", headers=get_auth_header())
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["schedule_name"] == "Historial"
    assert payload[0]["message"] == "ok"
