import base64
import hashlib
import hmac
import os
import time
from fastapi import HTTPException, Request
from fastapi.security import HTTPBasicCredentials

SESSION_COOKIE_NAME = "admin_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


def verify_basic_auth(credentials: HTTPBasicCredentials) -> bool:
    expected_user = os.getenv("ADMIN_USER", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "admin123")
    return credentials.username == expected_user and credentials.password == expected_password


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
