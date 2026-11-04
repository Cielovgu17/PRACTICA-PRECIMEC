"""Pone los textos del instructivo sobre las imágenes hechas con IA (carpeta ia/) y guarda el PNG final.

    python ilustraciones/componer.py                     (todas)
    python ilustraciones/componer.py 1-1-posicion-supina  (solo una)

Cada escena dice qué imagen usa de fondo y en qué lienzo se dibuja; las coordenadas van en ese lienzo.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WHITE, MUTED, ORANGE, NAVY, PANEL, LINE = "#ffffff", "#b3c1d0", "#ff8a33", "#021a35", "#0d2c4f", "#3a5f86"


def text(x, y, lines, size=30, color=WHITE, weight=500, anchor="start"):
    lines = [lines] if isinstance(lines, str) else lines
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else size * 1.25:.1f}">{v}</tspan>' for i, v in enumerate(lines))
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
            f'paint-order="stroke" stroke="{NAVY}" stroke-width="6" stroke-opacity=".55" stroke-linejoin="round">{spans}</text>')


def pointer(px, py, ex, ey, color=WHITE):
    """Línea con un punto en el objeto señalado (px, py) que termina junto al texto (ex, ey)."""
    return (f'<line x1="{px}" y1="{py}" x2="{ex}" y2="{ey}" stroke="{color}" stroke-width="3"/>'
            f'<circle cx="{px}" cy="{py}" r="8" fill="{color}"/>')


def callout(px, py, tx, ty, lines, color=WHITE, anchor="start", size=30):
    shift = 12 if anchor == "start" else -12
    return pointer(px, py, tx, ty, color) + text(tx + shift, ty + size * 0.35, lines, size, color, 500, anchor)


def note(w, h, anchor="end"):
    x = w - 44 if anchor == "end" else 44
    return text(x, h - 30, "Ilustración generada con IA, esquemática", 22, MUTED, 400, anchor)


# nombre final: (imagen de fondo en ia/, (ancho, alto) del lienzo, textos)
SCENES = {
    "1-1-posicion-supina": ("1-1-posicion-supina-v3.png", (1600, 1143), lambda w, h: (
        pointer(608, 380, 890, 222) + text(900, 214, ["Paciente boca arriba", "(posición supina)"], 36)
        + pointer(560, 868, 380, 948, ORANGE) + text(90, 960, ["Mesa ortopédica", "de tracción"], 36, ORANGE)
        + note(w, h)
    )),
    "1-2-intensificador": ("1-2-intensificador-v3.png", (1600, 1143), lambda w, h: (
        pointer(870, 330, 990, 222, ORANGE) + text(1000, 214, ["Intensificador de imágenes", "(arco en C)"], 36, ORANGE)
        + pointer(336, 418, 230, 262) + text(90, 246, "Monitor", 36)
        + note(w, h)
    )),
}


def main():
    edge = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft/Edge/Application/msedge.exe"
    only = set(sys.argv[1:])
    with tempfile.TemporaryDirectory() as tmp:
        for name, (source, (w, h), overlay) in SCENES.items():
            if only and name not in only:
                continue
            background = HERE / "ia" / source
            page = Path(tmp) / f"{name}.html"
            page.write_text(
                '<!doctype html><meta charset="utf-8">'
                '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">'
                f'<style>html,body{{margin:0;background:{NAVY}}}div{{position:relative;width:{w}px;height:{h}px}}'
                f'img,svg{{position:absolute;inset:0;width:{w}px;height:{h}px}}</style>'
                f'<div><img src="{background.as_uri()}"><svg viewBox="0 0 {w} {h}" style="font-family:\'DM Sans\',sans-serif">{overlay(w, h)}</svg></div>',
                encoding="utf-8",
            )
            target = HERE / f"{name}.png"
            subprocess.run([
                str(edge), "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={tmp}/perfil",
                "--allow-file-access-from-files", "--hide-scrollbars", "--virtual-time-budget=4000",
                f"--window-size={w},{h}", f"--screenshot={target}", page.as_uri(),
            ], check=True, timeout=90, capture_output=True)
            print(name, target.stat().st_size)


if __name__ == "__main__":
    main()
