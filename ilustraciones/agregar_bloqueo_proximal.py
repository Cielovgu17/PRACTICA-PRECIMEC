"""Agrega las animaciones del bloqueo proximal (pasos 6.1, 6.2 y 6.4) al borrador y les pone nombres en español.

    python ilustraciones/agregar_bloqueo_proximal.py

Antes hace una copia de la base de datos. Si una animación ya estaba, la reemplaza por el archivo nuevo.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import assets  # noqa: E402

DB = ROOT / "data" / "plataforma.db"
UPLOADS = ROOT / "data" / "archivos"
FILES = ROOT / "animaciones"

ANIMATIONS = [   # (paso, archivo, título, clip)
    (29, "paso10_montaje_varilla_refuerzo_KTO-PFNA.glb", "Montaje del brazo de soporte",
     "Paso10_montaje_varilla_de_refuerzo"),
    (30, "paso11_conjunto_guias_KTO-PFNA.glb", "Conjunto de guías de la hoja",
     "Paso11_conjunto_de_guias_retiro_trocar_apriete_manguito"),
    (32, "paso12_pin_guia_roscado_KTO-PFNA - centrado en la cabeza.glb", "Pin guía roscado hacia el centro de la cabeza",
     "Paso12_pin_guia_roscado_perforador"),
]

PIECES = {
    "Varilla Refuerzo Clavo Cefalomedular": "Brazo de soporte",
    "Pieza Roscada Varilla Refuerzo": "Perilla de fijación M8",
    "Blade Nail Combination Sleeve Tubo": "Manguito protector de la hoja",
    "Blade Nail Combination Sleeve Roscado": "Tuerca del conjunto de mangas",
    "Drill Sleeve 3 2mm 92211601 92042001": "Casquillo para broca de 3,2 mm",
    "Trocar 3 2mm 92211701 modelado": "Trocar de 3,2 mm",
    "Pin guia roscado 32x400mm": "Pin guía roscado de 3,2 mm",
    "Perforador portabrocas": "Portabrocas del perforador",
    "Perforador nariz": "Perforador quirúrgico",
    "Perforador cabezal": "Perforador quirúrgico",
    "Perforador carcasa empunadura": "Perforador quirúrgico",
    "Perforador gatillo": "Perforador quirúrgico",
    "Perforador bateria": "Perforador quirúrgico",
    "Llave del portabrocas": "Llave del portabrocas",
    "Indicador 10 15mm": "Distancia de 10 a 15 mm al borde de la cabeza",
    "Abertura canal medular": "Abertura del canal medular",
}


def main():
    backup = DB.with_name("plataforma-respaldo-antes-bloqueo-proximal.db")
    shutil.copy2(DB, backup)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    for step, filename, title, clip in ANIMATIONS:
        path = FILES / filename
        with open(path, "rb") as stream:
            asset = assets.save_upload(conn, stream, path.stat().st_size, filename, UPLOADS)
        settings = '{"clip": "%s"}' % clip
        old = conn.execute("SELECT id FROM animations WHERE step_id = ?", (step,)).fetchone()
        if old:
            conn.execute("UPDATE animations SET asset_id = ?, title = ?, settings = ? WHERE id = ?",
                         (asset["id"], title, settings, old["id"]))
        else:
            conn.execute("INSERT INTO animations (step_id, asset_id, title, description, position, settings) "
                         "VALUES (?, ?, ?, '', 0, ?)", (step, asset["id"], title, settings))
        print(f"paso {step}: {filename} (archivo {asset['id']})")
    for raw, label in PIECES.items():
        conn.execute("INSERT INTO piece_names (raw, label) VALUES (?, ?) "
                     "ON CONFLICT(raw) DO UPDATE SET label = excluded.label", (raw, label))
    conn.commit()
    print("nombres en español:", len(PIECES), "· copia de seguridad:", backup.name)


if __name__ == "__main__":
    main()
