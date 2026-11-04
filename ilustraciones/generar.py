"""Dibuja las ilustraciones de las etapas 1 a 4 como SVG y las convierte en PNG con Microsoft Edge.

    python ilustraciones/generar.py

El contorno del fémur sale del modelo 3D del proyecto (Femur_derecho_adulto), medido en milímetros.
Vistas: AP = de frente, cabeza a la derecha; LAT = desde afuera, anterior a la derecha;
TOP = desde arriba, posterior hacia arriba. Los textos clínicos salen de la matriz de la técnica.
"""
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
W, H = 1600, 1000

NAVY = "#021a35"
TISSUE = "#17395e"
TISSUE_LINE = "#2d5580"
TABLE = "#0d2c4f"
TABLE_LINE = "#3a5f86"
BONE = "#e6ecf2"
BONE_DARK = "#b9c6d3"
CANAL = "#7f93a8"
ORANGE = "#f56f0d"
WHITE = "#ffffff"
MUTED = "#b3c1d0"

AP = [17.8,-229.1,27.5,-228.4,31.3,-226.6,34.4,-223.4,40.9,-211.3,43.8,-200.9,43.8,-193.4,42.2,-188.8,34.4,-178.8,23.4,-172.2,18.1,-166.6,12.8,-157.2,9.1,-144.1,6.6,-125.9,5,-103.1,-0.9,-70.6,0.3,-49.7,-1.6,-7.5,-1.3,31.3,-2.8,51.6,1.2,73.4,2.5,93.4,7.8,117.8,11.9,125.6,22.8,134.7,24.1,138.1,23.4,144.7,17.8,152.2,16.2,156.3,17.5,166.9,20,172.2,22.8,175.3,35.6,175,44.4,179.1,48.1,182.8,51.6,188.4,53.4,198.4,51.9,205.3,48.4,210.9,42.8,216.3,34.4,220.6,27.5,221.9,19.1,221.3,9.1,217.5,3.1,213.1,-2.5,208.8,-17.8,214.1,-23.1,213.4,-35.6,204.1,-41.6,198.1,-45.3,191.2,-44.4,176.6,-43.1,171.9,-34.1,159.7,-30.3,149.4,-26.6,121.9,-26.2,110.6,-31.9,48.4,-30.9,14.4,-32.8,-14.1,-31.6,-94.1,-32.5,-134.7,-36.3,-166.9,-49.4,-194.7,-50.3,-202.8,-47.2,-212.5,-40.9,-217.8,-33.1,-219.4,-18.1,-215.9,-12.2,-216.3,6.9,-226.9,17.5,-228.8]
LAT = [-7.8,-229.1,0.9,-228.8,6.6,-227.5,9.7,-225.6,16.9,-217.5,20.9,-206.9,20.3,-200,14.4,-183.4,11.6,-170,13.4,-109.7,18.1,-38.4,19.1,-8.4,14.7,80,7.8,114.4,7.2,130.3,11.2,145.3,13.1,156.9,18.1,167.5,25.3,175,33.8,174.7,41.3,178.4,46.3,184.4,50,194.4,49.7,202.5,47.2,209.4,41.3,215.9,32.5,220.6,25.6,221.9,18.7,221.6,11.2,218.4,3.7,211.6,-0.6,201.2,-10.6,211.9,-15.9,214.1,-19.4,213.8,-22.2,212.2,-25,208.8,-30.6,196.6,-30.3,182.2,-32.8,164.7,-32.8,155.3,-29.7,137.8,-22.2,112.2,-15,62.8,-14.7,43.1,-12.8,33.1,-12.8,12.8,-13.8,8.7,-12.5,-1.3,-13.1,-20.6,-16.9,-43.1,-16.9,-65,-22.2,-95.9,-22.5,-108.4,-26.9,-136.6,-26.9,-148.4,-28.4,-157.8,-37.5,-176.3,-40.9,-179.1,-46.9,-180.3,-51.9,-183.1,-57.5,-190,-60,-198.4,-59.7,-203.1,-58.1,-206.6,-50,-213.8,-41.9,-217.2,-30.3,-218.8,-21.2,-224.7,-8.1,-228.8]
CANAL_AP = [-15.6,-153.8,-9.4,-153.4,-4.7,-142.2,-5.6,-128.8,-5,-104.7,-9.1,-71.6,-7.8,-48.7,-9.1,-34.1,-8.4,-16.2,-10,-4.1,-9.1,1.9,-9.1,20.3,-10.6,51.3,-9.1,59.1,-3.8,114.7,-1.3,126.2,4.1,133.7,3.1,140.6,-1.3,145.9,-7.5,145.9,-7.8,141.9,-12.5,134.7,-15.6,126.2,-20.3,82.5,-21.9,56.3,-23.1,50.6,-21.2,18.4,-22.8,-1.6,-21.6,-16.9,-22.5,-32.2,-21.6,-48.4,-22.5,-78.1,-20.3,-100.9,-21.6,-135,-20.9,-142.5,-15.6,-153.4]
TOP = [20,-50.3,25.9,-50.3,32.5,-48.7,43.4,-43.1,52.5,-30.9,53.4,-25.3,52.5,-18.1,49.1,-10.6,41.3,-2.5,33.8,0.3,26.2,-0.6,23.4,0,23.4,9.1,19.4,13.7,11.9,19.1,13.1,23.7,10.3,28.1,0.9,31.6,-3.8,32.2,-13.8,32.2,-25.9,28.4,-33.8,24.7,-43.8,15,-45.3,5.3,-38.1,-8.1,-34.7,-12.5,-30.6,-14.7,-22.2,-16.2,-15.3,-19.7,4.1,-43.1,11.2,-47.8,19.7,-50]

