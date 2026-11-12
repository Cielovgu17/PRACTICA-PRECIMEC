"""Aligera un GLB: junta los puntos de las mallas muy densas que quedan a menos de CELL de distancia (agrupación
en una cuadrícula) y vuelve a armar el archivo sin los datos que quedan sin usar.

    python ilustraciones/aligerar.py entrada.glb salida.glb [celda_mm] [min_puntos]

No cambia nombres, materiales, animaciones ni la posición de nada; solo baja el número de puntos y triángulos de
las mallas que tienen más de min_puntos (por defecto 150 000) con una celda de 0,2 mm.
"""
import json
import struct
import sys

import numpy as np

COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
DTYPES = {5120: "<i1", 5121: "<u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}


def read(path):
    data = open(path, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + json_len])
    start = 20 + json_len + 8
    return doc, memoryview(data)[start:]


def accessor(doc, binary, index):
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    n = COMPONENTS[acc["type"]]
    dtype = np.dtype(DTYPES[acc["componentType"]])
    stride = view.get("byteStride", 0) or dtype.itemsize * n
    offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    raw = np.frombuffer(binary, dtype=np.uint8, count=stride * (acc["count"] - 1) + dtype.itemsize * n, offset=offset)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(acc["count"], dtype.itemsize * n), strides=(stride, 1))
    return np.ascontiguousarray(rows).view(dtype).reshape(acc["count"], n)


def cell_code(positions, cell):
    k = np.floor(positions / cell).astype(np.int64) + (1 << 20)
    return (k[:, 0] << 42) | (k[:, 1] << 21) | k[:, 2]


def shared_clusters(parts, cell):
    """Promedios por celda de TODAS las partes de una pieza. Blender parte las piezas grandes en muchas partes;
    si cada parte se promediara por separado, sus bordes dejarían de coincidir y quedarían rendijas."""
    codes = np.concatenate([cell_code(p, cell) for p, _ in parts])
    ucodes, inverse, counts = np.unique(codes, return_inverse=True, return_counts=True)
    pos = np.zeros((len(ucodes), 3))
    np.add.at(pos, inverse, np.concatenate([p for p, _ in parts]))
    pos /= counts[:, None]
    nor = None
    if all(n is not None for _, n in parts):
        nor = np.zeros((len(ucodes), 3))
        np.add.at(nor, inverse, np.concatenate([n for _, n in parts]))
        nor /= np.maximum(np.linalg.norm(nor, axis=1, keepdims=True), 1e-12)
    return ucodes, pos, nor


def simplify(positions, normals, extra, indices, cell, shared=None):
    keys = np.floor(positions / cell).astype(np.int64)
    _, cluster, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    cluster = cluster.ravel()
    k = len(counts)
    def mean(values):
        out = np.zeros((k, values.shape[1]))
        np.add.at(out, cluster, values)
        return out / counts[:, None]
    pos = mean(positions)
    nor = None
    if normals is not None:
        nor = np.zeros((k, 3))
        np.add.at(nor, cluster, normals)
        nor /= np.maximum(np.linalg.norm(nor, axis=1, keepdims=True), 1e-12)
    if shared is not None:                       # mismos puntos que las demás partes de la pieza
        ucodes, spos, snor = shared
        first = np.zeros(k, np.int64)
        first[cluster] = np.arange(len(cluster))
        row = np.searchsorted(ucodes, cell_code(positions[first], cell))
        pos = spos[row]
        if nor is not None and snor is not None:
            nor = snor[row]
    ext = {name: mean(v) for name, v in extra.items()}
    tri = cluster[indices.reshape(-1, 3)]
    keep = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    tri = tri[keep]
    _, first = np.unique(np.sort(tri, axis=1), axis=0, return_index=True)   # sin triángulos repetidos
    tri = tri[np.sort(first)]
    if nor is not None:
        # Al juntar puntos algunos triángulos quedan al revés (se ven como rayas o huecos): se voltean según la
        # dirección de la superficie en sus tres puntos.
        face = np.cross(pos[tri[:, 1]] - pos[tri[:, 0]], pos[tri[:, 2]] - pos[tri[:, 0]])
        flip = np.einsum("ij,ij->i", face, nor[tri].sum(axis=1)) < 0
        tri[flip] = tri[flip][:, [0, 2, 1]]
    return pos, nor, ext, tri


