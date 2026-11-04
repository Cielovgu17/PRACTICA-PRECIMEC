"""Autenticación y permisos: contraseñas, sesiones y límite de intentos."""
import base64
import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

SESSION_DAYS = 7
MIN_PASSWORD = 10
MAX_FAILS = 5
LOCK_SECONDS = 300
ROLES = ("admin", "consulta")

_fails: dict[str, tuple[int, float]] = {}
_fails_lock = threading.Lock()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(key).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, key = stored.split("$")
        expected = base64.b64decode(key)
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2**14, r=8, p=1, dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


def is_locked(email: str) -> bool:
    with _fails_lock:
        count, last = _fails.get(email.lower(), (0, 0.0))
        return count >= MAX_FAILS and time.time() - last < LOCK_SECONDS


def record_fail(email: str) -> None:
    with _fails_lock:
        count, last = _fails.get(email.lower(), (0, 0.0))
        if time.time() - last >= LOCK_SECONDS:
            count = 0
        _fails[email.lower()] = (count + 1, time.time())


def clear_fails(email: str) -> None:
    with _fails_lock:
        _fails.pop(email.lower(), None)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_now(),))
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, expires.isoformat()),
    )
    conn.commit()
    return token


def destroy_session(conn, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
    conn.commit()


def user_from_token(conn, token: str | None):
    if not token:
        return None
    return conn.execute(
        """SELECT u.id, u.email, u.name, u.role FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ?""",
        (_token_hash(token), _now()),
    ).fetchone()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
