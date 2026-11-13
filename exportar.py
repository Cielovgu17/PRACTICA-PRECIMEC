"""Crea la carpeta `publicar/` con la última versión PUBLICADA del instructivo, solo para ver.

    python exportar.py

Esa carpeta se sube tal cual a Vercel (o a Netlify). No incluye cuentas, contraseñas ni borradores:
solo los textos publicados, los archivos que esos textos usan y la página.
"""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DATA = ROOT / "data"
OUT = ROOT / "publicar"
SKIP = {"ilustraciones3d"}  # herramienta interna para fotografiar las escenas 3D

VERCEL = {
    "cleanUrls": False,
    "rewrites": [
        {"source": "/((?!api/|archivos/|css/|js/|vendor/|brand/).*)", "destination": "/index.html"},
    ],
    "headers": [
        {"source": "/api/(.*)", "headers": [{"key": "Content-Type", "value": "application/json; charset=utf-8"},
                                           {"key": "Cache-Control", "value": "no-cache"}]},
        {"source": "/(.*)", "headers": [{"key": "X-Content-Type-Options", "value": "nosniff"}]},
    ],
}

# Netlify: primero los archivos que existen, luego la página para cualquier otra ruta.
NETLIFY_REDIRECTS = "/*  /index.html  200\n"
NETLIFY_HEADERS = "/api/*\n  Content-Type: application/json; charset=utf-8\n  Cache-Control: no-cache\n"


def main():
    # python exportar.py --servidor https://USUARIO.pythonanywhere.com : el link de Vercel muestra lo del servidor
    # en línea (que tiene el modo edición) y solo guarda las imágenes y animaciones.
    server = sys.argv[sys.argv.index("--servidor") + 1].rstrip("/") if "--servidor" in sys.argv else ""
    conn = sqlite3.connect(DATA / "plataforma.db")
    row = conn.execute("SELECT snapshot, published_at FROM publications ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        raise SystemExit("Todavía no hay nada publicado: publica primero desde el modo edición.")
    snapshot, published_at = row
    document = json.loads(snapshot)

    if OUT.exists():
        shutil.rmtree(OUT)
    if server:
        # Solo los archivos pesados; la página, los textos y el modo edición los da el servidor en línea.
        OUT.mkdir()
    else:
        shutil.copytree(WEB, OUT, ignore=lambda folder, names: [n for n in names if n in SKIP])
        api = OUT / "api"
        api.mkdir()
        (api / "content").write_text(snapshot, encoding="utf-8")
        (api / "me").write_text(json.dumps({"user": None, "read_only": True}), encoding="utf-8")

    total = 0
    for asset in document.get("assets", {}).values():
        relative = asset["url"].lstrip("/")
        stored = relative.split("/")[-1]
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DATA / "archivos" / stored, target)
        total += target.stat().st_size

    vercel = VERCEL
    if server:
        # Lo que no es un archivo de aquí (página, textos, modo edición y archivos nuevos) lo responde el servidor.
        vercel = {"cleanUrls": False, "rewrites": [{"source": "/(.*)", "destination": f"{server}/$1"}]}
    (OUT / "vercel.json").write_text(json.dumps(vercel, indent=2), encoding="utf-8")
    (OUT / "_redirects").write_text(NETLIFY_REDIRECTS, encoding="utf-8")
    (OUT / "_headers").write_text(NETLIFY_HEADERS, encoding="utf-8")
    print(f"Listo: carpeta {OUT}")
    print(f"Versión publicada el {published_at} (hora UTC), {len(document.get('assets', {}))} archivos, {total / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
