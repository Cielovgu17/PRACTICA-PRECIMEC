"""Pone los textos del instructivo sobre las imágenes hechas con IA (carpeta ia/) y guarda el PNG final.

    python ilustraciones/componer.py

Las coordenadas están en el lienzo final de 1600 × 893 (la proporción 16:9 de las imágenes).
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1600, 893
WHITE, MUTED, ORANGE, NAVY, PANEL, LINE = "#ffffff", "#b3c1d0", "#ff8a33", "#021a35", "#0d2c4f", "#3a5f86"


def text(x, y, lines, size=30, color=WHITE, weight=500, anchor="start"):
    lines = [lines] if isinstance(lines, str) else lines
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else size * 1.25:.1f}">{v}</tspan>' for i, v in enumerate(lines))
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
            f'paint-order="stroke" stroke="{NAVY}" stroke-width="6" stroke-opacity=".55" stroke-linejoin="round">{spans}</text>')


def callout(px, py, tx, ty, lines, color=WHITE, anchor="start", size=30):
    shift = 12 if anchor == "start" else -12
    return (f'<line x1="{px}" y1="{py}" x2="{tx}" y2="{ty}" stroke="{color}" stroke-width="2.5"/>'
            f'<circle cx="{px}" cy="{py}" r="7" fill="{color}"/>' + text(tx + shift, ty + size * 0.35, lines, size, color, 500, anchor))


def chip(x, y, label):
    width = len(label) * 13.8 + 32
    return (f'<rect x="{x}" y="{y}" width="{width:.0f}" height="46" rx="6" fill="{PANEL}" stroke="{LINE}" stroke-width="2"/>'
            + text(x + 16, y + 31, label, 25, MUTED, 400))


def title(main, sub):
    return text(72, 92, main, 42, WHITE, 600) + text(72, 144, sub, 30, MUTED, 400)


def note():
    return text(W - 44, H - 30, "Ilustración generada con IA, esquemática", 22, MUTED, 400, "end")


SCENES = {
    "1-1-posicion-supina": lambda: (
        callout(600, 330, 800, 150, ["Paciente boca arriba", "(posición supina)"])
        + f'<line x1="330" y1="500" x2="190" y2="615" stroke="{ORANGE}" stroke-width="2.5"/><circle cx="330" cy="500" r="7" fill="{ORANGE}"/>'
        + text(80, 652, ["Mesa ortopédica", "de tracción"], 30, ORANGE)
        + text(44, H - 30, "Ilustración generada con IA, esquemática", 20, MUTED, 400)
    ),
    "1-2-intensificador": lambda: (
        title("Usar el intensificador de imágenes", "Para vigilar la cirugía.")
        + callout(705, 240, 520, 300, ["Fluoroscopio", "(arco en C)"], ORANGE, "end")
        + note()
    ),
}


def main():
    edge = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft/Edge/Application/msedge.exe"
    with tempfile.TemporaryDirectory() as tmp:
        only = set(sys.argv[1:])
        for name, overlay in SCENES.items():
            if only and name not in only:
                continue
            background = next(p for p in (HERE / "ia" / f"{name}{ext}" for ext in (".png", ".jpg")) if p.exists())
            page = Path(tmp) / f"{name}.html"
            page.write_text(
                '<!doctype html><meta charset="utf-8">'
                '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">'
                f'<style>html,body{{margin:0;background:{NAVY}}}div{{position:relative;width:{W}px;height:{H}px}}'
                f'img,svg{{position:absolute;inset:0;width:{W}px;height:{H}px}}</style>'
                f'<div><img src="{background.as_uri()}"><svg viewBox="0 0 {W} {H}" style="font-family:\'DM Sans\',sans-serif">{overlay()}</svg></div>',
                encoding="utf-8",
            )
            target = HERE / f"{name}.png"
            subprocess.run([
                str(edge), "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={tmp}/perfil",
                "--allow-file-access-from-files", "--hide-scrollbars", "--virtual-time-budget=4000",
                f"--window-size={W},{H}", f"--screenshot={target}", page.as_uri(),
            ], check=True, timeout=90, capture_output=True)
            print(name, target.stat().st_size)


if __name__ == "__main__":
    main()
