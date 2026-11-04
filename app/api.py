"""Rutas de la API. Cada función recibe el contexto de la petición y devuelve un dict."""
import re
from dataclasses import dataclass, field

from . import assets, auth, content
from .errors import ApiError

ROUTES: list[tuple[str, re.Pattern, object, str | None]] = []


@dataclass
class Ctx:
    conn: object
    user: object
    body: dict
    query: dict
    params: tuple
    uploads: object
    token: str | None = None
    stream: object = None
    length: int = 0
    set_token: list = field(default_factory=list)  # [token] inicia sesión, [None] la cierra


def route(method: str, path: str, role: str | None = None):
    """role: None = abierta, 'user' = con sesión, 'admin' = solo administradores."""
    pattern = re.compile("^" + re.sub(r":\w+", r"(\\d+)", path) + "$")

    def wrap(fn):
        ROUTES.append((method, pattern, fn, role))
        return fn

    return wrap


def resolve(method: str, path: str):
    known = False
    for route_method, pattern, fn, role in ROUTES:
        match = pattern.match(path)
        if match:
            known = True
            if route_method == method:
                return fn, role, tuple(int(g) for g in match.groups())
    raise ApiError(405 if known else 404, "Ruta no encontrada.")


def _user_dict(user) -> dict:
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


# ---------- Sesión ----------

@route("GET", "/api/me")
def me(ctx):
    return {"user": _user_dict(ctx.user) if ctx.user else None}


@route("POST", "/api/login")
def login(ctx):
    email = str(ctx.body.get("email", "")).strip()
    password = str(ctx.body.get("password", ""))
    if auth.is_locked(email):
        raise ApiError(429, "Demasiados intentos. Espera 5 minutos e inténtalo de nuevo.")
    row = ctx.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not auth.verify_password(password, row["password_hash"]):
        auth.record_fail(email)
        raise ApiError(401, "El correo o la contraseña no son correctos.")
    auth.clear_fails(email)
    ctx.set_token.append(auth.create_session(ctx.conn, row["id"]))
    return {"user": _user_dict(row)}


@route("POST", "/api/logout")
def logout(ctx):
    if ctx.token:
        auth.destroy_session(ctx.conn, ctx.token)
    ctx.set_token.append(None)
    return {"ok": True}


@route("POST", "/api/me/password", "user")
def change_password(ctx):
    row = ctx.conn.execute("SELECT * FROM users WHERE id = ?", (ctx.user["id"],)).fetchone()
    if not auth.verify_password(str(ctx.body.get("current", "")), row["password_hash"]):
        raise ApiError(400, "La contraseña actual no es correcta.")
    new = str(ctx.body.get("new", ""))
    if len(new) < auth.MIN_PASSWORD:
        raise ApiError(400, f"La contraseña nueva debe tener al menos {auth.MIN_PASSWORD} caracteres.")
    ctx.conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(new), row["id"]))
    ctx.conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
    ctx.conn.commit()
    ctx.set_token.append(auth.create_session(ctx.conn, row["id"]))
    return {"ok": True}


# ---------- Consulta ----------

@route("GET", "/api/content")
def get_content(ctx):
    if ctx.query.get("version") == "draft":
        if not ctx.user or ctx.user["role"] != "admin":
            raise ApiError(403, "La vista previa es solo para administradores.")
        return content.build_document(ctx.conn)
    return content.published_document(ctx.conn)


@route("GET", "/api/progress", "user")
def get_progress(ctx):
    done = [r["step_id"] for r in ctx.conn.execute("SELECT step_id FROM progress WHERE user_id = ?", (ctx.user["id"],))]
    state = ctx.conn.execute("SELECT last_step_id FROM user_state WHERE user_id = ?", (ctx.user["id"],)).fetchone()
    return {"done": done, "last_step_id": state["last_step_id"] if state else None}


@route("PUT", "/api/progress", "user")
def put_progress(ctx):
    done = ctx.body.get("done", [])
    last = ctx.body.get("last_step_id")
    if not isinstance(done, list) or not all(isinstance(i, int) for i in done):
        raise ApiError(400, "Progreso no válido.")
    if last is not None and not isinstance(last, int):
        raise ApiError(400, "Progreso no válido.")
    uid = ctx.user["id"]
    ctx.conn.execute("DELETE FROM progress WHERE user_id = ?", (uid,))
    ctx.conn.executemany("INSERT OR IGNORE INTO progress (user_id, step_id) VALUES (?, ?)", [(uid, i) for i in done])
    ctx.conn.execute(
        "INSERT INTO user_state (user_id, last_step_id) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET last_step_id = excluded.last_step_id",
        (uid, last),
    )
    ctx.conn.commit()
    return {"ok": True}


# ---------- Administración: borrador y publicación ----------

@route("GET", "/api/admin/draft", "admin")
def draft(ctx):
    return {"document": content.build_document(ctx.conn), "status": content.status(ctx.conn)}


@route("POST", "/api/admin/publish", "admin")
def publish(ctx):
    return content.publish(ctx.conn, ctx.user["name"])


@route("PUT", "/api/admin/technique", "admin")
def technique(ctx):
    content.update_technique(ctx.conn, ctx.body)
    return {"ok": True}


# ---------- Administración: pasos ----------

@route("POST", "/api/admin/steps", "admin")
def create_step(ctx):
    return {"id": content.create_step(ctx.conn, ctx.body)}


@route("PUT", "/api/admin/steps/:id", "admin")
def update_step(ctx):
    content.update_step(ctx.conn, ctx.params[0], ctx.body)
    return {"ok": True}


