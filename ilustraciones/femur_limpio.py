"""Limpia la superficie del fémur dentro de un GLB, sin cambiar nada más del archivo.

    python ilustraciones/femur_limpio.py entrada.glb salida.glb

Qué corrige (defectos del modelo, no de la anatomía):
  * bultos y hundimientos a lo largo de la diáfisis, que hacen ver los laterales "dentados";
  * la línea donde se unen las dos mitades en que viene partido el hueso;
  * el sombreado duro en costuras de la malla.

Cómo: se sueldan las mitades, se aplica un suavizado de Taubin (alisa sin encoger el hueso) y se
limita cuánto puede moverse cada punto (MAX_SHIFT). Así se van las irregularidades, pero la cabeza,
el cuello, los trocánteres, la línea áspera y los cóndilos conservan su forma y su tamaño.
Los bordes abiertos (p. ej. el orificio del abridor) no se mueven: el instrumental sigue alineado.
Solo cambian las posiciones y las normales del fémur; animaciones, piezas y escenas quedan iguales.
"""
import json
import re
import struct
import sys

import numpy as np

import os
# Primero un alisado directo (quita bultos y hundimientos de unos milímetros a pocos centímetros) y
# luego pasadas de Taubin que devuelven el volumen. El tope MAX_SHIFT evita que cambie la forma general.
SMOOTH = int(os.environ.get("FEMUR_SMOOTH", 110))
PASSES = int(os.environ.get("FEMUR_PASSES", 60))
LAMBDA = 0.5
MU = -0.53
MAX_SHIFT = float(os.environ.get("FEMUR_MAX_MM", 1.4)) / 1000  # metros: tope de movimiento de cada punto
FEMUR = re.compile(r"femur", re.I)
NOT_BONE = re.compile(r"canal|abertura|cortical|anillo|flecha|eje|indicador|linea|bordes", re.I)

COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
DTYPES = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}


def read_glb(path):
    data = bytearray(open(path, "rb").read())
    json_len = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    return data, doc, bin_start


def accessor_view(data, doc, bin_start, index):
    """Devuelve (arreglo, posición en el archivo de cada elemento, tipo) de un accessor."""
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    n = COMPONENTS[acc["type"]]
    dtype = np.dtype(DTYPES[acc["componentType"]]).newbyteorder("<")
    stride = view.get("byteStride") or n * dtype.itemsize
    base = bin_start + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    offsets = base + np.arange(acc["count"], dtype=np.int64) * stride
    raw = np.frombuffer(data, dtype=np.uint8)
    idx = offsets[:, None] + np.arange(n * dtype.itemsize)[None, :]
    out = raw[idx].copy().view(dtype).reshape(acc["count"], n)
    return out, offsets, dtype


def write_floats(data, offsets, values):
    raw = np.frombuffer(data, dtype=np.uint8)  # misma memoria que data (bytearray)
    payload = np.ascontiguousarray(values.astype("<f4")).view(np.uint8).reshape(len(offsets), -1)
    idx = offsets[:, None] + np.arange(payload.shape[1])[None, :]
    raw[idx] = payload


# ---------- Diáfisis: contornos continuos con curvas suaves ----------
# El cuerpo del fémur (entre el trocánter menor y el ensanchamiento distal) se rehace a partir de su
# propia forma: un eje central con una curva suave y, para cada lado del hueso, un radio que cambia de
# manera continua a lo largo. Así las paredes quedan como líneas continuas con curvas ligeras (como en
# las láminas de anatomía), sin bultos. Los extremos del hueso no se tocan y la unión es gradual.
SHAFT_FULL = (-0.100, 0.095)   # metros en el eje largo (y): zona rehecha por completo
SHAFT_BLEND = (-0.170, 0.128)  # hasta aquí se mezcla gradualmente con la forma original
SHAFT_ANGLES = 48               # lados en que se divide la sección
SHAFT_DEGREE = 4                # grado de la curva a lo largo de cada lado (curvas suaves)


