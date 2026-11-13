"""Contenido educativo: técnica, pasos, instrumental, animaciones y publicación.

El administrador edita siempre el borrador (las tablas). Al publicar se guarda una
copia completa en JSON, que es lo único que ven las personas de consulta.
"""
import json

from . import assets
from .errors import ApiError

STEP_FIELDS = ("title", "objective", "description", "procedure", "observations", "recommendations")
INSTRUMENT_FIELDS = ("name", "description", "function")
TECHNIQUE_FIELDS = ("company", "platform_name", "name", "intro", "system_info")
MAX_TEXT = 200000  # textos largos pegados de otro documento (unas 60 páginas)
MAX_TITLE = 200


def _text(data: dict, field: str, required: bool = False) -> str:
    value = data.get(field, "")
    if not isinstance(value, str):
        raise ApiError(400, f"El campo {field} no es válido.")
    value = value.strip()
    if required and not value:
        raise ApiError(400, "Este nombre no puede quedar vacío.")
    limit = MAX_TITLE if field in ("title", "name", "company", "platform_name") else MAX_TEXT
    if len(value) > limit:
        raise ApiError(400, f"El texto supera el máximo de {limit} caracteres.")
    return value


def _exists(conn, table: str, row_id: int, message: str):
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if not row:
        raise ApiError(404, message)
    return row


def _asset_ref(conn, value, kind: str | None = None):
    """Valida una referencia opcional a un archivo y su tipo."""
    if value in (None, ""):
        return None
    row = conn.execute("SELECT id, kind FROM assets WHERE id = ?", (value,)).fetchone()
    if not row:
        raise ApiError(400, "El archivo seleccionado no existe.")
    if kind and row["kind"] != kind:
        raise ApiError(400, "El tipo de archivo no corresponde a este campo.")
    return row["id"]


# ---------- Documento completo ----------

def build_document(conn) -> dict:
    technique = dict(conn.execute("SELECT * FROM technique WHERE id = 1").fetchone())
    technique["is_sample"] = bool(technique["is_sample"])

    links: dict[int, list[int]] = {}
    for r in conn.execute("SELECT step_id, instrument_id FROM step_instruments ORDER BY position"):
        links.setdefault(r["step_id"], []).append(r["instrument_id"])
    media: dict[int, list[dict]] = {}
    for r in conn.execute("SELECT * FROM step_media ORDER BY position, id"):
        media.setdefault(r["step_id"], []).append(dict(r))
    animations: dict[int, list[dict]] = {}
    for r in conn.execute("SELECT * FROM animations ORDER BY position, id"):
        animations.setdefault(r["step_id"], []).append({**dict(r), "settings": json.loads(r["settings"] or "{}")})

    nodes = {}
    roots = []
    rows = conn.execute("SELECT * FROM steps ORDER BY position, id").fetchall()
    for r in rows:
        nodes[r["id"]] = {
            **dict(r),
            "is_sample": bool(r["is_sample"]),
            "instrument_ids": links.get(r["id"], []),
            "media": media.get(r["id"], []),
            "animations": animations.get(r["id"], []),
            "children": [],
        }
    for r in rows:
        if r["parent_id"] is None:
            roots.append(nodes[r["id"]])
        elif r["parent_id"] in nodes:
            nodes[r["parent_id"]]["children"].append(nodes[r["id"]])

    instruments = [
        {**dict(r), "is_verified": bool(r["is_verified"])}
        for r in conn.execute("SELECT * FROM instruments ORDER BY name COLLATE NOCASE")
    ]

    used = {technique["cover_asset_id"], technique["model_asset_id"]}
    for i in instruments:
        used |= {i["image_asset_id"], i["model_asset_id"]}
    for group in (media, animations):
        for items in group.values():
            used |= {item["asset_id"] for item in items}
    used.discard(None)
    asset_map = {}
    if used:
        marks = ",".join("?" * len(used))
        for r in conn.execute(f"SELECT * FROM assets WHERE id IN ({marks})", tuple(used)):
            asset_map[str(r["id"])] = assets.row_to_dict(r)

    document = {"technique": technique, "steps": roots, "instruments": instruments, "assets": asset_map}
    names = {r["raw"]: r["label"] for r in conn.execute("SELECT raw, label FROM piece_names")}
    if names:
        document["piece_names"] = names
    return document