@route("DELETE", "/api/admin/steps/:id", "admin")
def delete_step(ctx):
    content.delete_step(ctx.conn, ctx.params[0])
    return {"ok": True}


@route("POST", "/api/admin/steps/:id/move", "admin")
def move_step(ctx):
    content.move_step(ctx.conn, ctx.params[0], ctx.body)
    return {"ok": True}


@route("PUT", "/api/admin/steps/:id/instruments", "admin")
def step_instruments(ctx):
    ids = ctx.body.get("ids", [])
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise ApiError(400, "Lista de instrumentos no válida.")
    content.set_step_instruments(ctx.conn, ctx.params[0], ids)
    return {"ok": True}


@route("POST", "/api/admin/steps/:id/media", "admin")
def add_media(ctx):
    content.add_media(ctx.conn, ctx.params[0], ctx.body)
    return {"ok": True}


@route("DELETE", "/api/admin/media/:id", "admin")
def delete_media(ctx):
    content.delete_media(ctx.conn, ctx.params[0])
    return {"ok": True}


# ---------- Administración: animaciones ----------

@route("POST", "/api/admin/steps/:id/animations", "admin")
def add_animation(ctx):
    content.add_animation(ctx.conn, ctx.params[0], ctx.body)
    return {"ok": True}


@route("PUT", "/api/admin/animations/:id", "admin")
def update_animation(ctx):
    content.update_animation(ctx.conn, ctx.params[0], ctx.body)
    return {"ok": True}


@route("PUT", "/api/admin/animations/:id/settings", "admin")
def animation_settings(ctx):
    content.update_animation_settings(ctx.conn, ctx.params[0], ctx.body)
    return {"ok": True}


@route("POST", "/api/admin/animations/:id/move", "admin")
def move_animation(ctx):
    content.move_animation(ctx.conn, ctx.params[0], ctx.body.get("direction"))
    return {"ok": True}


@route("DELETE", "/api/admin/animations/:id", "admin")
def delete_animation(ctx):
    content.delete_animation(ctx.conn, ctx.params[0])
    return {"ok": True}


# ---------- Administración: nombres de piezas ----------

@route("PUT", "/api/admin/piece-names", "admin")
def piece_name(ctx):
    content.set_piece_name(ctx.conn, ctx.body)
    return {"ok": True}


# ---------- Administración: instrumental ----------

@route("POST", "/api/admin/instruments", "admin")
def create_instrument(ctx):
    return {"id": content.save_instrument(ctx.conn, ctx.body)}


@route("PUT", "/api/admin/instruments/:id", "admin")
def update_instrument(ctx):
    return {"id": content.save_instrument(ctx.conn, ctx.body, ctx.params[0])}


@route("DELETE", "/api/admin/instruments/:id", "admin")
def delete_instrument(ctx):
    content.delete_instrument(ctx.conn, ctx.params[0])
    return {"ok": True}


# ---------- Administración: archivos ----------

@route("GET", "/api/admin/assets", "admin")
def list_assets(ctx):
    return {"assets": assets.list_all(ctx.conn)}


@route("POST", "/api/admin/assets", "admin")
def upload_asset(ctx):
    return assets.save_upload(ctx.conn, ctx.stream, ctx.length, ctx.query.get("filename", ""), ctx.uploads)


@route("POST", "/api/admin/assets/:id/replace", "admin")
def replace_asset(ctx):
    old = ctx.conn.execute("SELECT kind FROM assets WHERE id = ?", (ctx.params[0],)).fetchone()
    if not old:
        raise ApiError(404, "El archivo no existe.")
    new = assets.save_upload(ctx.conn, ctx.stream, ctx.length, ctx.query.get("filename", ""), ctx.uploads)
    if new["kind"] != old["kind"]:
        raise ApiError(400, "El archivo nuevo debe ser del mismo tipo que el que reemplaza.")
    assets.replace_references(ctx.conn, ctx.params[0], new["id"])
    return new


@route("DELETE", "/api/admin/assets/:id", "admin")
def delete_asset(ctx):
    assets.delete(ctx.conn, ctx.params[0], ctx.uploads)
    return {"ok": True}


# ---------- Administración: usuarios ----------

@route("GET", "/api/admin/users", "admin")
def list_users(ctx):
    rows = ctx.conn.execute("SELECT id, email, name, role FROM users ORDER BY name COLLATE NOCASE").fetchall()
    return {"users": [dict(r) for r in rows]}


@route("POST", "/api/admin/users", "admin")
def create_user(ctx):
    email = str(ctx.body.get("email", "")).strip()
    name = str(ctx.body.get("name", "")).strip()
    role = ctx.body.get("role")
    password = str(ctx.body.get("password", ""))
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", email) or not name:
        raise ApiError(400, "Escribe un nombre y un correo válidos.")
    if role not in auth.ROLES:
        raise ApiError(400, "Rol no válido.")
    if len(password) < auth.MIN_PASSWORD:
        raise ApiError(400, f"La contraseña debe tener al menos {auth.MIN_PASSWORD} caracteres.")
    if ctx.conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise ApiError(409, "Ya existe una cuenta con ese correo.")
    ctx.conn.execute(
        "INSERT INTO users (email, name, role, password_hash) VALUES (?, ?, ?, ?)",
        (email, name, role, auth.hash_password(password)),
    )
    ctx.conn.commit()
    return {"ok": True}


@route("DELETE", "/api/admin/users/:id", "admin")
def delete_user(ctx):
    if ctx.params[0] == ctx.user["id"]:
        raise ApiError(400, "No puedes eliminar tu propia cuenta.")
    ctx.conn.execute("DELETE FROM users WHERE id = ?", (ctx.params[0],))
    ctx.conn.commit()
    return {"ok": True}
