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


def refine(points, triangles):
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
    # Pasadas finales de Taubin para dejar la transición del tope sin marcas.
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
        P, N, moved = refine(np.array(points), np.concatenate(tris))
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
