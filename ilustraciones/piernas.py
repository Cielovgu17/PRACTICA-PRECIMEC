"""Gira cada pierna (con su apoyo y su barra) alrededor de la cadera y cambia el fondo negro por el azul del instructivo."""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

NAVY = np.array([12, 25, 49], dtype=np.float32)
src = Image.open(sys.argv[1]).convert("RGB")
a = np.asarray(src).astype(np.int16)
H, W = a.shape[:2]
EDGE = 590  # borde de la cobija

r, g, b = a[..., 0], a[..., 1], a[..., 2]
teal = (g - r > 25) & (b - r > 25)           # la cobija
dark = a.max(axis=2) <= 6                      # fondo negro


def region(poly):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    return np.asarray(m) > 0


legs = {
    "upper": (region([(560, 105), (885, 105), (885, 225), (700, 225), (640, 222), (614, 219), (560, 219)]), (EDGE, 183)),
    "lower": (region([(560, 296), (614, 300), (640, 296), (700, 300), (885, 330), (885, 432), (560, 432)]), (EDGE, 325)),
}
angles = {"upper": float(sys.argv[3]), "lower": float(sys.argv[4])}

out = a.copy()
for name, (m, _) in legs.items():
    out[m & (np.arange(W)[None, :] >= EDGE)] = 0      # se borra la pierna en su sitio original

for name, (m, pivot) in legs.items():
    piece = np.zeros((H, W, 4), dtype=np.uint8)
    sel = m & ~teal & ~dark & (np.arange(W)[None, :] >= EDGE + 4)
    piece[sel, :3] = a[sel]
    piece[sel, 3] = 255
    # El muslo se prolonga un poco por debajo de la cobija para que al girar no quede un hueco.
    for y in range(H):
        if sel[y, EDGE + 6]:
            piece[y, EDGE - 40:EDGE + 4, :3] = a[y, EDGE + 6]
            piece[y, EDGE - 40:EDGE + 4, 3] = 255
    rot = np.asarray(Image.fromarray(piece, "RGBA").rotate(angles[name], resample=Image.BICUBIC, center=pivot)).astype(np.float32)
    al = rot[..., 3:4] / 255
    out = (out * (1 - al) + rot[..., :3] * al).astype(np.int16)

# La cobija y todo lo que queda a la izquierda del borde vuelve a ir encima.
keep = np.zeros((H, W), bool)
keep[:, :EDGE] = True
keep &= ~dark
keep |= teal & (np.arange(W)[None, :] < EDGE + 2)
keep = np.asarray(Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
keep &= (a.max(axis=2) > 6)
out[keep] = a[keep]

# Fondo: lo negro pasa a azul; los bordes se mezclan.
lum = out.max(axis=2).astype(np.float32)
alpha = np.clip((lum - 4) / 30, 0, 1)[..., None]
final = out * alpha + NAVY * (1 - alpha)
img = Image.fromarray(final.clip(0, 255).astype(np.uint8), "RGB").resize((W * 2, H * 2), Image.LANCZOS)
img.save(sys.argv[2])
img.crop((1080, 220, 1480, 880)).save("zoom.png")
print("ok", img.size)