def _smoothstep(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def shaft(P):
    y = P[:, 1]
    weight = np.minimum(_smoothstep(y, SHAFT_BLEND[0], SHAFT_FULL[0]), 1 - _smoothstep(y, SHAFT_FULL[1], SHAFT_BLEND[1]))
    zone = weight > 0
    if zone.sum() < 100:
        return P
    # Eje central: centro de cada rebanada, ajustado a una curva suave (cúbica).
    bins = np.arange(SHAFT_BLEND[0] - 0.01, SHAFT_BLEND[1] + 0.01, 0.004)
    centers = []
    for lo in bins:
        s = P[(y >= lo) & (y < lo + 0.004)]
        if len(s) > 20:
            centers.append((lo + 0.002, s[:, 0].mean(), s[:, 2].mean()))
    centers = np.array(centers)
    cx = np.polyfit(centers[:, 0], centers[:, 1], 3)
    cz = np.polyfit(centers[:, 0], centers[:, 2], 3)
    Q = P[zone]
    qy = Q[:, 1]
    dx, dz = Q[:, 0] - np.polyval(cx, qy), Q[:, 2] - np.polyval(cz, qy)
    theta = np.arctan2(dz, dx)
    radius = np.hypot(dx, dz)
    # Radio de cada lado a lo largo del hueso: curva suave (polinomio) ajustada a los puntos del lado.
    k = SHAFT_ANGLES
    pos = (theta + np.pi) / (2 * np.pi) * k
    side = np.floor(pos).astype(int) % k
    coeffs = np.zeros((k, SHAFT_DEGREE + 1))
    span = (SHAFT_BLEND[0] - 0.01, SHAFT_BLEND[1] + 0.01)
    for i in range(k):
        sel = (side == i) | (side == (i + 1) % k) | (side == (i - 1) % k)
        sel &= (qy > span[0]) & (qy < span[1])
        coeffs[i] = np.polyfit(qy[sel], radius[sel], SHAFT_DEGREE)
    # Un leve alisado entre lados vecinos, para que la sección no quede facetada.
    coeffs = (np.roll(coeffs, 1, 0) + 2 * coeffs + np.roll(coeffs, -1, 0)) / 4
    frac = pos - np.floor(pos)
    r0 = np.array([np.polyval(coeffs[s], v) for s, v in zip(side, qy)])
    r1 = np.array([np.polyval(coeffs[(s + 1) % k], v) for s, v in zip(side, qy)])
    # El ángulo de cada lado corresponde al centro de su franja: se interpola entre franjas vecinas.
    centre_shift = frac - 0.5
    r_left = np.array([np.polyval(coeffs[(s - 1) % k], v) for s, v in zip(side, qy)])
    new_r = np.where(centre_shift >= 0, r0 + (r1 - r0) * centre_shift, r0 + (r0 - r_left) * centre_shift)
    target = np.stack([np.polyval(cx, qy) + new_r * np.cos(theta), qy, np.polyval(cz, qy) + new_r * np.sin(theta)], axis=1)
    w = weight[zone][:, None]
    out = P.copy()
    out[zone] = Q * (1 - w) + target * w
    return out


# ---------- Hueso alrededor de la broca ----------
# En este modelo la zona justo debajo del trocánter es angosta para la broca canulada de Φ16,5 mm: se
# ensancha suave y localmente la pared, solo en el tramo donde pasa la broca, para dejar al menos 2 mm de
# hueso alrededor. El eje del instrumental lo deja anotado ajustar_animaciones.py en el propio archivo.
def around_drill(P, axis, triangles=None):
    if not axis:
        return P
    E, u = np.asarray(axis["entrada"], float), np.asarray(axis["direccion"], float)
    u = u / np.linalg.norm(u)
    q = P - E
    k = q @ u
    radial = q - np.outer(k, u)
    r = np.linalg.norm(radial, axis=1)
    unit = radial / np.maximum(r, 1e-12)[:, None]
    a = np.cross(u, [1.0, 0.0, 0.0]); a /= np.linalg.norm(a); b = np.cross(u, a)
    ang = np.arctan2(radial @ b, radial @ a)
    need = axis["radio_minimo"]
    lo, hi = axis["broca_hasta"] - 0.004, -0.010 * need / 0.01175
    # Superficie exterior cercana a la broca (mira hacia afuera del eje y no es el túnel interno).
    tri = P[triangles]
    face = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normal = np.zeros_like(P)
    for c in range(3):
        np.add.at(normal, triangles[:, c], face)
    facing = np.einsum("ij,ij->i", normal, unit) / np.maximum(np.linalg.norm(normal, axis=1), 1e-12)
    outer = (facing > 0.3) & (r > 0.25 * need)
    # Mapa de lo que falta (alto a lo largo del eje × ángulo alrededor), engrosado y suavizado.
    dk = 0.002 * need / 0.01175
    kb = np.round((k - lo) / dk).astype(int)
    nk = int(np.ceil((hi - lo) / dk)) + 1
    na = 36
    ab = np.floor((ang + np.pi) / (2 * np.pi) * na).astype(int) % na
    grid = np.zeros((nk + 40, na))
    sel = outer & (k >= lo) & (k <= hi) & (r < need)
    np.maximum.at(grid, (kb[sel] + 20, ab[sel]), need - r[sel])
    for _ in range(3):  # ensanchar la zona de cada déficit
        grid = np.maximum.reduce([grid, np.roll(grid, 1, 0), np.roll(grid, -1, 0), np.roll(grid, 1, 1), np.roll(grid, -1, 1)])
    kernel_k = np.exp(-0.5 * (np.arange(-12, 13) / 5.0) ** 2); kernel_k /= kernel_k.sum()
    kernel_a = np.exp(-0.5 * (np.arange(-4, 5) / 1.8) ** 2); kernel_a /= kernel_a.sum()
    peak = grid.max()
    grid = np.apply_along_axis(lambda c: np.convolve(c, kernel_k, mode="same"), 0, grid)
    grid = np.apply_along_axis(lambda c: np.convolve(np.r_[c[-4:], c, c[:4]], kernel_a, mode="valid"), 1, grid)
    if grid.max() > 0:
        grid *= peak / grid.max()  # el suavizado no debe quedarse corto en el punto más angosto
    # Lectura suave del mapa (bilineal), solo para la superficie exterior: el túnel interno no se mueve.
    fk = np.clip((k - lo) / dk + 20, 0, grid.shape[0] - 1.001)
    fa = (ang + np.pi) / (2 * np.pi) * na - 0.5
    k0 = np.floor(fk).astype(int); tk = fk - k0
    a0 = np.floor(fa).astype(int); ta = fa - a0
    a0m, a1m = a0 % na, (a0 + 1) % na
    value = ((1 - tk) * ((1 - ta) * grid[k0, a0m] + ta * grid[k0, a1m])
             + tk * ((1 - ta) * grid[k0 + 1, a0m] + ta * grid[k0 + 1, a1m]))
    push = np.where(r > 0.25 * need, value, 0.0)  # todo junto: la superficie se desplaza sin doblarse
    out = P + unit * push[:, None]
    print(f"   hueso ensanchado alrededor de la broca: {int((push > 1e-4).sum())} puntos, hasta {push.max() * 1000:.1f} mm")
    return out


def refine(points, triangles, axis=None):
    n = len(points)
    P = points.astype(np.float64)
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    a, b = np.minimum(edges[:, 0], edges[:, 1]), np.maximum(edges[:, 0], edges[:, 1])
    key = a.astype(np.int64) * n + b
    uniq, counts = np.unique(key, return_counts=True)
    ea, eb = uniq // n, uniq % n
    fixed = np.zeros(n, bool)
    fixed[ea[counts == 1]] = True
    fixed[eb[counts == 1]] = True
    src = np.concatenate([ea, eb])
    dst = np.concatenate([eb, ea])
    deg = np.bincount(src, minlength=n).astype(np.float64)
    deg[deg == 0] = 1
    move = (~fixed)[:, None]
    original = P.copy()
    steps = [LAMBDA] * SMOOTH + [LAMBDA, MU] * PASSES
    for factor in steps:
        if True:
            avg = np.stack([np.bincount(src, weights=P[dst, k], minlength=n) for k in range(3)], axis=1) / deg[:, None]
            P = np.where(move, P + factor * (avg - P), P)
    shift = P - original
    length = np.linalg.norm(shift, axis=1)
    # Tope gradual: los movimientos grandes se frenan suavemente (sin cortes bruscos entre vecinos).
    soft = MAX_SHIFT * np.tanh(length / MAX_SHIFT)
    shift *= (soft / np.maximum(length, 1e-12))[:, None]
    P = original + shift
    # Diáfisis con contornos continuos.
    P = np.where(move, shaft(P), P)
    # Hueso suficiente alrededor de la broca (si el archivo trae el eje del instrumental).
    P = np.where(move, around_drill(P, axis, triangles), P)
    # Pasadas finales de Taubin para dejar sin marcas las transiciones.
    for factor in [LAMBDA, MU] * 30:
        avg = np.stack([np.bincount(src, weights=P[dst, k], minlength=n) for k in range(3)], axis=1) / deg[:, None]
        P = np.where(move, P + factor * (avg - P), P)
    # Normales suaves sobre toda la superficie (sin línea entre mitades).
    tri = P[triangles]
    face = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    N = np.zeros_like(P)
    for k in range(3):
        np.add.at(N, triangles[:, k], face)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return P, N, length


def _trs(node):
    from math import isclose  # noqa: F401
    t = np.array(node.get("translation", [0, 0, 0]), float)
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4)
    M[:3, :3] = R * np.array(node.get("scale", [1, 1, 1]), float)[None, :]
    M[:3, 3] = t
    return M


