"""Entrada WSGI para publicar la plataforma en un servidor (PythonAnywhere u otro).

Reutiliza el mismo manejador de server.py: aquí solo se traduce la petición WSGI a lo que ese
manejador espera. Variables de entorno opcionales:
    PRECIMEC_DATA   carpeta de datos (por defecto, data/ junto a este archivo)
    PRECIMEC_HTTP=1 solo para probar sin HTTPS: la cookie de sesión deja de marcarse como Secure
    PRECIMEC_ARCHIVOS sitio de donde se piden los archivos que no estén en esta máquina
                    (por defecto, https://practica-precimec.vercel.app; vacío = ninguno)
"""
import io
import os
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from urllib.parse import quote

from server import ROOT, Handler, prepare

DATA = Path(os.environ.get("PRECIMEC_DATA", ROOT / "data")).resolve()
Handler.db_path = prepare(DATA)
Handler.uploads = DATA / "archivos"
Handler.secure_cookie = os.environ.get("PRECIMEC_HTTP") != "1"
# En línea, las imágenes y animaciones que no estén en data/archivos se piden al link público (Vercel).
Handler.external_assets = os.environ.get("PRECIMEC_ARCHIVOS", "https://practica-precimec.vercel.app").rstrip("/")


class WsgiHandler(Handler):
    """El manejador de server.py, alimentado desde WSGI en lugar de un socket."""

    def __init__(self, environ):  # noqa: D107 - no se llama al constructor de socket a propósito
        self.command = environ["REQUEST_METHOD"].upper()
        path = quote(environ.get("PATH_INFO", "") or "/", safe="/%")
        query = environ.get("QUERY_STRING")
        self.path = f"{path}?{query}" if query else path
        self.request_version = "HTTP/1.1"
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                self.headers[key[5:].replace("_", "-").title()] = value
        if environ.get("CONTENT_LENGTH"):
            self.headers["Content-Length"] = environ["CONTENT_LENGTH"]
        if environ.get("CONTENT_TYPE"):
            self.headers["Content-Type"] = environ["CONTENT_TYPE"]
        self.rfile = environ["wsgi.input"]
        self.wfile = io.BytesIO()
        self.close_connection = True
        self.status_line = "500 Internal Server Error"
        self.response_headers = []

    def send_response(self, code, message=None):
        self.status_line = f"{code} {HTTPStatus(code).phrase}"

    def send_header(self, keyword, value):
        self.response_headers.append((keyword, str(value)))

    def end_headers(self):
        pass

    def log_message(self, fmt, *args):
        pass


def application(environ, start_response):
    handler = WsgiHandler(environ)
    handler._dispatch()
    start_response(handler.status_line, handler.response_headers)
    return [handler.wfile.getvalue()]
