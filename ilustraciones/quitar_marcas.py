"""Quita de un GLB las marcas del hueso trabajado en la etapa del canal medular (hueco del abridor, túnel de la broca
de Φ16,5 y canal escariado). Se usan hasta el paso 5.4; desde el 5.5 ya no se muestran.

    python ilustraciones/quitar_marcas.py archivo.glb [otro.glb ...]

Cambia el archivo en su lugar: las piezas quedan sin malla (no se ven) y el resto del archivo no cambia.
"""
import json
import re
import struct
import sys

MARCAS = re.compile(r"^(Abertura_punto_entrada|Tunel_broca|Hueso_escariado|Canal_escariado)")


def quitar(path):
    data = open(path, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + json_len])
    quitadas = 0
    for node in doc["nodes"]:
        if MARCAS.match(node.get("name", "")) and "mesh" in node:
            del node["mesh"]
            quitadas += 1
    text = json.dumps(doc, separators=(",", ":")).encode()
    text += b" " * ((4 - len(text) % 4) % 4)
    body = data[20 + json_len:]
    out = struct.pack("<III", 0x46546C67, 2, 20 + len(text) + len(body)) + struct.pack("<II", len(text), 0x4E4F534A) + text + body
    open(path, "wb").write(out)
    print(f"{path}: {quitadas} marcas quitadas")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        quitar(p)
