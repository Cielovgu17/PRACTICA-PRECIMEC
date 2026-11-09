"""Reemplaza el archivo de las animaciones de los pasos indicados por la versión nueva de la carpeta animaciones/.
Conserva el título y los ajustes de cada animación. Antes hace una copia de la base de datos.

    python ilustraciones/reemplazar_animaciones.py "archivo.glb" 23 24 [-- "otro.glb" 25 ...]
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import assets  # noqa: E402

DB = ROOT / "data" / "plataforma.db"


def main(args):
    shutil.copy2(DB, DB.with_name(f"plataforma-respaldo-{datetime.now():%Y%m%d-%H%M%S}.db"))
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    groups, current = [], None
    for arg in args:
        if arg == "--":
            continue
        if arg.isdigit():
            current[1].append(int(arg))
        else:
            current = (arg, [])
            groups.append(current)
    for filename, steps in groups:
        path = ROOT / "animaciones" / filename
        with open(path, "rb") as stream:
            asset = assets.save_upload(conn, stream, path.stat().st_size, filename, ROOT / "data" / "archivos")
        for step in steps:
            n = conn.execute("UPDATE animations SET asset_id = ? WHERE step_id = ?", (asset["id"], step)).rowcount
            print(f"paso {step}: {filename} (archivo {asset['id']}, {n} animación)")
    conn.commit()


if __name__ == "__main__":
    main(sys.argv[1:])
