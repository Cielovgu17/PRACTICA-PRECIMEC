"""Corrige profundidades en las animaciones del fresado del canal medular (archivos GLB de Blender).

    python ilustraciones/ajustar_animaciones.py paso32 entrada.glb salida.glb
    python ilustraciones/ajustar_animaciones.py paso33 entrada.glb salida.glb
    python ilustraciones/ajustar_animaciones.py paso34 entrada.glb salida.glb

Solo cambia valores de las pistas de movimiento (y la posición fija de alguna pieza); la geometría, las
escenas y los nombres quedan iguales. Coordenadas en metros, el fémur con su eje largo en y (arriba +y).

  * Pin guía roscado (Φ3,2 × 400 mm): entra PIN_EXTRA más en el hueso. Así su extremo superior queda
    por debajo del perforador del paso 3.4 y el perforador ya no lo atraviesa.
      - paso 3.2: el pin avanza más a medida que entra en el hueso; el mango que lo sostiene baja con él.
      - paso 3.3: el pin y el mango arrancan desde esa nueva profundidad.
      - paso 3.4: el pin queda en esa misma profundidad.
  * Broca canulada Φ16,5 (paso 3.4): se detiene con la punta en DRILL_STOP_Y. Más abajo el hueso se
    angosta y la broca salía hasta 3,2 mm por la pared; a esa altura queda toda dentro del hueso.
    El perforador se detiene con ella y no aparecen los anillos del túnel que quedaban más abajo.
"""
import json
import struct
import sys

import numpy as np

PIN_EXTRA = float(__import__("os").environ.get("PIN_EXTRA", 0.100))  # el pin llega a 250 mm desde la superficie
PIN_AXIS = np.array([-0.0488, 0.9987, 0.0170])      # dirección del pin, de la punta hacia arriba
PIN_AXIS = PIN_AXIS / np.linalg.norm(PIN_AXIS)
ENTRY_Y = 0.2135                                    # altura del punto de entrada en el trocánter mayor
ENTRY = np.array([-0.0039, 0.2043, -0.0007])        # punto de entrada (centro del orificio del abridor)
# Eje del canal medular: recta por el punto de entrada ajustada a los centros del canal entre y=-0,10 y 0,12.
# El pin, el protector, la broca y el perforador se giran (~2°) alrededor de la entrada para seguirlo.
# Ajustado además 1° y 0,5° para que la broca y el pin queden lo más centrados posible en el hueso y el canal.
# El instrumental conserva su recorrido original: es el hueso el que se acomoda a él (ver anatomia()).
CANAL_AXIS = PIN_AXIS.copy()
# El protector de tejidos se apoya sobre el hueso (antes entraba 17,5 mm en él): se sube a lo largo del eje.
# Con el hueso acomodado (escala 1,15), la camisa queda apoyada en el borde del orificio de entrada.
# El protector se apoya en la superficie del hueso, en la punta del trocánter.
PROTECTOR_LIFT = float(__import__("os").environ.get("PROTECTOR_LIFT", 0.0275))
# La broca baja hasta que su tope toca el borde superior de la camisa del protector: en la animación original
# eso ocurre con la punta en y=0,1203; con el protector 17,5 mm más arriba, el tope toca 17,5 mm antes.
DRILL_STOP_Y = float(__import__("os").environ.get("DRILL_STOP_Y", 0.1203 + PROTECTOR_LIFT))
TINY = 1e-4


