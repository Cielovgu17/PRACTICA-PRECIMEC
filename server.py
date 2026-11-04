"""Servidor de la plataforma. No requiere instalar nada: solo Python 3.11 o superior.

    python server.py                  http://127.0.0.1:8000
    python server.py --port 9000 --data otra-carpeta
"""
import argparse
import json
import mimetypes
import sys
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from app import api, assets, auth, db, seed
from app.errors import ApiError

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
COOKIE = "precimec_sesion"
MAX_JSON = 2 * 1024 * 1024
UPLOAD_PATHS = ("/api/admin/assets",)

CSP = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; img-src 'self' data: blob:; media-src 'self'; "
    "connect-src 'self' blob: data:; worker-src 'self' blob:; frame-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
)
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/png", ".png")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Precimec"
    sys_version = ""
    db_path: Path
    uploads: Path
    secure_cookie = False

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")

    # ---------- Entrada ----------

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PUT(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

    def _dispatch(self):
        parts = urlsplit(self.path)
        try:
            if parts.path.startswith("/api/"):
                self._api(parts)
            elif self.command not in ("GET", "HEAD"):
                raise ApiError(405, "Método no permitido.")
            elif parts.path.startswith("/archivos/"):
                self._asset(parts.path)
            else:
                self._static(parts.path)
        except ApiError as error:
            self._discard_body()
            self._json({"error": error.message}, error.status)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            traceback.print_exc()
            self._discard_body()
            self._json({"error": "Ocurrió un error en el servidor."}, 500)

    def _discard_body(self):
        # Si no se leyó el cuerpo, la conexión no se puede reutilizar.
        self.close_connection = True

    # ---------- API ----------

    def _api(self, parts):
        fn, role, params = api.resolve(self.command, parts.path)

        if self.command != "GET" and self.headers.get("X-Requested-With") != "precimec":
            raise ApiError(403, "Petición rechazada.")

        length = int(self.headers.get("Content-Length") or 0)
        is_upload = parts.path.startswith(UPLOAD_PATHS) and self.command == "POST"
        body = {}
        if not is_upload and length:
            if length > MAX_JSON:
                raise ApiError(413, "La petición es demasiado grande.")
            try:
                body = json.loads(self.rfile.read(length))
            except ValueError:
                raise ApiError(400, "El contenido no es válido.")
            if not isinstance(body, dict):
                raise ApiError(400, "El contenido no es válido.")

        conn = db.connect(self.db_path)
        try:
            token = self._cookie_token()
            user = auth.user_from_token(conn, token)
            if role and not user:
                raise ApiError(401, "Debes iniciar sesión.")
            if role == "admin" and user["role"] != "admin":
                raise ApiError(403, "Esta sección es solo para administradores.")
            ctx = api.Ctx(
                conn=conn, user=user, body=body, query=dict(parse_qsl(parts.query)), params=params,
                uploads=self.uploads, token=token, stream=self.rfile if is_upload else None, length=length,
            )
            self._json(fn(ctx), 200, ctx.set_token)
        finally:
            conn.close()

    def _cookie_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return None
        return cookie[COOKIE].value if COOKIE in cookie else None

    def _json(self, data, status=200, set_token=None):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for token in set_token or []:
            self.send_header("Set-Cookie", self._cookie_header(token))
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _cookie_header(self, token):
        secure = "; Secure" if self.secure_cookie else ""
        if token is None:
            return f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict{secure}"
        age = auth.SESSION_DAYS * 86400
        return f"{COOKIE}={token}; Path=/; Max-Age={age}; HttpOnly; SameSite=Strict{secure}"

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CSP)

    # ---------- Archivos ----------

    def _asset(self, path):
        pieces = path.strip("/").split("/")
        if len(pieces) != 3 or not pieces[1].isdigit():
            raise ApiError(404, "Archivo no encontrado.")
        conn = db.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT stored_name, mime, filename FROM assets WHERE id = ? AND stored_name = ?",
                (int(pieces[1]), pieces[2]),
            ).fetchone()
        finally:
            conn.close()
        if not row or not (self.uploads / row["stored_name"]).is_file():
            raise ApiError(404, "Archivo no encontrado.")
        self._send_file(self.uploads / row["stored_name"], row["mime"], "private, max-age=86400")

    def _static(self, path):
        relative = path.lstrip("/")
        target = (WEB / relative).resolve() if relative else WEB / "index.html"
        if not target.is_relative_to(WEB):
            raise ApiError(404, "No encontrado.")
        if not target.is_file():
            # Las rutas sin extensión las resuelve la aplicación en el navegador.
            if Path(relative).suffix:
                raise ApiError(404, "No encontrado.")
            target = WEB / "index.html"
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send_file(target, mime, "no-cache")

    def _send_file(self, target: Path, mime: str, cache: str):
        size = target.stat().st_size
        start, end, status = 0, size - 1, 200
        requested = self.headers.get("Range", "")
        if requested.startswith("bytes=") and "," not in requested:
            first, _, last = requested[6:].partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                else:
                    start = max(size - int(last), 0)
                if start > end or start >= size:
                    raise ValueError
                end = min(end, size - 1)
                status = 206
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self._security_headers()
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(target, "rb") as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = source.read(min(assets.CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def prepare(data_dir: Path) -> Path:
    uploads = data_dir / "archivos"
    uploads.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "plataforma.db"
    db.init(db_path)
    conn = db.connect(db_path)
    try:
        seed.seed_users(conn, data_dir)
        seed.seed_content(conn)
    finally:
        conn.close()
    return db_path


def main():
    parser = argparse.ArgumentParser(description="Plataforma de instructivos quirúrgicos PRECIMEC")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--https", action="store_true", help="Marca la cookie como Secure (detrás de HTTPS)")
    args = parser.parse_args()

    data_dir = args.data.resolve()
    Handler.db_path = prepare(data_dir)
    Handler.uploads = data_dir / "archivos"
    Handler.secure_cookie = args.https

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Plataforma lista en http://{args.host}:{args.port}", flush=True)
    print(f"Cuentas iniciales: {data_dir / 'credenciales-iniciales.txt'}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