def main():
    src, dst = sys.argv[1:3]
    cell = float(sys.argv[3]) / 1000 if len(sys.argv) > 3 else 0.0002
    min_points = int(sys.argv[4]) if len(sys.argv) > 4 else 150_000
    doc, binary = read(src)
    # Las mallas que ya no usa ninguna pieza se quitan del archivo (y se renumeran las que quedan).
    used = sorted({n["mesh"] for n in doc["nodes"] if "mesh" in n})
    if len(used) < len(doc["meshes"]):
        renum = {old: new for new, old in enumerate(used)}
        doc["meshes"] = [doc["meshes"][i] for i in used]
        for n in doc["nodes"]:
            if "mesh" in n:
                n["mesh"] = renum[n["mesh"]]
    chunks, views = [], []

    def add(array, component, kind, target=None):
        array = np.ascontiguousarray(array, dtype=DTYPES[component])
        raw = array.tobytes()
        offset = sum(len(c) for c in chunks)
        chunks.append(raw + bytes((4 - len(raw) % 4) % 4))
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(raw)}
        if target:
            view["target"] = target
        views.append(view)
        acc = {"bufferView": len(views) - 1, "componentType": component, "count": len(array), "type": kind}
        if kind == "VEC3" and component == 5126 and target == 34962:
            acc["min"], acc["max"] = array.min(0).astype(float).tolist(), array.max(0).astype(float).tolist()
        return acc

    new_accessors = {}
    before = after = 0
    for mesh in doc["meshes"]:
        total = sum(doc["accessors"][p["attributes"]["POSITION"]]["count"] for p in mesh["primitives"])
        usable = lambda p: "indices" in p and p.get("mode", 4) == 4 and "targets" not in p
        shared = None
        if total >= min_points:
            shared = shared_clusters([(accessor(doc, binary, p["attributes"]["POSITION"]).astype(float),
                                       accessor(doc, binary, p["attributes"]["NORMAL"]).astype(float)
                                       if "NORMAL" in p["attributes"] else None)
                                      for p in mesh["primitives"] if usable(p)], cell)
        for prim in mesh["primitives"]:
            count = doc["accessors"][prim["attributes"]["POSITION"]]["count"]
            before += count
            if total < min_points or not usable(prim):
                after += count
                continue
            pos = accessor(doc, binary, prim["attributes"]["POSITION"]).astype(float)
            nor = accessor(doc, binary, prim["attributes"]["NORMAL"]).astype(float) if "NORMAL" in prim["attributes"] else None
            extra = {name: accessor(doc, binary, idx).astype(float) for name, idx in prim["attributes"].items()
                     if name not in ("POSITION", "NORMAL") and doc["accessors"][idx]["componentType"] == 5126}
            others = [name for name in prim["attributes"] if name not in ("POSITION", "NORMAL") and name not in extra]
            for name in others:
                del prim["attributes"][name]
            idx = accessor(doc, binary, prim["indices"]).ravel().astype(np.int64)
            p, n, e, tri = simplify(pos, nor, extra, idx, cell, shared)
            after += len(p)
            attrs = {"POSITION": ("new", add(p, 5126, "VEC3", 34962))}
            if n is not None:
                attrs["NORMAL"] = ("new", add(n, 5126, "VEC3", 34962))
            for name, v in e.items():
                attrs[name] = ("new", add(v, 5126, {2: "VEC2", 3: "VEC3", 4: "VEC4"}[v.shape[1]], 34962))
            prim["attributes"] = attrs
            component = 5123 if len(p) < 65535 else 5125
            prim["indices"] = ("new", add(tri.ravel(), component, "SCALAR", 34963))
            # Al juntar puntos, algunos triángulos quedan al revés; con una sola cara se verían como huecos.
            if "material" in prim:
                doc["materials"][prim["material"]]["doubleSided"] = True
            mesh["_antes"] = mesh.get("_antes", 0) + count
            mesh["_despues"] = mesh.get("_despues", 0) + len(p)

    for mesh in doc["meshes"]:
        if "_antes" in mesh:
            print(f"  {mesh['name']}: {mesh.pop('_antes')} -> {mesh.pop('_despues')} puntos")
    # Copia el resto de los accessors que se usan y arma la lista final sin lo que sobra.
    final = []
    mapping = {}

    def keep(index):
        if index not in mapping:
            acc = dict(doc["accessors"][index])
            data = accessor(doc, binary, index)
            dtype_component = acc["componentType"]
            new = add(data, dtype_component, acc["type"], doc["bufferViews"][acc["bufferView"]].get("target"))
            for k in ("normalized", "min", "max"):
                if k in acc:
                    new[k] = acc[k]
            final.append(new)
            mapping[index] = len(final) - 1
        return mapping[index]

    def place(value):
        if isinstance(value, tuple):
            final.append(value[1])
            return len(final) - 1
        return keep(value)

    for mesh in doc["meshes"]:
        for prim in mesh["primitives"]:
            prim["attributes"] = {k: place(v) for k, v in prim["attributes"].items()}
            if "indices" in prim:
                prim["indices"] = place(prim["indices"])
            if "targets" in prim:
                prim["targets"] = [{k: keep(v) for k, v in t.items()} for t in prim["targets"]]
    for anim in doc.get("animations", []):
        for s in anim["samplers"]:
            s["input"], s["output"] = keep(s["input"]), keep(s["output"])
    for skin in doc.get("skins", []):
        if "inverseBindMatrices" in skin:
            skin["inverseBindMatrices"] = keep(skin["inverseBindMatrices"])
    assert not doc.get("images"), "este script no copia imágenes"
    doc["accessors"] = final
    doc["bufferViews"] = views
    body = b"".join(chunks)
    doc["buffers"] = [{"byteLength": len(body)}]
    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()
    text += b" " * ((4 - len(text) % 4) % 4)
    out = (struct.pack("<III", 0x46546C67, 2, 28 + len(text) + len(body)) + struct.pack("<II", len(text), 0x4E4F534A)
           + text + struct.pack("<II", len(body), 0x004E4942) + body)
    open(dst, "wb").write(out)
    print(f"puntos {before} -> {after}; archivo {len(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
