"""Fotografía las escenas 3D de web/ilustraciones3d con Microsoft Edge y guarda los PNG en esta carpeta.

    python server.py                    (en otra ventana)
    python ilustraciones/generar3d.py [nombre de una escena]
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8000/ilustraciones3d/index.html"
SCENES = [
    "etapa1-paciente-obeso", "1-1-posicion-supina", "1-2-intensificador", "2-1-aduccion", "2-2-fijar-miembro",
    "2-3-traccion", "3-1-angulo-cuello-diafisis", "3-2-largo-del-clavo", "3-3-diametro-del-canal",
    "3-4-clavo-principal-extendido", "4-1-incision", "4-2-punto-de-entrada",
]


def main():
    edge = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft/Edge/Application/msedge.exe"
    names = sys.argv[1:] or SCENES
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            target = OUT / f"{name}.png"
            subprocess.run([
                str(edge), "--headless=new", "--no-first-run", f"--user-data-dir={tmp}/perfil",
                "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
                "--hide-scrollbars", "--virtual-time-budget=45000", "--window-size=1600,1000",
                f"--screenshot={target}", f"{BASE}?escena={name}",
            ], check=True, timeout=240, capture_output=True)
            print(name, target.stat().st_size)


if __name__ == "__main__":
    main()
