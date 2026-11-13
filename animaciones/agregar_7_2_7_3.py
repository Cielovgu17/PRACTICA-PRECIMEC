"""Se corre en el servidor en línea (PythonAnywhere), dentro de ~/instructivo:  python3 agregar_7_2_7_3.py

Registra las animaciones nuevas de los pasos 7.2 (guía intermedia de Φ4,1 mm) y 7.3 (retiro del trocar y broca de
Φ4 mm). Los archivos no se guardan aquí: están en el link de Vercel y el servidor los pide allá.
Publica solo si no había otros cambios sin publicar (para no publicar el trabajo de otra persona).
"""
import json
import sqlite3
import sys

sys.path.insert(0, ".")
from app import content  # noqa: E402

NEW = [
    {"filename": "paso19_guias_distales_KTO-PFNA - guia de 4,1 mm.glb", "stored": "71377def5a871eecbd1e87343891d795.glb",
     "size": 42846004, "sha": "7e1691e10eeb492621651d63c0c7934e893ba5042ff3be64730cfad6907fff69"},
    {"filename": "paso20_broca_distal_KTO-PFNA.glb", "stored": "739992b1187daeea2399fcf0b6c76878.glb",
     "size": 76115844, "sha": "810b57f9e32d06bd2bc25eacda2654baee249774a869ee041f200a0e66750fa5"},
]
STEP_72, STEP_73 = 41, 42

conn = sqlite3.connect("data/plataforma.db")
conn.row_factory = sqlite3.Row
pending = content.status(conn)["has_changes"]
ids = []
for a in NEW:
    row = conn.execute("SELECT id FROM assets WHERE sha256 = ?", (a["sha"],)).fetchone()
    if row:
        ids.append(row["id"])
        continue
    cur = conn.execute("INSERT INTO assets (filename, stored_name, kind, mime, size, sha256) VALUES (?, ?, 'model', ?, ?, ?)",
                       (a["filename"], a["stored"], "model/gltf-binary", a["size"], a["sha"]))
    ids.append(cur.lastrowid)
# 7.2: mismo título y ajustes, archivo nuevo (la escena se llama igual).
conn.execute("UPDATE animations SET asset_id = ? WHERE step_id = ?", (ids[0], STEP_72))
# 7.3: animación nueva.
if not conn.execute("SELECT 1 FROM animations WHERE step_id = ? AND asset_id = ?", (STEP_73, ids[1])).fetchone():
    pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM animations WHERE step_id = ?", (STEP_73,)).fetchone()[0]
    conn.execute("INSERT INTO animations (step_id, asset_id, title, description, position, settings) VALUES (?, ?, ?, '', ?, ?)",
                 (STEP_73, ids[1], "Retiro del trocar y broca de Φ4 mm por las guías", pos,
                  json.dumps({"clip": "Paso7_3_retiro_del_trocar_y_broca_de_4mm"})))
conn.execute("INSERT OR REPLACE INTO piece_names (raw, label) VALUES (?, ?)", ("Broca 4mm bloqueo distal", "Broca de Φ4 mm (bloqueo distal)"))
conn.commit()
for a, i in zip(NEW, ids):
    print(f"archivo {i}: /archivos/{i}/{a['stored']}")
if pending:
    print("HABIA CAMBIOS SIN PUBLICAR: no se publica; queda listo en el modo edición.")
else:
    print(content.publish(conn, "Administración PRECIMEC"))