def _serialize(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def latest_publication(conn):
    return conn.execute("SELECT * FROM publications ORDER BY id DESC LIMIT 1").fetchone()


def published_document(conn) -> dict:
    row = latest_publication(conn)
    if not row:
        raise ApiError(404, "Todavía no hay una versión publicada.")
    return json.loads(row["snapshot"])


def publish(conn, author: str) -> dict:
    document = _serialize(build_document(conn))
    conn.execute("INSERT INTO publications (snapshot, published_by) VALUES (?, ?)", (document, author))
    conn.commit()
    return status(conn)


def status(conn) -> dict:
    row = latest_publication(conn)
    return {
        "has_changes": row is None or row["snapshot"] != _serialize(build_document(conn)),
        "published_at": row["published_at"] if row else None,
        "published_by": row["published_by"] if row else None,
    }


# ---------- Técnica ----------

def update_technique(conn, data: dict) -> None:
    values = {f: _text(data, f, required=f in ("company", "platform_name", "name")) for f in TECHNIQUE_FIELDS}
    conn.execute(
        """UPDATE technique SET company = ?, platform_name = ?, name = ?, intro = ?, system_info = ?,
           cover_asset_id = ?, model_asset_id = ?, is_sample = ? WHERE id = 1""",
        (
            *[values[f] for f in TECHNIQUE_FIELDS],
            _asset_ref(conn, data.get("cover_asset_id"), "image"),
            _asset_ref(conn, data.get("model_asset_id"), "model"),
            1 if data.get("is_sample") else 0,
        ),
    )
    conn.commit()


# ---------- Pasos y subpasos ----------

def _next_position(conn, parent_id) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM steps WHERE parent_id IS ?", (parent_id,)
    ).fetchone()
    return row[0]


def _renumber(conn, parent_id) -> None:
    rows = conn.execute("SELECT id FROM steps WHERE parent_id IS ? ORDER BY position, id", (parent_id,)).fetchall()
    for index, row in enumerate(rows):
        conn.execute("UPDATE steps SET position = ? WHERE id = ?", (index, row["id"]))


def create_step(conn, data: dict) -> int:
    parent_id = data.get("parent_id")
    if parent_id is not None:
        parent = _exists(conn, "steps", parent_id, "El paso superior no existe.")
        if parent["parent_id"] is not None:
            raise ApiError(400, "Un subpaso no puede tener subpasos propios.")
    title = _text(data, "title", required=True)
    cur = conn.execute(
        "INSERT INTO steps (parent_id, position, title) VALUES (?, ?, ?)",
        (parent_id, _next_position(conn, parent_id), title),
    )
    conn.commit()
    return cur.lastrowid


def update_step(conn, step_id: int, data: dict) -> None:
    _exists(conn, "steps", step_id, "El paso no existe.")
    values = {f: _text(data, f, required=f == "title") for f in STEP_FIELDS}
    conn.execute(
        """UPDATE steps SET title = ?, objective = ?, description = ?, procedure = ?,
           observations = ?, recommendations = ?, is_sample = ? WHERE id = ?""",
        (*[values[f] for f in STEP_FIELDS], 1 if data.get("is_sample") else 0, step_id),
    )
    conn.commit()


def delete_step(conn, step_id: int) -> None:
    row = _exists(conn, "steps", step_id, "El paso no existe.")
    conn.execute("DELETE FROM steps WHERE id = ?", (step_id,))
    _renumber(conn, row["parent_id"])
    conn.commit()


