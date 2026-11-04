"""Archivos: modelos 3D, imágenes, documentos y video.

Cada archivo se guarda una sola vez (se identifica por su huella SHA-256), así un
mismo instrumento se reutiliza en varios pasos sin cargar el archivo de nuevo.
"""
import hashlib
import json
import secrets
from pathlib import Path

from .errors import ApiError

MAX_UPLOAD = 400 * 1024 * 1024
CHUNK = 1024 * 1024

# Solo formatos que el navegador muestra sin ejecutar código. SVG y HTML quedan fuera a propósito.
ALLOWED = {
    ".stl": ("model", "model/stl"),
    ".glb": ("model", "model/gltf-binary"),
    ".gltf": ("model", "model/gltf+json"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".webp": ("image", "image/webp"),
    ".pdf": ("document", "application/pdf"),
    ".mp4": ("video", "video/mp4"),
    ".webm": ("video", "video/webm"),
}

# Dónde se puede usar un archivo dentro del borrador.
REFERENCES = (
    ("technique", "cover_asset_id"),
    ("technique", "model_asset_id"),
    ("instruments", "image_asset_id"),
    ("instruments", "model_asset_id"),
    ("step_media", "asset_id"),
    ("animations", "asset_id"),
)


def row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "kind": row["kind"],
        "size": row["size"],
        "url": f"/archivos/{row['id']}/{row['stored_name']}",
    }


def save_upload(conn, stream, length: int, filename: str, uploads: Path) -> dict:
    """Guarda el cuerpo de la petición; si el archivo ya existe, devuelve el existente."""
    filename = Path(filename.replace("\\", "/")).name.strip()
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in ALLOWED:
        raise ApiError(400, "Formato no permitido. Usa STL, GLB, GLTF, PNG, JPG, WEBP, PDF, MP4 o WEBM.")
    if length <= 0:
        raise ApiError(400, "El archivo está vacío.")
    if length > MAX_UPLOAD:
        raise ApiError(413, "El archivo supera el máximo de 400 MB.")

    kind, mime = ALLOWED[suffix]
    stored = secrets.token_hex(16) + suffix
    target = uploads / stored
    digest = hashlib.sha256()
    remaining = length
    try:
        with open(target, "wb") as out:
            while remaining:
                chunk = stream.read(min(CHUNK, remaining))
                if not chunk:
                    raise ApiError(400, "La carga se interrumpió. Intenta de nuevo.")
                digest.update(chunk)
                out.write(chunk)
                remaining -= len(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    sha = digest.hexdigest()
    existing = conn.execute("SELECT * FROM assets WHERE sha256 = ?", (sha,)).fetchone()
    if existing:
        target.unlink(missing_ok=True)
        return {**row_to_dict(existing), "reused": True}

    cur = conn.execute(
        "INSERT INTO assets (filename, stored_name, kind, mime, size, sha256) VALUES (?, ?, ?, ?, ?, ?)",
        (filename, stored, kind, mime, length, sha),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {**row_to_dict(row), "reused": False}


def draft_uses(conn, asset_id: int) -> int:
    return sum(
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (asset_id,)).fetchone()[0]
        for table, column in REFERENCES
    )


def published_ids(conn) -> set[int]:
    row = conn.execute("SELECT snapshot FROM publications ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return set()
    return {int(key) for key in json.loads(row["snapshot"]).get("assets", {})}


def list_all(conn) -> list[dict]:
    published = published_ids(conn)
    rows = conn.execute("SELECT * FROM assets ORDER BY id DESC").fetchall()
    return [
        {**row_to_dict(r), "uses": draft_uses(conn, r["id"]), "published": r["id"] in published}
        for r in rows
    ]


def replace_references(conn, old_id: int, new_id: int) -> None:
    """Apunta el borrador al archivo nuevo. Lo publicado no cambia hasta publicar de nuevo."""
    for table, column in REFERENCES:
        conn.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (new_id, old_id))
    conn.commit()


def delete(conn, asset_id: int, uploads: Path) -> None:
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        raise ApiError(404, "El archivo no existe.")
    uses = draft_uses(conn, asset_id)
    if uses:
        raise ApiError(409, f"No se puede eliminar: el borrador lo usa en {uses} lugar(es).")
    if asset_id in published_ids(conn):
        raise ApiError(409, "No se puede eliminar: la versión publicada todavía lo usa. Publica primero.")
    conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    conn.commit()
    (uploads / row["stored_name"]).unlink(missing_ok=True)
