"""Endereza cada pierna (sin cortes en la rodilla), la gira completa desde la cadera,
cambia el fondo negro por el azul del instructivo y deja la imagen nítida.

    python piernas.py original_x3.png salida.png
Las coordenadas van en la imagen original (936 × 529) y se multiplican por K (la imagen llega ampliada ×3).
"""
import math
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

K = 3
NAVY = np.array([12, 25, 49], dtype=np.float32)
a = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(np.float32)
H, W = a.shape[:2]
X = np.arange(W)[None, :]
EDGE = 590 * K  # borde de la cobija
r, g, b = a[..., 0], a[..., 1], a[..., 2]
teal = (g - r > 25) & (b - r > 25)
dark = a.max(axis=2) <= 8


def poly(points):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([(x * K, y * K) for x, y in points], fill=255)
    return np.asarray(m) > 0


def slope(p, q):
    return (q[1] - p[1]) / (q[0] - p[0])  # pendiente en la imagen (positiva = baja hacia la derecha)


LEGS = {
    # cadera, rodilla, tobillo (en la imagen original) y ángulo final hacia arriba en grados
    "sana": dict(hip=(520, 195), knee=(665, 186), ankle=(752, 162), target=27,
                 zone=poly([(590, 100), (890, 100), (890, 224), (676, 224), (614, 219), (590, 219)])),
    "afectada": dict(hip=(520, 318), knee=(665, 335), ankle=(755, 370), target=12,
                     zone=poly([(590, 296), (614, 300), (640, 296), (676, 298), (890, 326), (890, 436), (590, 436)])),
}

out = a.copy()
layers = []
for name, leg in LEGS.items():
    zone = leg["zone"] & (X >= EDGE + 4 * K)
    out[leg["zone"] & (X >= EDGE)] = 0
    piece = np.zeros((H, W, 4), np.float32)
    sel = zone & ~teal & ~dark
    piece[sel, :3] = a[sel]
    piece[sel, 3] = 255
    # El muslo sigue por debajo de la cobija para que al girar no quede hueco.
    col = EDGE + 6 * K
    rows = sel[:, col]
    piece[rows, EDGE - 45 * K:col, :3] = a[rows, col][:, None, :]
    piece[rows, EDGE - 45 * K:col, 3] = 255

    # 1) Enderezar: de la rodilla hacia el pie todo se desliza en vertical hasta quedar en la línea del muslo.
    hip, knee, ankle = [(p[0] * K, p[1] * K) for p in (leg["hip"], leg["knee"], leg["ankle"])]
    k = slope(knee, ankle) - slope(hip, knee)
    w = 25 * K  # transición suave alrededor de la rodilla
    t = (np.arange(W) - knee[0]) / w
    hinge = np.where(t < -1, 0, np.where(t > 1, t, (t + 1) ** 2 / 4)) * w
    map_x = np.tile(np.arange(W, dtype=np.float32), (H, 1))
    map_y = (np.arange(H, dtype=np.float32)[:, None] + (k * hinge)[None, :]).astype(np.float32)
    piece = cv2.remap(piece, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # 2) Girar la pierna entera desde la cadera hasta el ángulo pedido.
    current = -math.degrees(math.atan(slope(hip, knee)))
    turn = leg["target"] - current
    M = cv2.getRotationMatrix2D(hip, turn, 1.0)  # positivo = antihorario en la imagen
    piece = cv2.warpAffine(piece, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    piece[..., 3] = piece[..., 3].clip(0, 255)
    layers.append(piece)
    print(name, "enderezado", round(math.degrees(math.atan(k)), 1), "giro", round(turn, 1))

for piece in layers:
    al = piece[..., 3:4] / 255
    out = out * (1 - al) + piece[..., :3].clip(0, 255) * al

# La cobija (y lo que está a la izquierda del borde) vuelve a ir encima.
keep = np.zeros((H, W), bool)
keep[:, :EDGE] = True
keep |= teal & (X < EDGE + 2 * K)
keep &= ~dark
out[keep] = a[keep]

# Fondo azul con bordes suaves y un poco de nitidez.
alpha = np.clip((out.max(axis=2) - 4) / 30, 0, 1)[..., None]
final = out * alpha + NAVY * (1 - alpha)
img = Image.fromarray(final.clip(0, 255).astype(np.uint8), "RGB").filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
img.save(sys.argv[2])
img.crop((1650, 150, 2750, 1300)).save("zoom.png")
print("ok", img.size)
