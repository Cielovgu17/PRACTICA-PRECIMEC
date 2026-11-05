"""Reubica y agranda el fémur de las animaciones del canal medular (pasos 3.1 a 3.4), sin mover el instrumental.

    python ilustraciones/reubicar_femur.py base.glb entrada.glb salida.glb

`base.glb` es el archivo del que se toma la malla limpia del fémur (la del paso 3.2: una sola pieza, sin
costuras). El resultado reemplaza el fémur de `entrada.glb` y se guarda en `salida.glb`.
Se aplica una sola vez, sobre las versiones de las animaciones anteriores a este cambio (en el historial de
git): los archivos de `animaciones/` ya lo tienen aplicado.

El instrumental de los cuatro pasos baja por el eje CANAL_AXIS desde el punto ENTRY. En lugar de mover todas
sus pistas, se mueve el hueso para que quede bien alrededor de ese eje:

  1. Punto de entrada: vértice del trocánter mayor, en la unión del tercio anterior con los dos tercios
     posteriores (la línea roja de la guía de tercios, z = ENTRY_Z en el hueso original).
  2. Eje: la recta desde ese punto que mejor pasa por el centro del canal medular entre y = -0,06 y 0,12 m.
     El hueso se gira (0,6°) para que esa recta coincida con el eje del instrumental: el pin queda centrado.
  3. Tamaño: el fémur se agranda SCALE veces alrededor del punto de entrada.
  4. Región subtrocantérica: el modelo es angosto bajo el trocánter (5 mm de pared hacia anterolateral).
     Ahí se ensancha suavemente la pared alrededor del eje para que la broca de Φ16,5 mm y la parte
     proximal del clavo queden dentro del hueso con al menos WALL de distancia.
  5. Orificio de entrada: se cierra el que traía el modelo y se abre de nuevo en el punto de entrada del
     instrumental, con su mismo borde. Alrededor, la cara superior del trocánter conserva su altura: así
     calzan la cortical que retira el abridor, la abertura, el protector de tejidos y el túnel de la broca.

También se centra en el eje el canal medular esquemático y, en el paso 3.1, se mueve con el hueso la guía
de tercios del trocánter. El resto del archivo (instrumental, animaciones, cámaras) no cambia.
"""
import json
import re
import struct
import sys

import numpy as np

ENTRY = np.array([-0.0039, 0.2043, -0.0007])      # punto de entrada del instrumental (no cambia)
CANAL_AXIS = np.array([-0.02752, 0.99949, 0.01625])  # eje del instrumental, hacia arriba
CANAL_AXIS = CANAL_AXIS / np.linalg.norm(CANAL_AXIS)
OLD_HOLE = ENTRY                                    # centro del orificio que trae el modelo
ENTRY_Z = 0.0015          # línea del tercio anterior / dos tercios posteriores (guía del paso 3.1), en metros
SCALE = 1.12              # el hueso queda 12 % más grande
DRILL_RADIUS = 0.00825    # broca canulada y parte proximal del clavo, Φ16,5 mm
WALL = 0.0035             # pared mínima de hueso alrededor de la broca
CANAL_FIT = (-0.06, 0.12)  # tramo del canal (y en el hueso original) que define el eje
STITCH = 0.0015           # ancho de la franja que une el corte con el borde original
LOCK_INNER, LOCK_OUTER = 0.0125, 0.032  # alrededor del orificio la superficie conserva su altura original

COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
DTYPES = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}


# ---------- Lectura y escritura del GLB ----------