def move_step(conn, step_id: int, data: dict) -> None:
    """Sube o baja un paso entre sus hermanos, o lleva un subpaso a otro paso."""
    row = _exists(conn, "steps", step_id, "El paso no existe.")
    if "parent_id" in data:
        new_parent = data["parent_id"]
        if conn.execute("SELECT 1 FROM steps WHERE parent_id = ?", (step_id,)).fetchone() and new_parent is not None:
            raise ApiError(400, "Un paso con subpasos no puede convertirse en subpaso.")
        if new_parent is not None:
            target = _exists(conn, "steps", new_parent, "El paso de destino no existe.")
            if target["parent_id"] is not None or new_parent == step_id:
                raise ApiError(400, "Ese destino no es válido.")
        conn.execute(
            "UPDATE steps SET parent_id = ?, position = ? WHERE id = ?",
            (new_parent, _next_position(conn, new_parent), step_id),
        )
        _renumber(conn, row["parent_id"])
        conn.commit()
        return
    direction = data.get("direction")
    if direction not in ("up", "down"):
        raise ApiError(400, "Dirección no válida.")
    _swap(conn, "steps", step_id, row["position"], direction, "parent_id IS ?", (row["parent_id"],))
    conn.commit()


def _swap(conn, table: str, row_id: int, position: int, direction: str, scope: str, args: tuple) -> None:
    op, order = ("<", "DESC") if direction == "up" else (">", "ASC")
    other = conn.execute(
        f"SELECT id, position FROM {table} WHERE {scope} AND position {op} ? ORDER BY position {order} LIMIT 1",
        (*args, position),
    ).fetchone()
    if other:
        conn.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (other["position"], row_id))
        conn.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (position, other["id"]))


def set_step_instruments(conn, step_id: int, ids: list) -> None:
    _exists(conn, "steps", step_id, "El paso no existe.")
    conn.execute("DELETE FROM step_instruments WHERE step_id = ?", (step_id,))
    for index, instrument_id in enumerate(ids):
        _exists(conn, "instruments", instrument_id, "El instrumento no existe.")
        conn.execute(
            "INSERT INTO step_instruments (step_id, instrument_id, position) VALUES (?, ?, ?)",
            (step_id, instrument_id, index),
        )
    conn.commit()


# ---------- Imágenes, documentos y video de un paso ----------

def add_media(conn, step_id: int, data: dict) -> None:
    _exists(conn, "steps", step_id, "El paso no existe.")
    asset_id = _asset_ref(conn, data.get("asset_id"))
    if asset_id is None:
        raise ApiError(400, "Selecciona un archivo.")
    position = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM step_media WHERE step_id = ?", (step_id,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO step_media (step_id, asset_id, caption, position) VALUES (?, ?, ?, ?)",
        (step_id, asset_id, _text(data, "caption"), position),
    )
    conn.commit()


def delete_media(conn, media_id: int) -> None:
    conn.execute("DELETE FROM step_media WHERE id = ?", (media_id,))
    conn.commit()


# ---------- Animaciones ----------

def add_animation(conn, step_id: int, data: dict) -> None:
    _exists(conn, "steps", step_id, "El paso no existe.")
    asset_id = _asset_ref(conn, data.get("asset_id"), "model")
    if asset_id is None:
        raise ApiError(400, "Selecciona un modelo 3D.")
    position = conn.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM animations WHERE step_id = ?", (step_id,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO animations (step_id, asset_id, title, description, position) VALUES (?, ?, ?, ?, ?)",
        (step_id, asset_id, _text(data, "title", required=True), _text(data, "description"), position),
    )
    conn.commit()


def update_animation(conn, animation_id: int, data: dict) -> None:
    row = _exists(conn, "animations", animation_id, "La animación no existe.")
    asset_id = _asset_ref(conn, data.get("asset_id"), "model")
    if asset_id is None:
        raise ApiError(400, "Selecciona un modelo 3D.")
    # Con otro archivo, la escena, el recorte y las piezas ocultas del anterior ya no aplican.
    settings = row["settings"] if asset_id == row["asset_id"] else "{}"
    conn.execute(
        "UPDATE animations SET asset_id = ?, title = ?, description = ?, settings = ? WHERE id = ?",
        (asset_id, _text(data, "title", required=True), _text(data, "description"), settings, animation_id),
    )
    conn.commit()