class Glb:
    def __init__(self, path):
        self.data = bytearray(open(path, "rb").read())
        self.json_len = struct.unpack_from("<I", self.data, 12)[0]
        self.doc = json.loads(self.data[20:20 + self.json_len])
        self.bin = 20 + self.json_len + 8

    def array(self, index):
        acc = self.doc["accessors"][index]
        view = self.doc["bufferViews"][acc["bufferView"]]
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
        assert acc["componentType"] == 5126 and not view.get("byteStride"), "solo flotantes sin intercalar"
        start = self.bin + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        return np.frombuffer(self.data, dtype="<f4", count=acc["count"] * n, offset=start).reshape(acc["count"], n)

    def set_array(self, index, values):
        target = self.array(index)
        target[...] = values  # misma memoria que el archivo
        acc = self.doc["accessors"][index]
        if "min" in acc:
            acc["min"] = values.min(axis=0).astype(float).tolist()
            acc["max"] = values.max(axis=0).astype(float).tolist()

    def clip(self, name):
        return next(a for a in self.doc["animations"] if a["name"] == name)

    def track(self, clip, node_name, path):
        for ch in clip["channels"]:
            if self.doc["nodes"][ch["target"]["node"]]["name"] == node_name and ch["target"]["path"] == path:
                s = clip["samplers"][ch["sampler"]]
                return s["input"], s["output"]
        return None

    def node(self, name):
        return next(n for n in self.doc["nodes"] if n["name"] == name)

    def save(self, path):
        text = json.dumps(self.doc, separators=(",", ":")).encode()
        text += b" " * ((4 - len(text) % 4) % 4)
        body = bytes(self.data[20 + self.json_len:])
        out = struct.pack("<III", 0x46546C67, 2, 20 + len(text) + len(body)) + struct.pack("<II", len(text), 0x4E4F534A) + text + body
        open(path, "wb").write(out)