class Glb:
    def __init__(self, path):
        data = open(path, "rb").read()
        json_len = struct.unpack_from("<I", data, 12)[0]
        self.doc = json.loads(data[20:20 + json_len])
        bin_start = 20 + json_len + 8
        bin_len = struct.unpack_from("<I", data, 20 + json_len)[0]
        self.bin = bytearray(data[bin_start:bin_start + bin_len])

    def array(self, index):
        acc = self.doc["accessors"][index]
        view = self.doc["bufferViews"][acc["bufferView"]]
        n = COMPONENTS[acc["type"]]
        dtype = np.dtype(DTYPES[acc["componentType"]]).newbyteorder("<")
        stride = view.get("byteStride") or n * dtype.itemsize
        base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        raw = np.frombuffer(bytes(self.bin), dtype=np.uint8)
        idx = base + np.arange(acc["count"])[:, None] * stride + np.arange(n * dtype.itemsize)[None, :]
        return raw[idx].copy().view(dtype).reshape(acc["count"], n)

    def add(self, values, target=None):
        """Agrega un arreglo al final del bloque binario y devuelve su accessor."""
        values = np.ascontiguousarray(values)
        if values.dtype == np.float32:
            ctype, kind = 5126, {1: "SCALAR", 3: "VEC3"}[values.shape[1] if values.ndim > 1 else 1]
        else:
            values = values.astype("<u4")
            ctype, kind = 5125, "SCALAR"
        self.bin += b"\0" * ((4 - len(self.bin) % 4) % 4)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": values.nbytes}
        if target:
            view["target"] = target
        self.bin += values.tobytes()
        self.doc["bufferViews"].append(view)
        acc = {"bufferView": len(self.doc["bufferViews"]) - 1, "componentType": ctype,
               "count": int(len(values) if values.ndim > 1 else values.size), "type": kind}
        if ctype == 5126:
            acc["min"] = values.reshape(len(values), -1).min(axis=0).astype(float).tolist()
            acc["max"] = values.reshape(len(values), -1).max(axis=0).astype(float).tolist()
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def nodes(self, pattern):
        return [n for n in self.doc["nodes"] if re.match(pattern, n.get("name", "")) and "mesh" in n]

    def compact(self):
        """Quita del archivo los datos que ya nadie usa (p. ej. la malla anterior del fémur)."""
        doc = self.doc
        used_acc = set()
        for mesh in doc["meshes"]:
            for prim in mesh["primitives"]:
                used_acc.update(prim["attributes"].values())
                if "indices" in prim:
                    used_acc.add(prim["indices"])
        for anim in doc.get("animations", []):
            for sampler in anim["samplers"]:
                used_acc.update((sampler["input"], sampler["output"]))
        acc_map = {old: new for new, old in enumerate(sorted(used_acc))}
        accessors = [doc["accessors"][old] for old in sorted(used_acc)]
        used_views = {a["bufferView"] for a in accessors if "bufferView" in a}
        used_views |= {img["bufferView"] for img in doc.get("images", []) if "bufferView" in img}
        view_map, views, data = {}, [], bytearray()
        for old in sorted(used_views):
            view = dict(doc["bufferViews"][old])
            start = view.get("byteOffset", 0)
            data += b"\0" * ((4 - len(data) % 4) % 4)
            chunk = self.bin[start:start + view["byteLength"]]
            view["byteOffset"] = len(data)
            data += chunk
            view_map[old] = len(views)
            views.append(view)
        for a in accessors:
            if "bufferView" in a:
                a["bufferView"] = view_map[a["bufferView"]]
        for img in doc.get("images", []):
            if "bufferView" in img:
                img["bufferView"] = view_map[img["bufferView"]]
        for mesh in doc["meshes"]:
            for prim in mesh["primitives"]:
                prim["attributes"] = {k: acc_map[v] for k, v in prim["attributes"].items()}
                if "indices" in prim:
                    prim["indices"] = acc_map[prim["indices"]]
        for anim in doc.get("animations", []):
            for sampler in anim["samplers"]:
                sampler["input"], sampler["output"] = acc_map[sampler["input"]], acc_map[sampler["output"]]
        doc["accessors"], doc["bufferViews"], self.bin = accessors, views, data

    def save(self, path):
        self.compact()
        self.bin += b"\0" * ((4 - len(self.bin) % 4) % 4)
        self.doc["buffers"][0]["byteLength"] = len(self.bin)
        text = json.dumps(self.doc, separators=(",", ":")).encode()
        text += b" " * ((4 - len(text) % 4) % 4)
        total = 12 + 8 + len(text) + 8 + len(self.bin)
        with open(path, "wb") as out:
            out.write(struct.pack("<III", 0x46546C67, 2, total))
            out.write(struct.pack("<II", len(text), 0x4E4F534A) + text)
            out.write(struct.pack("<II", len(self.bin), 0x004E4942) + bytes(self.bin))


# ---------- Geometría ----------

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def rotation_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = a @ b
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def vertex_normals(points, tris):
    face = np.cross(points[tris[:, 1]] - points[tris[:, 0]], points[tris[:, 2]] - points[tris[:, 0]])
    normals = np.zeros_like(points)
    for k in range(3):
        np.add.at(normals, tris[:, k], face)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return normals / np.where(length > 0, length, 1)


