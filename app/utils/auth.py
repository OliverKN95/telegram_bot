import base64
import os
from fastapi import HTTPException, Request
from fastapi.security import HTTPBasicCredentials


def verify_basic_auth(credentials: HTTPBasicCredentials) -> bool:
    expected_user = os.getenv("ADMIN_USER", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "admin123")
    return credentials.username == expected_user and credentials.password == expected_password


def auth_required(request: Request) -> None:
    if os.getenv("ENABLE_AUTH", "true").lower() != "true":
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
