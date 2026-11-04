"""Pruebas de la API contra un servidor real con datos temporales.

    python -m unittest discover -s tests -v
"""
import json
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None, raw=None, headers=True):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = urllib.request.Request(BASE + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if headers:
            request.add_header("X-Requested-With", "precimec")
        try:
            with self.opener.open(request) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"null")


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.proc = cls._start()
        lines = (Path(cls.tmp.name) / "credenciales-iniciales.txt").read_text(encoding="utf-8").splitlines()
        cls.accounts = {}
        for i, line in enumerate(lines):
            if line.startswith("Rol: "):
                cls.accounts[line[5:]] = (lines[i + 1][8:], lines[i + 2][12:])
        cls.admin = Client()
        status, _ = cls._login(cls.admin, "admin")
        assert status == 200

    @classmethod
    def _start(cls):
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "server.py"), "--port", str(PORT), "--data", cls.tmp.name],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            try:
                urllib.request.urlopen(BASE + "/api/me")
                return proc
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("El servidor no arrancó")

    @classmethod
    def _login(cls, client, role):
        email, password = cls.accounts[role]
        return client.call("POST", "/api/login", {"email": email, "password": password})

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait()
        cls.tmp.cleanup()

    def test_anonymous_cannot_use_admin(self):
        self.assertEqual(Client().call("GET", "/api/admin/draft")[0], 401)
        self.assertEqual(Client().call("POST", "/api/admin/steps", {"title": "X"})[0], 401)

    def test_consulta_cannot_use_admin(self):
        client = Client()
        self.assertEqual(self._login(client, "consulta")[0], 200)
        self.assertEqual(client.call("GET", "/api/admin/draft")[0], 403)
        self.assertEqual(client.call("POST", "/api/admin/publish")[0], 403)
        self.assertEqual(client.call("GET", "/api/content?version=draft")[0], 403)

    def test_wrong_password_rejected(self):
        status, body = Client().call("POST", "/api/login", {"email": "nadie@x.co", "password": "mala"})
        self.assertEqual(status, 401)
        self.assertIn("error", body)

    def test_write_without_custom_header_rejected(self):
        self.assertEqual(self.admin.call("POST", "/api/admin/steps", {"title": "X"}, headers=False)[0], 403)

    def test_seed_is_published_and_marked_as_sample(self):
        status, doc = Client().call("GET", "/api/content")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(doc["steps"]), 9)
        self.assertEqual(doc["steps"][0]["children"][0]["title"], "Preparación de la mesa quirúrgica")
        self.assertTrue(doc["technique"]["is_sample"])

    def test_draft_stays_private_until_published(self):
        status, created = self.admin.call("POST", "/api/admin/steps", {"title": "Paso de prueba privado"})
        self.assertEqual(status, 200)
        titles = lambda doc: [s["title"] for s in doc["steps"]]
        self.assertNotIn("Paso de prueba privado", titles(Client().call("GET", "/api/content")[1]))
        self.assertTrue(self.admin.call("GET", "/api/admin/draft")[1]["status"]["has_changes"])
        self.admin.call("POST", "/api/admin/publish")
        self.assertIn("Paso de prueba privado", titles(Client().call("GET", "/api/content")[1]))
        self.assertFalse(self.admin.call("GET", "/api/admin/draft")[1]["status"]["has_changes"])
        self.admin.call("DELETE", f"/api/admin/steps/{created['id']}")
        self.admin.call("POST", "/api/admin/publish")

    def test_reorder_and_nesting(self):
        steps = self.admin.call("GET", "/api/admin/draft")[1]["document"]["steps"]
        first, second = steps[0]["id"], steps[1]["id"]
        self.admin.call("POST", f"/api/admin/steps/{second}/move", {"direction": "up"})
        steps = self.admin.call("GET", "/api/admin/draft")[1]["document"]["steps"]
        self.assertEqual(steps[0]["id"], second)
        self.admin.call("POST", f"/api/admin/steps/{second}/move", {"direction": "down"})
        steps = self.admin.call("GET", "/api/admin/draft")[1]["document"]["steps"]
        self.assertEqual(steps[0]["id"], first)
        sub = steps[0]["children"][0]["id"]
        self.assertEqual(self.admin.call("POST", "/api/admin/steps", {"parent_id": sub, "title": "No"})[0], 400)
        self.assertEqual(self.admin.call("POST", f"/api/admin/steps/{first}/move", {"parent_id": second})[0], 400)

    def test_step_edit_requires_title(self):
        step = self.admin.call("GET", "/api/admin/draft")[1]["document"]["steps"][0]
        self.assertEqual(self.admin.call("PUT", f"/api/admin/steps/{step['id']}", {"title": "   "})[0], 400)

    def test_upload_dedupes_and_blocks_bad_files(self):
        stl = b"solid prueba\nendsolid prueba\n"
        upload = lambda name, raw=stl: self.admin.call("POST", f"/api/admin/assets?filename={name}", raw=raw)
        status, first = upload("pieza.stl")
        self.assertEqual(status, 200)
        self.assertFalse(first["reused"])
        status, again = upload("copia.stl")
        self.assertTrue(again["reused"])
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(upload("malo.html", b"<script>")[0], 400)
        self.assertEqual(upload("malo.svg", b"<svg>")[0], 400)
        self.assertEqual(urllib.request.urlopen(BASE + first["url"]).status, 200)

        step = self.admin.call("GET", "/api/admin/draft")[1]["document"]["steps"][0]
        payload = {"asset_id": first["id"], "title": "Animación de prueba"}
        self.assertEqual(self.admin.call("POST", f"/api/admin/steps/{step['id']}/animations", payload)[0], 200)
        self.assertEqual(self.admin.call("DELETE", f"/api/admin/assets/{first['id']}")[0], 409)

        status, new = upload("nueva.stl", stl + b"\n")
        status, replaced = self.admin.call("POST", f"/api/admin/assets/{first['id']}/replace?filename=nueva2.stl", raw=stl + b"\n\n")
        self.assertEqual(status, 200)
        doc = self.admin.call("GET", "/api/admin/draft")[1]["document"]
        self.assertEqual(doc["steps"][0]["animations"][-1]["asset_id"], replaced["id"])
        self.admin.call("DELETE", f"/api/admin/animations/{doc['steps'][0]['animations'][-1]['id']}")

    def test_instrument_reused_across_steps(self):
        doc = self.admin.call("GET", "/api/admin/draft")[1]["document"]
        instrument = doc["instruments"][0]["id"]
        a, b = doc["steps"][0]["id"], doc["steps"][1]["id"]
        for step in (a, b):
            self.assertEqual(self.admin.call("PUT", f"/api/admin/steps/{step}/instruments", {"ids": [instrument]})[0], 200)
        doc = self.admin.call("GET", "/api/admin/draft")[1]["document"]
        self.assertEqual(doc["steps"][0]["instrument_ids"], [instrument])
        self.assertEqual(doc["steps"][1]["instrument_ids"], [instrument])
        for step in (a, b):
            self.admin.call("PUT", f"/api/admin/steps/{step}/instruments", {"ids": []})

    def test_progress_persists_per_user(self):
        client = Client()
        self._login(client, "consulta")
        self.assertEqual(client.call("PUT", "/api/progress", {"done": [1, 2], "last_step_id": 2})[0], 200)
        again = Client()
        self._login(again, "consulta")
        progress = again.call("GET", "/api/progress")[1]
        self.assertEqual(sorted(progress["done"]), [1, 2])
        self.assertEqual(progress["last_step_id"], 2)

    def test_piece_names_stay_in_draft_until_published(self):
        payload = {"raw": "Hoja helicoidal", "label": "Hoja del sistema"}
        self.assertEqual(Client().call("PUT", "/api/admin/piece-names", payload)[0], 401)
        self.assertEqual(self.admin.call("PUT", "/api/admin/piece-names", payload)[0], 200)
        doc = self.admin.call("GET", "/api/admin/draft")[1]["document"]
        self.assertEqual(doc["piece_names"]["Hoja helicoidal"], "Hoja del sistema")
        self.assertNotIn("piece_names", Client().call("GET", "/api/content")[1])
        self.admin.call("PUT", "/api/admin/piece-names", {"raw": "Hoja helicoidal", "label": ""})
        self.assertNotIn("piece_names", self.admin.call("GET", "/api/admin/draft")[1]["document"])

    def test_path_traversal_blocked(self):
        for path in ("/..%2fserver.py", "/../server.py", "/archivos/1/..%2f..%2fplataforma.db"):
            try:
                body = urllib.request.urlopen(BASE + path).read()
                self.assertNotIn(b"ThreadingHTTPServer", body)
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 404)

    def test_data_survives_restart(self):
        title = "Paso que debe sobrevivir"
        _, created = self.admin.call("POST", "/api/admin/steps", {"title": title})
        type(self).proc.terminate()
        type(self).proc.wait()
        type(self).proc = self._start()
        doc = self.admin.call("GET", "/api/admin/draft")[1]["document"]
        self.assertIn(title, [s["title"] for s in doc["steps"]])
        self.admin.call("DELETE", f"/api/admin/steps/{created['id']}")


if __name__ == "__main__":
    unittest.main()