# Puntos de referencia medidos en el modelo (mm, vista AP)
ENTRY_AP = (-19.0, 213.5)     # vértice del trocánter mayor
ENTRY_TOP = (-19.0, 0.7)      # unión del tercio anterior con los dos tercios posteriores
TROCH_TOP_RANGE = (-17.0, 32.0)  # borde anterior y posterior del trocánter a esa altura
LESSER_TROCH_Y = 138.0        # trocánter menor
SHAFT_X = -13.0               # eje de la diáfisis


def pairs(flat):
    return list(zip(flat[0::2], flat[1::2]))


def smooth(points, closed=True, tension=0.5):
    """Curva suave que pasa por los puntos."""
    n = len(points)
    d = f"M{points[0][0]:.1f} {points[0][1]:.1f}"
    last = n if closed else n - 1
    for i in range(last):
        p0 = points[(i - 1) % n] if closed or i > 0 else points[0]
        p1, p2 = points[i], points[(i + 1) % n]
        p3 = points[(i + 2) % n] if closed or i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d + ("Z" if closed else "")


def bone_view(flat, ox, oy, s, flip=False):
    sign = -1 if flip else 1
    return [(ox + sign * x * s, oy - y * s) for x, y in pairs(flat)]


def path(d, fill="none", stroke="none", width=0, extra=""):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round" {extra}/>'


def line(x1, y1, x2, y2, color=WHITE, width=3, dash=None):
    d = f'stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" {d}/>'


def dot(x, y, r=7, color=WHITE):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>'


def text(x, y, lines, size=30, color=WHITE, weight=500, anchor="start"):
    if isinstance(lines, str):
        lines = [lines]
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else size * 1.25:.1f}">{value}</tspan>' for i, value in enumerate(lines)
    )
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{spans}</text>'


def callout(px, py, tx, ty, lines, color=WHITE, anchor="start", size=30, weight=500):
    """Texto con una línea que señala un punto."""
    return dot(px, py, 7, color) + line(px, py, tx, ty, color, 2.5) + text(
        tx + (12 if anchor == "start" else -12), ty + size * 0.35, lines, size, color, weight, anchor
    )


def arrow(x1, y1, x2, y2, color=ORANGE, width=6, head=20):
    angle = math.atan2(y2 - y1, x2 - x1)
    a = (x2 - head * math.cos(angle - 0.45), y2 - head * math.sin(angle - 0.45))
    b = (x2 - head * math.cos(angle + 0.45), y2 - head * math.sin(angle + 0.45))
    return line(x1, y1, x2, y2, color, width) + f'<path d="M{a[0]:.1f} {a[1]:.1f}L{x2:.1f} {y2:.1f}L{b[0]:.1f} {b[1]:.1f}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def dimension(x1, y1, x2, y2, color=ORANGE, width=4, tick=14):
    """Cota con topes en los extremos."""
    angle = math.atan2(y2 - y1, x2 - x1) + math.pi / 2
    dx, dy = math.cos(angle) * tick, math.sin(angle) * tick
    return line(x1, y1, x2, y2, color, width) + line(x1 - dx, y1 - dy, x1 + dx, y1 + dy, color, width) + line(x2 - dx, y2 - dy, x2 + dx, y2 + dy, color, width)