def boundary_loops(tris):
    """Bordes abiertos, como listas de vértices en el sentido de los triángulos."""
    directed = np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    edges = {(int(a), int(b)) for a, b in directed}
    following = {a: b for a, b in edges if (b, a) not in edges}
    loops = []
    while following:
        start, current = following.popitem()
        loop = [start]
        while current != start and current in following:
            loop.append(current)
            current = following.pop(current)
        loops.append(loop)
    return loops


def fill_hole(points, tris, loop, rings=8, relax=300):
    """Cierra un orificio con una membrana: anillos concéntricos que luego se alisan con el borde fijo."""
    rim = points[loop]
    center = rim.mean(axis=0)
    n = len(loop)
    new_points = [points]
    ring_ids = [np.array(loop)]
    next_id = len(points)
    for k in range(1, rings):
        ring = center + (rim - center) * (1 - k / rings)
        new_points.append(ring)
        ring_ids.append(np.arange(next_id, next_id + n))
        next_id += n
    new_points.append(center[None, :])
    center_id = next_id
    points = np.vstack(new_points)
    faces = []
    for k in range(rings - 1):
        outer, inner = ring_ids[k], ring_ids[k + 1]
        for i in range(n):
            j = (i + 1) % n
            faces.append((outer[j], outer[i], inner[i]))
            faces.append((outer[j], inner[i], inner[j]))
    last = ring_ids[-1]
    for i in range(n):
        faces.append((last[(i + 1) % n], last[i], center_id))
    patch = np.array(faces)
    # Alisado tipo membrana: cada punto interior va al promedio de sus vecinos.
    inner_ids = np.arange(len(points) - (rings - 1) * n - 1, len(points))
    neighbors = {i: set() for i in inner_ids}
    for f in patch:
        for a in f:
            if a in neighbors:
                neighbors[a].update(int(b) for b in f if b != a)
    order = list(neighbors)
    lists = [np.array(sorted(neighbors[i])) for i in order]
    for _ in range(relax):
        points[order] = np.array([points[l].mean(axis=0) for l in lists])
    return points, np.vstack([tris, patch])


def ray_hit(points, tris, origin, direction):
    """Primer cruce de una semirrecta con la malla (Möller-Trumbore, para todos los triángulos a la vez)."""
    v0, v1, v2 = points[tris[:, 0]], points[tris[:, 1]], points[tris[:, 2]]
    e1, e2 = v1 - v0, v2 - v0
    p = np.cross(direction, e2)
    det = (e1 * p).sum(axis=1)
    ok = np.abs(det) > 1e-14
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = origin - v0
    u = (s * p).sum(axis=1) * inv
    q = np.cross(s, e1)
    v = (q @ direction) * inv
    t = (q * e2).sum(axis=1) * inv
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0)
    return origin + direction * t[hit].min() if hit.any() else None


def axial(points):
    """Altura a lo largo del eje del instrumental (negativa hacia distal) y vector perpendicular."""
    rel = points - ENTRY
    t = rel @ CANAL_AXIS
    return t, rel - np.outer(t, CANAL_AXIS)


def canal_centers(canal, y_range):
    ys = np.arange(y_range[0], y_range[1] + 1e-9, 0.01)
    centers = []
    for y in ys:
        s = canal[np.abs(canal[:, 1] - y) < 0.002]
        centers.append([(s[:, 0].min() + s[:, 0].max()) / 2, y, (s[:, 2].min() + s[:, 2].max()) / 2])
    return np.array(centers)


def plan(points, tris, canal):
    """Punto de entrada y eje en el hueso original, y la transformación que los lleva al instrumental."""
    centers = canal_centers(canal, CANAL_FIT)
    top = 0.205
    dy = centers[:, 1] - top
    # Recta desde el vértice del trocánter (x del orificio original, z en la línea del tercio) que mejor pasa
    # por el centro del canal: el pin entra por el trocánter y baja centrado.
    slope_x = np.sum(dy * (centers[:, 0] - OLD_HOLE[0])) / np.sum(dy * dy)
    slope_z = np.sum(dy * (centers[:, 2] - ENTRY_Z)) / np.sum(dy * dy)
    x0 = OLD_HOLE[0]
    direction = np.array([slope_x, 1.0, slope_z])
    direction /= np.linalg.norm(direction)
    start = np.array([x0, top, ENTRY_Z]) + direction * 0.05
    entry = ray_hit(points, tris, start, -direction)
    rotation = rotation_between(direction, CANAL_AXIS)
    return entry, direction, rotation