def local_axis(doc, mesh_index):
    """El eje del instrumental (en coordenadas del mundo) llevado a las coordenadas de la malla del fémur."""
    axis = doc.get("extras", {}).get("eje_instrumental")
    if not axis:
        return None
    parents = {c: i for i, n in enumerate(doc["nodes"]) for c in n.get("children", [])}
    node = next(i for i, n in enumerate(doc["nodes"]) if n.get("mesh") == mesh_index)
    M = np.eye(4)
    while node is not None:
        M = _trs(doc["nodes"][node]) @ M
        node = parents.get(node)
    inv = np.linalg.inv(M)
    scale = np.cbrt(abs(np.linalg.det(M[:3, :3])))
    E = (inv @ np.array([*axis["entrada"], 1]))[:3]
    u = inv[:3, :3] @ np.asarray(axis["direccion"], float)
    return {**axis, "entrada": E.tolist(), "direccion": (u / np.linalg.norm(u)).tolist(),
            "broca_desde": axis["broca_desde"] / scale, "broca_hasta": axis["broca_hasta"] / scale,
            "radio_minimo": axis["radio_minimo"] / scale}


def main(src_path, dst_path):
    data, doc, bin_start = read_glb(src_path)
    done = set()
    for mesh_index, mesh in enumerate(doc["meshes"]):
        names = [mesh.get("name", "")] + [nd.get("name", "") for nd in doc["nodes"] if nd.get("mesh") == mesh_index]
        joined = " ".join(names)
        if not FEMUR.search(joined) or NOT_BONE.search(joined):
            continue
        prims = [p for p in mesh["primitives"] if p["attributes"]["POSITION"] not in done]
        if not prims:
            continue
        # Soldar todas las primitivas (las mitades) en una sola superficie.
        ids, points, maps, tris = {}, [], [], []
        for prim in prims:
            pos, offs, _ = accessor_view(data, doc, bin_start, prim["attributes"]["POSITION"])
            keys = np.round(pos.astype(np.float64) * 1e6).astype(np.int64)
            local = np.empty(len(pos), np.int64)
            for i, k in enumerate(map(tuple, keys)):
                if k not in ids:
                    ids[k] = len(points)
                    points.append(pos[i])
                local[i] = ids[k]
            maps.append((prim, local, offs))
            if "indices" in prim:
                idx, _, _ = accessor_view(data, doc, bin_start, prim["indices"])
                idx = idx.ravel().astype(np.int64)
            else:
                idx = np.arange(len(pos))
            t = local[idx].reshape(-1, 3)
            t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
            tris.append(t)
        P, N, moved = refine(np.array(points), np.concatenate(tris), local_axis(doc, mesh_index))
        for prim, local, offs in maps:
            write_floats(data, offs, P[local])
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            acc["min"] = P[local].min(axis=0).astype(float).tolist()
            acc["max"] = P[local].max(axis=0).astype(float).tolist()
            if "NORMAL" in prim["attributes"]:
                _, noffs, _ = accessor_view(data, doc, bin_start, prim["attributes"]["NORMAL"])
                write_floats(data, noffs, N[local])
            done.add(prim["attributes"]["POSITION"])
        print(f"{joined[:40]:40s} puntos {len(points):6d}  movimiento medio {moved.mean() * 1000:.2f} mm, máximo {moved.max() * 1000:.2f} mm")
    # Reescribir el JSON (mismo tamaño o con relleno) y guardar.
    text = json.dumps(doc, separators=(",", ":")).encode()
    text += b" " * ((4 - len(text) % 4) % 4)
    old_len = struct.unpack_from("<I", data, 12)[0]
    body = bytes(data[20 + old_len:])
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(text) + len(body)) + struct.pack("<II", len(text), 0x4E4F534A) + text + body
    open(dst_path, "wb").write(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
