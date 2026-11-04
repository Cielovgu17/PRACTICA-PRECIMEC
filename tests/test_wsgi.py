"""Prueba la entrada WSGI (la que usa PythonAnywhere) con una copia temporal de los datos.

    python -m unittest tests.test_wsgi -v
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parent.parent


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class WsgiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["PRECIMEC_DATA"] = cls.tmp.name
        os.environ["PRECIMEC_HTTP"] = "1"
        sys.path.insert(0, str(ROOT))
        import wsgi  # noqa: E402 - depende de las variables de entorno de arriba

        cls.server = make_server("127.0.0.1", 0, wsgi.application, handler_class=Quiet)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        text = (Path(cls.tmp.name) / "credenciales-iniciales.txt").read_text(encoding="utf-8").splitlines()
        cls.email = text[text.index("Rol: admin") + 1][8:]
        cls.password = text[text.index("Rol: admin") + 2][12:]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def client(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, opener, method, path, body=None, raw=None, headers=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("X-Requested-With", "precimec")
        request.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with opener.open(request) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers

    def test_page_and_routes(self):
        opener = self.client()
        status, body, headers = self.call(opener, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"<div id=\"app\">", body)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(self.call(opener, "GET", "/editar/paso/3")[0], 200)
        self.assertEqual(self.call(opener, "GET", "/js/main.js")[0], 200)
        self.assertEqual(self.call(opener, "GET", "/nada.js")[0], 404)
        self.assertEqual(self.call(opener, "GET", "/..%2fserver.py")[0], 404)

    def test_edit_flow_persists(self):
        opener = self.client()
        self.assertEqual(self.call(opener, "PUT", "/api/admin/technique", {})[0], 401)
        status, _, headers = self.call(opener, "POST", "/api/login", {"email": self.email, "password": self.password})
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        doc = json.loads(self.call(opener, "GET", "/api/admin/draft")[1])["document"]
        step = doc["steps"][0]
        fields = {k: step[k] for k in ("title", "objective", "description", "procedure", "observations", "recommendations", "is_sample")}
        self.assertEqual(self.call(opener, "PUT", f"/api/admin/steps/{step['id']}", {**fields, "objective": "Editado en línea"})[0], 200)
        self.assertEqual(self.call(opener, "POST", "/api/admin/publish")[0], 200)
        public = json.loads(self.call(self.client(), "GET", "/api/content")[1])
        self.assertEqual(public["steps"][0]["objective"], "Editado en línea")

        stl = b"solid t\nendsolid t\n" * 2000
        status, body, _ = self.call(opener, "POST", "/api/admin/assets?filename=pieza.stl", raw=stl,
                                    headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(status, 200)
        url = json.loads(body)["url"]
        status, part, headers = self.call(opener, "GET", url, headers={"Range": "bytes=0-9"})
        self.assertEqual(status, 206)
        self.assertEqual(part, stl[:10])
        self.assertEqual(headers["Content-Range"], f"bytes 0-9/{len(stl)}")


if __name__ == "__main__":
    unittest.main()