def place(points, entry, rotation):
    return ENTRY + SCALE * (points - entry) @ rotation.T


def widen(points):
    """Ensancha la pared alrededor del eje bajo el trocánter: r' = √(r² + a²), con a suave en altura."""
    t, perp = axial(points)
    depth = -t
    reach = (DRILL_RADIUS + WALL) * smoothstep(0.02, 0.04, depth) * (1 - smoothstep(0.10, 0.14, depth))
    r = np.linalg.norm(perp, axis=1)
    factor = np.sqrt(r * r + reach * reach) / np.where(r > 0, r, 1)
    return ENTRY + np.outer(t, CANAL_AXIS) + perp * factor[:, None]


def basis():
    u = np.cross(CANAL_AXIS, [0.0, 0.0, 1.0])
    u /= np.linalg.norm(u)
    return u, np.cross(CANAL_AXIS, u)


def angle_of(perp):
    u, v = basis()
    return np.arctan2(perp @ v, perp @ u)


def rim_profile(points, loop):
    """Contorno del orificio original (radio y altura en cada dirección alrededor del eje): la cortical que
    retira el abridor y la abertura calzan con él."""
    height, perp = axial(points[loop])
    angle = angle_of(perp)
    order = np.argsort(angle)
    angle, radius, height = angle[order], np.linalg.norm(perp, axis=1)[order], height[order]
    around = np.r_[angle - 2 * np.pi, angle, angle + 2 * np.pi]
    return lambda a: (np.interp(a, around, np.tile(radius, 3)), np.interp(a, around, np.tile(height, 3)))


def top_height(points, tris, perp):
    """Altura (a lo largo del eje) de la cara superior del hueso en cada posición perpendicular dada."""
    t, p = axial(points)
    centroid_r = np.linalg.norm(p[tris].mean(axis=1), axis=1)
    near = tris[(centroid_r < LOCK_OUTER + 0.006) & (t[tris].mean(axis=1) > -0.04)]
    heights = []
    for q in perp:
        hit = ray_hit(points, near, ENTRY + q + CANAL_AXIS * 0.06, -CANAL_AXIS)
        heights.append(np.nan if hit is None else (hit - ENTRY) @ CANAL_AXIS)
    return np.array(heights)


def keep_entry_surface(points, tris, old_points):
    """Alrededor del orificio, la cara superior del hueso queda a la altura que tenía: así la cortical que
    retira el abridor, la abertura y el protector de tejidos siguen apoyados en el hueso como antes.
    La diferencia de altura se mide en una grilla polar alrededor del eje, se alisa y se aplica suave."""
    u, v = basis()
    radii = np.linspace(0, LOCK_OUTER, 33)
    angles = np.linspace(-np.pi, np.pi, 73)[:-1]
    rr, aa = np.meshgrid(radii, angles, indexing="ij")
    grid = np.outer(np.cos(aa).ravel() * rr.ravel(), u) + np.outer(np.sin(aa).ravel() * rr.ravel(), v)
    new_top = top_height(points, tris, grid).reshape(rr.shape)
    old_top = top_height(old_points, tris, grid).reshape(rr.shape)
    delta = np.clip(np.nan_to_num(old_top - new_top), -0.012, 0.012)
    delta[np.isnan(new_top) | np.isnan(old_top)] = 0
    for _ in range(4):  # alisado: promedio con los vecinos en radio y en ángulo
        delta = (2 * delta + np.roll(delta, 1, 1) + np.roll(delta, -1, 1)
                 + np.vstack([delta[:1], delta[:-1]]) + np.vstack([delta[1:], delta[-1:]])) / 6
    new_top = np.where(np.isnan(new_top), -1.0, new_top)

    t, perp = axial(points)
    r = np.linalg.norm(perp, axis=1)
    region = np.nonzero((r < LOCK_OUTER) & (t > -0.035) & (t < 0.05))[0]
    fr = r[region] / LOCK_OUTER * (len(radii) - 1)
    fa = (angle_of(perp[region]) + np.pi) / (2 * np.pi) * len(angles)
    r0, a0 = np.floor(fr).astype(int).clip(0, len(radii) - 2), np.floor(fa).astype(int) % len(angles)
    a1 = (a0 + 1) % len(angles)
    wr, wa = (fr - r0).clip(0, 1), fa - np.floor(fa)

    def sample(field):
        return ((1 - wr) * ((1 - wa) * field[r0, a0] + wa * field[r0, a1])
                + wr * ((1 - wa) * field[r0 + 1, a0] + wa * field[r0 + 1, a1]))

    top_here = sample(new_top)
    weight = (1 - smoothstep(LOCK_INNER, LOCK_OUTER, r[region])) * (1 - smoothstep(0.002, 0.008, top_here - t[region]))
    points = points.copy()
    points[region] += np.outer(weight * sample(delta), CANAL_AXIS)
    return points