def quat_between(a, b):
    """Cuaternión (x, y, z, w) que gira el vector a hasta el vector b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    axis = np.cross(a, b)
    s = np.linalg.norm(axis)
    angle = np.arctan2(s, a @ b)
    axis = axis / s
    return np.array([*(axis * np.sin(angle / 2)), np.cos(angle / 2)])


def quat_mul(q, r):
    x1, y1, z1, w1 = q
    x2, y2, z2, w2 = r.T
    return np.stack([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
                     w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2], axis=1)


def quat_matrix(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


ALIGN = np.array([0.0, 0.0, 0.0, 1.0])


def realign(g, clip, names):
    """(Ya no se usa) Giraba el instrumental hacia el canal; ahora se mueve el hueso con anatomia()."""
    if np.allclose(ALIGN, [0, 0, 0, 1]):
        return
    R = quat_matrix(ALIGN)
    done = set()  # Blender guarda una sola vez los movimientos idénticos: cada dato se gira una sola vez
    for name in names:
        node = g.node(name)
        moved = False
        tr = g.track(clip, name, "translation")
        if tr and tr[1] not in done:
            values = g.array(tr[1]).astype(float)
            g.set_array(tr[1], (ENTRY + (values - ENTRY) @ R.T).astype(np.float32))
            done.add(tr[1])
        moved = bool(tr)
        ro = g.track(clip, name, "rotation")
        if ro and ro[1] not in done:
            g.set_array(ro[1], quat_mul(ALIGN, g.array(ro[1]).astype(float)).astype(np.float32))
            done.add(ro[1])
        t = np.array(node.get("translation", [0, 0, 0]), float)
        node["translation"] = (ENTRY + R @ (t - ENTRY)).tolist()
        q = np.array(node.get("rotation", [0, 0, 0, 1]), float)
        node["rotation"] = quat_mul(ALIGN, q[None, :])[0].tolist()
        print(f"   girado: {name}{' (con su recorrido)' if moved else ''}")


# ---------- Hueso acomodado al instrumental ----------
# La entrada va en la punta del trocánter mayor (su parte más alta, como en la técnica de Kangli). El
# instrumental conserva su recorrido; el hueso se ubica con esa punta en la entrada del instrumental (ENTRY,
# 10 mm más arriba a lo largo del eje: la superficie) y se gira para que el canal siga al pin guía.
# Elegido midiendo: pin dentro del canal en sus 250 mm, a 6 mm de la superficie del hueso; broca a 5,7 mm de la pared.
TROCHANTER_TIP = np.array([-0.0037, 0.2143, -0.0163])   # en las coordenadas propias del fémur
OLD_HOLE = np.array([-0.0039, 0.2043, -0.0007])         # orificio que traía el modelo (se tapa en femur_limpio.py)
SURFACE_UP = 0.010
BONE_SCALE = float(__import__("os").environ.get("BONE_SCALE", 1.05))
BONE_EULER = (np.radians(6.5), 0.0, np.radians(1.5))     # giro (x, y, z) alrededor de la punta


def euler_xyz_quat(rx, ry, rz):
    cx, sx = np.cos(rx / 2), np.sin(rx / 2)
    cy, sy = np.cos(ry / 2), np.sin(ry / 2)
    cz, sz = np.cos(rz / 2), np.sin(rz / 2)
    return np.array([sx * cy * cz + cx * sy * sz, cx * sy * cz - sx * cy * sz,
                     cx * cy * sz + sx * sy * cz, cx * cy * cz - sx * sy * sz])  # orden XYZ como Three.js


def bone_transform():
    """p -> A + S·R·(p - punta): traslación, giro (x, y, z, w) y escala del grupo Anatomia."""
    q = euler_xyz_quat(*BONE_EULER)
    R = quat_matrix(q)
    A = ENTRY + SURFACE_UP * PIN_AXIS
    t = A - BONE_SCALE * R @ TROCHANTER_TIP
    return t, q, BONE_SCALE


def anatomia(g):
    t, q, s = bone_transform()
    R = quat_matrix(q)
    Ri = R.T
    inverse_q = [-q[0], -q[1], -q[2], q[3]]
    for node in g.doc["nodes"]:
        name = node["name"]
        if name.startswith("Anatomia"):
            assert not any(k in node for k in ("translation", "rotation", "scale", "matrix")), name
            node["translation"], node["rotation"], node["scale"] = t.tolist(), q.tolist(), [s, s, s]
        elif name.startswith(("Tunel_broca_16.5", "Abertura_punto_entrada", "Cortical_retirada_por_el_abridor")):
            # Lo hace el instrumental: sigue al instrumental, no al hueso. La abertura sube a la superficie nueva.
            delta = np.zeros(3) if name.startswith("Tunel") else SURFACE_UP * PIN_AXIS
            base = np.array(node.get("translation", [0, 0, 0]), float)
            node["translation"] = ((Ri @ (base + delta - t)) / s).tolist()
            node["rotation"] = quat_mul(np.array(inverse_q), np.array([node.get("rotation", [0, 0, 0, 1])], float))[0].tolist()
            node["scale"] = (np.array(node.get("scale", [1, 1, 1]), float) / s).tolist()
    g.doc.setdefault("extras", {})["orificio_a_tapar"] = OLD_HOLE.tolist()
    print(f"   hueso: punta del trocánter en la entrada, girado {np.degrees(2 * np.arccos(min(1, q[3]))):.1f}°, escala {s}")


def shift(values, amount):
    return values - PIN_EXTRA * amount[:, None] * CANAL_AXIS[None, :]


def paso32(g):
    clip = g.clip("Paso2_montaje_guia_mandril_insercion_canal")
    realign(g, clip, ["Threaded_Guide_Pin_3.2x400.001", "Mango_de_acoplamiento.001", "Llave_portabrocas.001",
                      "Eje_de_entrada.001", "Indicador_profundidad.001"])
    times, out = g.track(clip, "Threaded_Guide_Pin_3.2x400.001", "translation")
    t = g.array(times)[:, 0]
    pin = g.array(out).copy()
    final = pin[-1, 1]
    # Avance extra proporcional a lo que el pin ya entró en el hueso (0 afuera, 1 al final).
    progress = np.clip((ENTRY_Y - pin[:, 1]) / (ENTRY_Y - final), 0, 1)
    done = set()
    for name in ("Threaded_Guide_Pin_3.2x400.001", "Mango_de_acoplamiento.001", "Llave_portabrocas.001"):
        found = g.track(clip, name, "translation")
        if not found or found[1] in done:
            continue
        done.add(found[1])
        ti, oi = found
        own_t = g.array(ti)[:, 0]
        g.set_array(oi, shift(g.array(oi).copy(), np.interp(own_t, t, progress)))
    print(f"3.2: punta del pin al final y={pin[-1, 1]:.4f} -> {pin[-1, 1] - PIN_EXTRA * PIN_AXIS[1]:.4f}")


def paso33(g):
    clip = g.clip("Paso3_retiro_mandril_insercion_protector")
    realign(g, clip, ["Threaded_Guide_Pin_3.2x400.002", "Mango_de_acoplamiento.002", "Llave_portabrocas.002", "Protector_de_tejidos"])
    found = g.track(clip, "Protector_de_tejidos", "translation")
    g.set_array(found[1], (g.array(found[1]).astype(float) + PROTECTOR_LIFT * CANAL_AXIS).astype(np.float32))
    print("3.3: protector apoyado sobre el hueso (", PROTECTOR_LIFT * 1000, "mm más arriba)")
    done = set()
    for name in ("Threaded_Guide_Pin_3.2x400.002", "Mango_de_acoplamiento.002", "Llave_portabrocas.002"):
        found = g.track(clip, name, "translation")
        if found and found[1] not in done:
            done.add(found[1])
            values = g.array(found[1]).copy()
            g.set_array(found[1], shift(values, np.ones(len(values))))
        node = g.node(name)
        if "translation" in node:
            node["translation"] = shift(np.array([node["translation"]]), np.ones(1))[0].tolist()
    print("3.3: pin y mango desplazados", PIN_EXTRA, "m a lo largo del pin")


def paso34(g):
    clip = g.clip("Paso4_broca_canulada_perforador_hasta_tope")
    realign(g, clip, ["Threaded_Guide_Pin_3.2x400", "Protector_de_tejidos_camisa", "Broca_canulada_16.5",
                      "Perforador_quirurgico", "Llave_en_T_portabrocas", "Tunel_broca_16.5"])
    camisa = g.node("Protector_de_tejidos_camisa")
    camisa["translation"] = (np.array(camisa["translation"]) + PROTECTOR_LIFT * CANAL_AXIS).tolist()
    pin = g.node("Threaded_Guide_Pin_3.2x400")
    pin["translation"] = shift(np.array([pin["translation"]]), np.ones(1))[0].tolist()
    # Momento en que la punta de la broca llega a DRILL_STOP_Y: desde ahí broca y perforador quedan quietos.
    ti, oi = g.track(clip, "Broca_canulada_16.5", "translation")
    t = g.array(ti)[:, 0]
    drill = g.array(oi)
    below = np.nonzero(drill[:, 1] < DRILL_STOP_Y)[0]
    if not len(below):
        print(f"3.4: la broca nunca baja de y={DRILL_STOP_Y}; no hace falta detenerla")
        return
    k = below[0]
    f = (drill[k - 1, 1] - DRILL_STOP_Y) / (drill[k - 1, 1] - drill[k, 1])
    stop_time = t[k - 1] + f * (t[k] - t[k - 1])
    held_done = set()
    for name in ("Broca_canulada_16.5", "Perforador_quirurgico"):
        tj, oj = g.track(clip, name, "translation")
        if oj in held_done:
            continue
        held_done.add(oj)
        tt = g.array(tj)[:, 0]
        values = g.array(oj).copy()
        held = np.array([np.interp(stop_time, tt, values[:, c]) for c in range(3)])
        values[tt >= stop_time] = held
        g.set_array(oj, values)
    # Anillos del túnel que quedaban por debajo de la nueva profundidad: no aparecen.
    hidden = 0
    for ch in clip["channels"]:
        node = g.doc["nodes"][ch["target"]["node"]]
        name = node["name"]
        if not name.startswith("Tunel_broca_") or ch["target"]["path"] != "scale" or not name[12:].isdigit():
            continue
        # Medido en Three.js: el anillo 00 va de y=0.1829 hacia arriba y el 52 de y=0.1203; uno cada ~1,2 mm.
        ring_low = 0.1829 + (0.1203 - 0.1829) * int(name[12:]) / 52
        if ring_low < DRILL_STOP_Y:
            out = clip["samplers"][ch["sampler"]]["output"]
            g.set_array(out, np.full_like(g.array(out), TINY))
            hidden += 1
    print(f"3.4: broca detenida en y={DRILL_STOP_Y} a los {stop_time:.2f} s; anillos ocultos: {hidden}")


if __name__ == "__main__":
    action, src, dst = sys.argv[1:4]
    glb = Glb(src)
    if action == "paso31":
        anatomia(glb)
    else:
        {"paso32": paso32, "paso33": paso33, "paso34": paso34}[action](glb)
        anatomia(glb)
    glb.save(dst)
