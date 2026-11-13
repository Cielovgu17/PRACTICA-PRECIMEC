"""Crea instructivo-en-linea.zip con todo lo que el servidor en línea necesita, incluidos los datos actuales.

    python empaquetar.py

El zip va a PythonAnywhere (ver SUBIR-EN-LINEA.md). Lleva el programa, una copia consistente de la base de
datos y el archivo de la cuenta admin; no lleva copias de seguridad, pruebas ni las imágenes y animaciones
(esas siguen en el link público de Vercel).
"""
import sqlite3
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT.parent / "instructivo-en-linea.zip"
CODE = ["server.py", "wsgi.py", "app", "web"]
SKIP_DIRS = {"__pycache__", "ilustraciones3d"}


def add_tree(archive, path, arcname):
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if child.name not in SKIP_DIRS:
                add_tree(archive, child, f"{arcname}/{child.name}")
    else:
        archive.write(path, arcname)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "plataforma.db"
        source = sqlite3.connect(ROOT / "data" / "plataforma.db")
        copy = sqlite3.connect(snapshot)
        source.backup(copy)
        copy.close()
        source.close()
        with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in CODE:
                add_tree(archive, ROOT / name, f"instructivo/{name}")
            archive.write(snapshot, "instructivo/data/plataforma.db")
            archive.write(ROOT / "data" / "credenciales-iniciales.txt", "instructivo/data/credenciales-iniciales.txt")
            # Las imágenes y animaciones no van en el zip (pesan más de 1 GB y la cuenta gratis tiene 512 MB):
            # el servidor las pide al link público de Vercel (ver PRECIMEC_ARCHIVOS en wsgi.py).
    print(f"Listo: {TARGET} ({TARGET.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