def open_hole(points, tris, radius_at, rim):
    """Abre el orificio de entrada en el eje del instrumental con exactamente el borde original (`rim`, en el
    orden de sus triángulos): se corta un poco más ancho y se cose una franja angosta hasta ese borde."""
    centroid = points[tris].mean(axis=1)
    centroid_t, cperp = axial(centroid)
    limit = radius_at(angle_of(cperp))[0] + STITCH
    inside = (np.linalg.norm(cperp, axis=1) < limit) & (centroid_t > -0.03) & (centroid_t < 0.03)
    tris = tris[~inside]
    _, perp = axial(points)
    loops = [l for l in boundary_loops(tris) if np.linalg.norm(perp[l].mean(axis=0)) < 0.006]
    assert len(loops) == 1, f"se esperaba un borde al cortar, hay {len(loops)}"
    outer = np.array(loops[0])
    # El borde del corte queda en un contorno parejo, a STITCH del borde original.
    t, perp = axial(points[outer])
    radius = radius_at(angle_of(perp))[0] + STITCH
    points = points.copy()
    points[outer] = ENTRY + np.outer(t, CANAL_AXIS) + perp / np.linalg.norm(perp, axis=1, keepdims=True) * radius[:, None]
    inner = np.arange(len(points), len(points) + len(rim))
    points = np.vstack([points, rim])

    ao = np.unwrap(angle_of(axial(points[outer])[1]))
    ai = np.unwrap(angle_of(axial(points[inner])[1]))
    turn = np.sign(ao[-1] - ao[0])
    assert turn == np.sign(ai[-1] - ai[0]), "los bordes giran en sentidos opuestos"
    ao, ai = ao * turn, ai * turn  # ángulos crecientes en el sentido de los bordes
    # Ambos bordes desde el mismo ángulo y dando una vuelta completa.
    k = int(np.argmin(np.abs((ai - ao[0] + np.pi) % (2 * np.pi) - np.pi)))
    inner, ai = np.roll(inner, -k), np.roll(ai, -k)
    ai = ao[0] + np.unwrap(ai - ai[0]) + ((ai[0] - ao[0] + np.pi) % (2 * np.pi) - np.pi)
    ao_c, ai_c = np.r_[ao, ao[0] + 2 * np.pi], np.r_[ai, ai[0] + 2 * np.pi]
    oc, ic = np.r_[outer, outer[0]], np.r_[inner, inner[0]]
    i = j = 0
    strip = []
    while i < len(inner) or j < len(outer):
        if j < len(outer) and (i == len(inner) or ao_c[j + 1] <= ai_c[i + 1]):
            strip.append((oc[j + 1], oc[j], ic[i]))
            j += 1
        else:
            strip.append((ic[i], ic[i + 1], oc[j]))
            i += 1
    tris = np.vstack([tris, np.array(strip)])
    used = np.unique(tris)
    remap = -np.ones(len(points), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return points[used], remap[tris]


def center_canal(points):
    """Lleva el centro del canal esquemático al eje del instrumental en el tramo que recorre el pin."""
    t, perp = axial(points)
    bins = np.round(t / 0.004).astype(int)
    offset = np.zeros_like(points)
    keys = np.unique(bins)
    means = {k: perp[bins == k].mean(axis=0) for k in keys}
    # promedio móvil de tres tramos para que el centro cambie suave
    smooth = {k: np.mean([means[j] for j in (k - 1, k, k + 1) if j in means], axis=0) for k in keys}
    offset = np.array([smooth[k] for k in bins])
    depth = -t
    weight = smoothstep(-0.01, 0.02, depth) * (1 - smoothstep(0.27, 0.33, depth))
    return points - offset * weight[:, None]


# ---------- Programa ----------

def base_femur(glb):
    node = glb.nodes(r"Femur_derecho")[0]
    prims = glb.doc["meshes"][node["mesh"]]["primitives"]
    assert len(prims) == 1, "la base debe tener el fémur en una sola pieza (paso 3.2)"
    points = glb.array(prims[0]["attributes"]["POSITION"]).astype(float)
    tris = glb.array(prims[0]["indices"]).reshape(-1, 3).astype(np.int64)
    keys, inverse = np.unique(np.round(points / 1e-5).astype(np.int64), axis=0, return_inverse=True)
    welded = np.zeros((len(keys), 3))
    welded[inverse.ravel()] = points
    return welded, inverse.ravel()[tris]


def build_femur(base_path, canal):
    points, tris = base_femur(Glb(base_path))
    loops = [l for l in boundary_loops(tris) if np.linalg.norm(points[l].mean(axis=0) - OLD_HOLE) < 0.015]
    assert len(loops) == 1, f"se esperaba un orificio de entrada, hay {len(loops)}"
    radius_at = rim_profile(points, loops[0])
    rim = points[loops[0]]  # el borde original queda tal cual: calza con la cortical y la abertura
    original, tris = fill_hole(points, tris, loops[0])
    entry, direction, rotation = plan(original, tris, canal)
    print(f"entrada en el hueso original: {np.round(entry, 4)}; eje {np.round(direction, 4)}; "
          f"giro {np.degrees(np.arccos(np.clip(direction @ CANAL_AXIS, -1, 1))):.2f}°")
    points = widen(place(original, entry, rotation))
    points = keep_entry_surface(points, tris, original)
    points, tris = open_hole(points, tris, radius_at, rim)
    return points, tris, entry, rotation


def main(base_path, src, dst):
    glb = Glb(src)
    canal_nodes = glb.nodes(r"Canal_medular_esquematico")
    canal_prim = glb.doc["meshes"][canal_nodes[0]["mesh"]]["primitives"][0]
    canal = glb.array(canal_prim["attributes"]["POSITION"]).astype(float)
    points, tris, entry, rotation = build_femur(base_path, canal)
    normals = vertex_normals(points, tris)
    pos_acc = glb.add(points.astype(np.float32), 34962)
    nor_acc = glb.add(normals.astype(np.float32), 34962)
    idx_acc = glb.add(tris.ravel().astype(np.uint32), 34963)
    for node in glb.nodes(r"Femur_derecho"):
        mesh = glb.doc["meshes"][node["mesh"]]
        material = mesh["primitives"][0].get("material")
        prim = {"attributes": {"POSITION": pos_acc, "NORMAL": nor_acc}, "indices": idx_acc, "mode": 4}
        if material is not None:
            prim["material"] = material
        mesh["primitives"] = [prim]
        print("fémur reemplazado:", node["name"])

    done = {}
    for node in canal_nodes:
        for prim in glb.doc["meshes"][node["mesh"]]["primitives"]:
            key = prim["attributes"]["POSITION"]
            if key not in done:
                cp = center_canal(place(glb.array(key).astype(float), entry, rotation))
                ct = glb.array(prim["indices"]).reshape(-1, 3).astype(np.int64)
                done[key] = (glb.add(cp.astype(np.float32), 34962), glb.add(vertex_normals(cp, ct).astype(np.float32), 34962))
            prim["attributes"]["POSITION"], prim["attributes"]["NORMAL"] = done[key]
        print("canal centrado:", node["name"])

    # Guía de tercios (paso 3.1): sus mallas están en coordenadas del hueso; se mueven con él.
    for node in glb.nodes(r"(Bordes_AP_trocanter|Linea_tercio)"):
        for prim in glb.doc["meshes"][node["mesh"]]["primitives"]:
            moved = place(glb.array(prim["attributes"]["POSITION"]).astype(float), entry, rotation)
            prim["attributes"]["POSITION"] = glb.add(moved.astype(np.float32), 34962)
            if "NORMAL" in prim["attributes"]:
                normals = glb.array(prim["attributes"]["NORMAL"]).astype(float) @ rotation.T
                prim["attributes"]["NORMAL"] = glb.add(normals.astype(np.float32), 34962)
        print("guía movida con el hueso:", node["name"])
    glb.save(dst)


if __name__ == "__main__":
    main(*sys.argv[1:4])