def arc(cx, cy, r, a0, a1, color=ORANGE, width=5):
    """Arco entre dos ángulos, en grados medidos como en la pantalla."""
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 > a0 else 0
    return f'<path d="M{x0:.1f} {y0:.1f}A{r} {r} 0 {large} {sweep} {x1:.1f} {y1:.1f}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>'


def note(lines=None):
    base = text(W - 48, H - 40, "Ilustración esquemática, no está a escala", 24, MUTED, 400, "end")
    return base


def chip(x, y, label):
    width = len(label) * 14.2 + 32
    return f'<rect x="{x}" y="{y}" width="{width:.0f}" height="46" rx="6" fill="{TABLE}" stroke="{TABLE_LINE}" stroke-width="2"/>' + text(x + 16, y + 31, label, 25, MUTED, 400)


# ---------- El paciente visto de lado ----------

BODY_SIDE = [
    (300, 578), (352, 560), (470, 545), (620, 558), (760, 562), (900, 590), (1060, 612), (1200, 628),
    (1282, 640), (1296, 580), (1322, 566), (1346, 576), (1350, 640), (1336, 672), (1200, 672), (1060, 668),
    (900, 672), (760, 676), (600, 676), (400, 676), (312, 662), (296, 622),
]


def table_side(highlight=False):
    color = ORANGE if highlight else TABLE_LINE
    parts = [
        f'<rect x="160" y="680" width="690" height="26" rx="8" fill="{TABLE}" stroke="{color}" stroke-width="3"/>',
        f'<rect x="470" y="706" width="60" height="170" fill="{TABLE}" stroke="{color}" stroke-width="3"/>',
        f'<rect x="360" y="876" width="280" height="26" rx="8" fill="{TABLE}" stroke="{color}" stroke-width="3"/>',
        line(840, 696, 1372, 716, color, 14),
        f'<rect x="1344" y="716" width="46" height="160" fill="{TABLE}" stroke="{color}" stroke-width="3"/>',
        f'<rect x="1270" y="876" width="200" height="26" rx="8" fill="{TABLE}" stroke="{color}" stroke-width="3"/>',
        f'<rect x="1272" y="622" width="96" height="66" rx="16" fill="{TABLE}" stroke="{color}" stroke-width="3"/>',
        line(1320, 688, 1364, 712, color, 10),
    ]
    return "".join(parts)


def patient_side():
    return (
        f'<circle cx="244" cy="606" r="62" fill="{TISSUE}" stroke="{TISSUE_LINE}" stroke-width="3"/>'
        + path(smooth(BODY_SIDE), TISSUE, TISSUE_LINE, 3)
    )


def scene_1_1():
    return (
        table_side(highlight=True) + patient_side()
        + text(96, 110, "Paciente en posición supina", 42, WHITE, 600)
        + text(96, 164, "Boca arriba, en una mesa ortopédica de tracción.", 32, MUTED, 400)
        + arrow(520, 400, 520, 520, WHITE, 5)
        + text(540, 420, "Boca arriba", 32, WHITE, 500)
        + line(1100, 712, 1100, 790, ORANGE, 2.5) + dot(1100, 712, 7, ORANGE)
        + text(860, 830, "Mesa ortopédica de tracción", 32, ORANGE, 500)
        + chip(860, 852, "No hace parte del set")
        + note()
    )


def scene_1_2():
    cx = 760
    c_arm = path(f"M{cx} 330C1120 330 1120 900 {cx} 900", "none", ORANGE, 26)
    return (
        table_side() + patient_side()
        + c_arm
        + f'<rect x="{cx - 80}" y="282" width="160" height="66" rx="10" fill="{TABLE}" stroke="{ORANGE}" stroke-width="4"/>'
        + f'<rect x="{cx - 56}" y="876" width="112" height="48" rx="8" fill="{TABLE}" stroke="{ORANGE}" stroke-width="4"/>'
        + line(cx, 350, cx, 874, ORANGE, 3, "12 14")
        + f'<rect x="1000" y="690" width="72" height="210" rx="6" fill="{TABLE}" stroke="{ORANGE}" stroke-width="3"/>'
        + text(96, 110, "Usar el intensificador de imágenes", 42, WHITE, 600)
        + callout(cx + 80, 315, 1130, 250, ["Fluoroscopio", "(arco en C)"], ORANGE, size=32)
        + chip(1142, 340, "No hace parte del set")
        + text(96, 164, "Para vigilar la cirugía.", 32, MUTED, 400)
        + note()
    )