def update_animation_settings(conn, animation_id: int, data: dict) -> None:
    """Qué escena del archivo se muestra, qué tramo se reproduce y qué piezas se ocultan."""
    _exists(conn, "animations", animation_id, "La animación no existe.")
    settings = {}
    clip = data.get("clip")
    if clip is not None:
        if not isinstance(clip, str) or len(clip) > MAX_TITLE:
            raise ApiError(400, "La escena no es válida.")
        settings["clip"] = clip
    for key in ("start", "end"):
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, (int, float)) or value < 0 or value > 36000:
            raise ApiError(400, "El tiempo de la animación no es válido.")
        settings[key] = round(float(value), 2)
    if "start" in settings and "end" in settings and settings["end"] <= settings["start"]:
        raise ApiError(400, "El final debe ser después del inicio.")
    hidden = data.get("hidden")
    if hidden is not None:
        if not isinstance(hidden, list) or len(hidden) > 500 or not all(isinstance(h, str) and len(h) <= MAX_TITLE for h in hidden):
            raise ApiError(400, "La lista de piezas no es válida.")
        settings["hidden"] = sorted(set(hidden))
    conn.execute("UPDATE animations SET settings = ? WHERE id = ?", (json.dumps(settings, ensure_ascii=False), animation_id))
    conn.commit()


def move_animation(conn, animation_id: int, direction: str) -> None:
    row = _exists(conn, "animations", animation_id, "La animación no existe.")
    if direction not in ("up", "down"):
        raise ApiError(400, "Dirección no válida.")
    _swap(conn, "animations", animation_id, row["position"], direction, "step_id = ?", (row["step_id"],))
    conn.commit()


def delete_animation(conn, animation_id: int) -> None:
    conn.execute("DELETE FROM animations WHERE id = ?", (animation_id,))
    conn.commit()


# ---------- Nombres de las piezas de los modelos 3D ----------

def set_piece_name(conn, data: dict) -> None:
    """Nombre que se muestra para una pieza del modelo. Vacío vuelve al nombre del archivo."""
    raw = data.get("raw")
    label = data.get("label", "")
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_TITLE:
        raise ApiError(400, "La pieza no es válida.")
    if not isinstance(label, str) or len(label.strip()) > MAX_TITLE:
        raise ApiError(400, f"El nombre supera el máximo de {MAX_TITLE} caracteres.")
    label = label.strip()
    if label and label != raw:
        conn.execute(
            "INSERT INTO piece_names (raw, label) VALUES (?, ?) "
            "ON CONFLICT(raw) DO UPDATE SET label = excluded.label",
            (raw, label),
        )
    else:
        conn.execute("DELETE FROM piece_names WHERE raw = ?", (raw,))
    conn.commit()


# ---------- Instrumental ----------

def save_instrument(conn, data: dict, instrument_id: int | None = None) -> int:
    values = {f: _text(data, f, required=f == "name") for f in INSTRUMENT_FIELDS}
    image = _asset_ref(conn, data.get("image_asset_id"), "image")
    model = _asset_ref(conn, data.get("model_asset_id"), "model")
    verified = 1 if data.get("is_verified") else 0
    if instrument_id is None:
        cur = conn.execute(
            """INSERT INTO instruments (name, description, function, image_asset_id, model_asset_id, is_verified)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (*[values[f] for f in INSTRUMENT_FIELDS], image, model, verified),
        )
        conn.commit()
        return cur.lastrowid
    _exists(conn, "instruments", instrument_id, "El instrumento no existe.")
    conn.execute(
        """UPDATE instruments SET name = ?, description = ?, function = ?, image_asset_id = ?,
           model_asset_id = ?, is_verified = ? WHERE id = ?""",
        (*[values[f] for f in INSTRUMENT_FIELDS], image, model, verified, instrument_id),
    )
    conn.commit()
    return instrument_id


def delete_instrument(conn, instrument_id: int) -> None:
    conn.execute("DELETE FROM instruments WHERE id = ?", (instrument_id,))
    conn.commit()