# ---------- El paciente visto desde arriba: cabeza a la izquierda, pierna derecha abajo ----------

HIP_R = (750, 582)   # cadera derecha, lado afectado
HIP_L = (750, 418)   # cadera izquierda, lado sano
LEG = 590


def limb(hip, angle, color=TISSUE, stroke=TISSUE_LINE):
    """Pierna como una sola forma, de la cadera al pie. El ángulo se mide desde la línea recta."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    stations = [(0, 72), (160, 62), (320, 44), (450, 36), (590, 22)]
    upper = [(hip[0] + ux * t + nx * w, hip[1] + uy * t + ny * w) for t, w in stations]
    lower = [(hip[0] + ux * t - nx * w, hip[1] + uy * t - ny * w) for t, w in reversed(stations)]
    foot_center = (hip[0] + ux * (LEG + 18), hip[1] + uy * (LEG + 18))
    return path(smooth(upper + [foot_center] + lower + [(hip[0] - ux * 40, hip[1] - uy * 40)]), color, stroke, 3)


def limb_point(hip, angle, t):
    a = math.radians(angle)
    return hip[0] + math.cos(a) * t, hip[1] + math.sin(a) * t


def trunk_top(rotation=0):
    points = [(322, 470), (345, 365), (420, 330), (540, 345), (640, 370), (740, 345), (812, 400), (832, 500), (812, 600), (740, 655), (640, 630), (540, 655), (420, 670), (345, 635), (322, 530)]
    arms = line(420, 312, 740, 300, TISSUE_LINE, 54) + line(420, 688, 740, 700, TISSUE_LINE, 54)
    arms += line(420, 312, 740, 300, TISSUE, 48) + line(420, 688, 740, 700, TISSUE, 48)
    body = path(smooth(points), TISSUE, TISSUE_LINE, 3)
    head = f'<circle cx="244" cy="500" r="66" fill="{TISSUE}" stroke="{TISSUE_LINE}" stroke-width="3"/>'
    return f'<g transform="rotate({rotation} 780 500)">{arms}{head}{body}</g>'


def table_top():
    return (
        f'<rect x="130" y="240" width="770" height="520" rx="16" fill="{TABLE}" stroke="{TABLE_LINE}" stroke-width="3"/>'
    )


def side_labels():
    return text(1410, 340, ["Lado sano"], 30, MUTED, 500) + text(1410, 660, ["Lado", "afectado"], 30, WHITE, 500)


def scene_etapa1():
    tilt = 8
    troch = (HIP_R[0] + 30, HIP_R[1] + 66)
    return (
        table_top() + trunk_top(tilt)
        + limb(HIP_L, -8) + limb(HIP_R, -7)
        + side_labels()
        + text(96, 110, "En un paciente obeso", 42, WHITE, 600)
        + text(96, 164, "Inclinar el cuerpo hacia el lado sano y aducir el miembro inferior.", 32, MUTED, 400)
        + arrow(120, 500, 120, 300, ORANGE, 6)
        + text(70, 810, ["Cuerpo inclinado", "hacia el lado sano"], 30, ORANGE, 500)
        + line(120, 510, 120, 770, ORANGE, 2.5)
        + f'<circle cx="{troch[0]}" cy="{troch[1]}" r="16" fill="{ORANGE}"/>'
        + callout(troch[0], troch[1], 900, 850, ["Trocánter mayor destacado:", "así cuesta menos introducir el clavo principal"], ORANGE, size=30)
        + note()
    )


def scene_2_1():
    add = -12
    p_end = limb_point(HIP_R, 0, LEG + 30)
    return (
        table_top() + trunk_top()
        + limb(HIP_L, -10) + limb(HIP_R, add, TISSUE, ORANGE)
        + line(HIP_R[0], HIP_R[1], p_end[0], p_end[1], MUTED, 3, "14 14")
        + line(HIP_R[0], HIP_R[1], *limb_point(HIP_R, add, LEG + 30), ORANGE, 4)
        + arc(HIP_R[0], HIP_R[1], 430, 0, add, ORANGE, 6)
        + side_labels()
        + text(96, 110, "Reducir (alinear) la fractura", 42, WHITE, 600)
        + text(96, 164, "Aducir el miembro afectado de 10 a 15 grados.", 32, MUTED, 400)
        + text(1200, 572, "10 a 15°", 40, ORANGE, 600)
        + text(1040, 770, "Línea sin aducción", 28, MUTED, 400)
        + line(1180, 590, 1180, 735, MUTED, 2)
        + note()
    )


def scene_2_2():
    add = -12
    foot = limb_point(HIP_R, add, LEG + 10)
    return (
        table_top() + trunk_top()
        + line(880, 500, foot[0] + 30, foot[1] - 8, TABLE_LINE, 18)
        + limb(HIP_L, -10) + limb(HIP_R, add)
        + f'<g transform="rotate({add} {foot[0]} {foot[1]})"><rect x="{foot[0] - 50}" y="{foot[1] - 56}" width="118" height="112" rx="20" fill="{TABLE}" stroke="{ORANGE}" stroke-width="6"/></g>'
        + side_labels()
        + text(96, 110, "Fijar el miembro a la mesa de tracción", 42, WHITE, 600)
        + callout(foot[0], foot[1] + 56, 1040, 780, ["El pie queda sujeto a la mesa"], ORANGE, size=32)
        + note()
    )


def scene_2_3():
    y = 470
    shaft = f'<rect x="240" y="{y - 26}" width="440" height="52" rx="24" fill="{BONE}"/>'
    shaft2 = f'<rect x="900" y="{y - 26}" width="440" height="52" rx="24" fill="{BONE}"/>'
    fragments = "".join(
        path(f"M{x} {y + dy - 24}L{x + 44} {y + dy - 30}L{x + 56} {y + dy + 8}L{x + 12} {y + dy + 24}Z", BONE, "none", 0)
        for x, dy in [(700, -44), (748, 22), (800, -18), (846, 38)]
    )
    tissue = path(smooth([(160, 300), (600, 290), (1100, 330), (1450, 380), (1450, 560), (1100, 610), (600, 650), (160, 640)]), TISSUE, TISSUE_LINE, 3)
    return (
        tissue + shaft + fragments + shaft2
        + text(96, 110, "Ajustar la tracción en una fractura conminuta", 42, WHITE, 600)
        + text(96, 164, "El miembro puede acortarse o alargarse.", 32, MUTED, 400)
        + arrow(1190, 740, 1440, 740, ORANGE, 7)
        + text(1190, 800, "Alargamiento", 32, ORANGE, 500)
        + arrow(1160, 740, 910, 740, WHITE, 7)
        + text(910, 800, "Acortamiento", 32, WHITE, 500)
        + callout(790, 450, 610, 770, ["Fractura conminuta:", "varios fragmentos"], WHITE, "end", size=30)
        + note()
    )


# ---------- Medición del implante ----------

def femur_ap(ox, oy, s, flip=False, canal=False):
    out = path(smooth(bone_view(AP, ox, oy, s, flip)), BONE, BONE_DARK, 2)
    if canal:
        out += path(smooth(bone_view(CANAL_AP, ox, oy, s, flip)), CANAL, "none", 0)
    return out


def scene_3_1():
    s = 2.45
    ox, oy = 730, 830
    # Fémur sano (izquierdo), espejo del modelo: cabeza hacia la izquierda
    px = lambda x, y: (ox - x * s, oy - y * s)
    corner = px(SHAFT_X, 162)
    head = px(27, 197)
    shaft = px(SHAFT_X, 30)
    neck_end = (corner[0] + (head[0] - corner[0]) * 1.2, corner[1] + (head[1] - corner[1]) * 1.2)
    a_neck = math.degrees(math.atan2(head[1] - corner[1], head[0] - corner[0]))
    a_neck = a_neck if a_neck > 90 else a_neck + 360
    mid = math.radians((90 + a_neck) / 2)
    on_arc = (corner[0] + 80 * math.cos(mid), corner[1] + 80 * math.sin(mid))
    template = (
        f'<rect x="{ox - 280}" y="240" width="560" height="660" rx="10" fill="{ORANGE}" fill-opacity=".07" stroke="{ORANGE}" stroke-width="3"/>'
        + "".join(line(ox + 244, 280 + i * 30, ox + (266 if i % 5 else 280), 280 + i * 30, ORANGE, 2) for i in range(20))
    )
    clip = f'<clipPath id="bajo"><rect x="0" y="0" width="{W}" height="900"/></clipPath>'
    return (
        clip + f'<g clip-path="url(#bajo)">{femur_ap(ox, oy, s, flip=True)}</g>' + template
        + line(*corner, *neck_end, ORANGE, 6)
        + line(*corner, *shaft, ORANGE, 6)
        + arc(corner[0], corner[1], 80, 90, a_neck, ORANGE, 6)
        + dot(*corner, 9, ORANGE)
        + text(96, 110, "Estimar el ángulo cuello-diáfisis", 42, WHITE, 600)
        + text(96, 164, "Con la plantilla ubicada en la pierna sana.", 32, MUTED, 400)
        + callout(on_arc[0], on_arc[1], 1070, 400, ["Ángulo", "cuello-diáfisis"], ORANGE, size=34)
        + callout(ox + 280, 720, 1070, 640, ["Plantilla radiográfica"], ORANGE, size=32)
        + chip(1082, 672, "No viene en el set")
        + callout(ox + 25, 700, 300, 620, ["Fémur de la", "pierna sana"], NAVY, "end", size=30).replace(f'fill="{NAVY}" text-anchor', f'fill="{WHITE}" text-anchor').replace(f'stroke="{NAVY}"', f'stroke="{WHITE}"')
        + note()
    )


def nail(ox, oy, s, tip_y, entry=ENTRY_AP, color=ORANGE, width=12):
    bend_y = 150
    top = (ox + entry[0] * s, oy - entry[1] * s)
    bend = (ox + SHAFT_X * s, oy - bend_y * s)
    end = (ox + SHAFT_X * s, oy - tip_y * s)
    return path(smooth([top, bend, end], closed=False, tension=0.35), "none", color, width * s / 2 + 4)


def scene_3_2():
    s = 1.95
    ox, oy = 520, 492
    x_rule = ox + 180
    top_y = oy - ENTRY_AP[1] * s
    tip_y = oy - (-165) * s
    ruler = (
        f'<rect x="{x_rule - 26}" y="{top_y - 18}" width="52" height="{tip_y - top_y + 36}" rx="6" fill="{ORANGE}" fill-opacity=".12" stroke="{ORANGE}" stroke-width="3"/>'
        + "".join(line(x_rule - 26, top_y + i * 25, x_rule - (6 if i % 4 else -6), top_y + i * 25, ORANGE, 2) for i in range(int((tip_y - top_y) / 25) + 1))
    )
    return (
        femur_ap(ox, oy, s) + ruler
        + line(ox + ENTRY_AP[0] * s, top_y, x_rule, top_y, ORANGE, 3, "10 10")
        + line(ox + SHAFT_X * s, tip_y, x_rule, tip_y, ORANGE, 3, "10 10")
        + dot(ox + ENTRY_AP[0] * s, top_y, 11, ORANGE)
        + dot(ox + SHAFT_X * s, tip_y, 11, ORANGE)
        + text(860, 110, ["Leer el largo del clavo"], 42, WHITE, 600)
        + text(860, 164, ["Plantilla frente al fémur."], 32, MUTED, 400)
        + callout(x_rule + 26, top_y, 860, 290, ["Parte proximal:", "en el punto de entrada"], ORANGE, size=32)
        + callout(x_rule + 26, tip_y, 860, 800, ["Parte distal:", "en la posición esperada"], ORANGE, size=32)
        + callout(x_rule + 26, (top_y + tip_y) / 2, 860, 510, ["Se lee el largo del clavo"], WHITE, size=32)
        + chip(860, 600, "Plantilla: no viene en el set")
        + note()
    )


def scene_3_3():
    s = 1.95
    ox, oy = 330, 492
    level = 20
    y = oy - level * s
    zoom = 6.2
    zx, zy = 1000, 560
    clip_y = 62
    zoom_group = (
        f'<clipPath id="zoom"><rect x="{zx - 300}" y="{zy - 300}" width="600" height="600" rx="12"/></clipPath>'
        f'<rect x="{zx - 300}" y="{zy - 300}" width="600" height="600" rx="12" fill="{TISSUE}"/>'
        f'<g clip-path="url(#zoom)">'
        + path(smooth(bone_view(AP, zx - SHAFT_X * zoom - 0, zy + level * zoom, zoom)), BONE, BONE_DARK, 2)
        + path(smooth(bone_view(CANAL_AP, zx - SHAFT_X * zoom, zy + level * zoom, zoom)), CANAL, "none", 0)
        + "</g>"
    )
    left = zx + (-21.8 - SHAFT_X) * zoom
    right = zx + (-9.1 - SHAFT_X) * zoom
    return (
        femur_ap(ox, oy, s, canal=True)
        + f'<rect x="{ox - 80}" y="{y - clip_y}" width="150" height="{clip_y * 2}" fill="none" stroke="{ORANGE}" stroke-width="4" rx="6"/>'
        + line(ox + 70, y - clip_y, zx - 300, zy - 300, ORANGE, 2)
        + line(ox + 70, y + clip_y, zx - 300, zy + 300, ORANGE, 2)
        + zoom_group
        + dimension(left, zy, right, zy, ORANGE, 6, 20)
        + text(700, 110, "Estimar el diámetro del canal", 42, WHITE, 600)
        + text(700, 164, "Con la plantilla, para elegir el diámetro del clavo.", 32, MUTED, 400)
        + callout((left + right) / 2, zy + 170, zx - 150, zy + 170, ["Canal", "intra-", "medular"], WHITE, "end", size=26)
        + callout(right, zy, zx + 150, zy - 100, ["Diámetro"], ORANGE, size=32)
        + chip(700, 880, "Clavo principal: Φ9.4, 10, 11 o 12 mm")
        + note()
    )


def fracture_line(ox, oy, s, y_mm, x_left=-34, x_right=26):
    pts = []
    steps = 7
    for i in range(steps + 1):
        x = x_left + (x_right - x_left) * i / steps
        y = y_mm + (6 if i % 2 else -6) - (x - x_left) * 0.28
        pts.append(f"{ox + x * s:.1f} {oy - y * s:.1f}")
    return path("M" + "L".join(pts), "none", "#d6281e", 5)


def scene_3_4():
    s = 1.8
    oy = 520
    a, b = 380, 1090
    lesser = lambda ox: line(ox - 130, oy - LESSER_TROCH_Y * s, ox + 130, oy - LESSER_TROCH_Y * s, MUTED, 2.5, "12 12")
    return (
        femur_ap(a, oy, s) + femur_ap(b, oy, s)
        + nail(a, oy, s, 35) + nail(b, oy, s, -170)
        + fracture_line(a, oy, s, 168) + fracture_line(b, oy, s, 80)
        + lesser(a) + lesser(b)
        + text(96, 90, "Elegir el largo del clavo", 42, WHITE, 600)
        + text(a + 140, oy - LESSER_TROCH_Y * s + 10, ["Trocánter", "menor"], 26, MUTED, 400)
        + text(b + 140, oy - LESSER_TROCH_Y * s + 10, ["Trocánter", "menor"], 26, MUTED, 400)
        + text(a + 110, 560, ["Clavo", "principal"], 34, ORANGE, 600)
        + text(a + 110, 660, ["Si la línea de fractura", "no baja del", "trocánter menor"], 26, WHITE, 400)
        + text(b + 110, 560, ["Clavo", "extendido"], 34, ORANGE, 600)
        + text(b + 110, 660, ["Se usa si la línea", "de fractura baja", "del trocánter menor"], 26, WHITE, 400)
        + note()
    )


# ---------- Abordaje ----------

def scene_4_1():
    s = 3.2
    x0, y0 = 760, 500
    project = [(x0 + (214 - y) * s, y0 - z * s) for z, y in pairs(LAT)]
    bone = path(smooth(project), BONE, BONE_DARK, 2)
    tissue = path(smooth([
        (40, 250), (420, 220), (720, 235), (1100, 260), (1600, 300), (1600, 700), (1100, 730), (720, 770), (420, 790), (40, 760),
    ]), TISSUE, TISSUE_LINE, 3)
    # El vértice del trocánter mayor en el modelo, visto desde afuera
    tip_x, tip_y = x0, y0 + 15.9 * s
    length = 55 * s
    return (
        tissue
        + f'<g opacity=".5">{bone}</g>'
        + line(tip_x - length, tip_y, tip_x, tip_y, ORANGE, 12)
        + dimension(tip_x - length, tip_y + 60, tip_x, tip_y + 60, WHITE, 3, 12)
        + dot(tip_x, tip_y, 15, WHITE)
        + text(96, 110, "Hacer la incisión", 42, WHITE, 600)
        + text(96, 164, "De 5 a 6 cm en dirección proximal, a partir del vértice del trocánter mayor.", 32, MUTED, 400)
        + text(tip_x - length / 2, tip_y + 108, "5 a 6 cm", 38, WHITE, 600, "middle")
        + callout(tip_x - length / 2, tip_y, 300, 400, ["Incisión"], ORANGE, "end", size=34)
        + callout(tip_x, tip_y, 1040, 830, ["Vértice del trocánter mayor"], WHITE, size=32)
        + arrow(290, 860, 90, 860, WHITE, 5)
        + text(310, 872, "Hacia proximal (la cabeza)", 30, WHITE, 400)
        + note()
    )


def scene_4_2():
    s = 4.0
    ox, oy = 420, 1130
    # Solo la parte proximal del hueso, recortada abajo
    clip = f'<clipPath id="prox"><rect x="40" y="200" width="680" height="700" rx="12"/></clipPath>'
    front = f'<g clip-path="url(#prox)">{path(smooth(bone_view(AP, ox + 20, oy, s)), BONE, BONE_DARK, 2)}</g>'
    entry_front = (ox + 20 + ENTRY_AP[0] * s, oy - ENTRY_AP[1] * s)

    st = 5.6
    tx, ty = 1170, 560
    view = bone_view(TOP, tx, ty, st)
    entry_top = (tx + ENTRY_TOP[0] * st, ty - ENTRY_TOP[1] * st)
    y_ant = ty - TROCH_TOP_RANGE[0] * st
    y_pos = ty - TROCH_TOP_RANGE[1] * st
    bar_x = tx - 58 * st + 40
    bracket = (
        dimension(bar_x, y_pos, bar_x, y_ant, WHITE, 3, 12)
        + line(bar_x - 14, entry_top[1], bar_x + 14, entry_top[1], ORANGE, 6)
        + line(bar_x, entry_top[1], entry_top[0], entry_top[1], ORANGE, 3, "10 10")
    )
    return (
        clip + front
        + dot(*entry_front, 15, ORANGE)
        + path(smooth(view), BONE, BONE_DARK, 2)
        + bracket
        + dot(*entry_top, 15, ORANGE)
        + text(96, 90, "Ubicar el punto de entrada", 42, WHITE, 600)
        + text(96, 142, "Vértice del trocánter mayor, en la unión del tercio anterior con los dos tercios posteriores.", 30, MUTED, 400)
        + text(70, 240, "De frente", 34, WHITE, 600)
        + text(860, 240, "Desde arriba", 34, WHITE, 600)
        + callout(entry_front[0], entry_front[1], 255, 330, ["Vértice del", "trocánter", "mayor"], ORANGE, "end", size=28)
        + text(bar_x - 22, (y_pos + entry_top[1]) / 2 + 8, ["2/3", "posteriores"], 26, WHITE, 500, "end")
        + text(bar_x - 22, (y_ant + entry_top[1]) / 2 + 2, ["1/3 anterior"], 26, WHITE, 500, "end")
        + text(tx + 60, 880, "Cabeza femoral", 26, MUTED, 400)
        + note()
    )


SCENES = {
    "etapa1-paciente-obeso": scene_etapa1,
    "1-1-posicion-supina": scene_1_1,
    "1-2-intensificador": scene_1_2,
    "2-1-aduccion": scene_2_1,
    "2-2-fijar-miembro": scene_2_2,
    "2-3-traccion": scene_2_3,
    "3-1-angulo-cuello-diafisis": scene_3_1,
    "3-2-largo-del-clavo": scene_3_2,
    "3-3-diametro-del-canal": scene_3_3,
    "3-4-clavo-principal-extendido": scene_3_4,
    "4-1-incision": scene_4_1,
    "4-2-punto-de-entrada": scene_4_2,
}


def svg(body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'style="font-family:\'DM Sans\',\'Segoe UI\',sans-serif"><rect width="{W}" height="{H}" fill="{NAVY}"/>{body}</svg>'
    )


def main():
    edge = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft/Edge/Application/msedge.exe"
    only = sys.argv[1:]
    with tempfile.TemporaryDirectory() as tmp:
        for name, scene in SCENES.items():
            if only and name not in only:
                continue
            drawing = svg(scene())
            (OUT / f"{name}.svg").write_text(drawing, encoding="utf-8")
            page = Path(tmp) / f"{name}.html"
            page.write_text(
                '<!doctype html><meta charset="utf-8">'
                '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">'
                f'<style>html,body{{margin:0;background:{NAVY}}}svg{{display:block}}</style>{drawing}',
                encoding="utf-8",
            )
            subprocess.run([
                str(edge), "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={tmp}/perfil",
                "--hide-scrollbars", "--virtual-time-budget=3000", f"--window-size={W},{H}",
                f"--screenshot={OUT / (name + '.png')}", page.as_uri(),
            ], check=True, timeout=60, capture_output=True)
            print(name, (OUT / f"{name}.png").stat().st_size)


if __name__ == "__main__":
    main()
