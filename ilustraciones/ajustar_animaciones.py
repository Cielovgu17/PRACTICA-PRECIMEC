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

    def append(self, values, kind):
        """Agrega un arreglo de flotantes al final del archivo y devuelve el número del nuevo accessor."""
        values = np.ascontiguousarray(values, dtype="<f4")
        raw = values.tobytes()
        pad = (4 - len(raw) % 4) % 4
        offset = self.doc["buffers"][0]["byteLength"]
        self.data = self.data + raw + bytes(pad)  # copia nueva: los arreglos ya leídos siguen válidos
        self.doc["buffers"][0]["byteLength"] = offset + len(raw) + pad
        struct.pack_into("<I", self.data, self.bin - 8, self.doc["buffers"][0]["byteLength"])
        self.doc["bufferViews"].append({"buffer": 0, "byteOffset": offset, "byteLength": len(raw)})
        acc = {"bufferView": len(self.doc["bufferViews"]) - 1, "componentType": 5126,
               "count": len(values), "type": kind}
        if kind == "SCALAR":
            acc["min"], acc["max"] = [float(values.min())], [float(values.max())]
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def append_raw(self, array, component, kind, target=None):
        raw = np.ascontiguousarray(array).tobytes()
        pad = (4 - len(raw) % 4) % 4
        offset = self.doc["buffers"][0]["byteLength"]
        self.data = self.data + raw + bytes(pad)
        self.doc["buffers"][0]["byteLength"] = offset + len(raw) + pad
        struct.pack_into("<I", self.data, self.bin - 8, self.doc["buffers"][0]["byteLength"])
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(raw)}
        if target:
            view["target"] = target
        self.doc["bufferViews"].append(view)
        acc = {"bufferView": len(self.doc["bufferViews"]) - 1, "componentType": component, "count": len(array), "type": kind}
        if kind == "VEC3" and component == 5126:
            acc["min"], acc["max"] = array.min(0).astype(float).tolist(), array.max(0).astype(float).tolist()
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

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
# Punto de entrada como en AO: de frente, en la punta del trocánter mayor; desde arriba, en la mitad
# anteroposterior de esa punta (ancho 47,7 mm; la punta queda a 0,62 desde adelante), en línea con el canal.
# El instrumental conserva su recorrido; el hueso se ubica con ese punto en la superficie de la entrada del
# instrumental (ENTRY, 10 mm más arriba a lo largo del eje) y se gira para que la recta que mejor pasa por los
# centros del canal (de 100 a 250 mm de profundidad, desde ese punto) quede justo sobre el pin guía.
# Medido: de 150 a 250 mm el pin queda a 0,7-2,8 mm del centro del canal; la broca, 1,9 mm dentro del hueso.
ENTRY_POINT = np.array([-0.0055, 0.2133, -0.0129])      # en las coordenadas propias del fémur
CANAL_LINE = np.array([-0.02946, 0.99718, -0.06906])    # recta por ENTRY_POINT ajustada a los centros del canal
OLD_HOLE = np.array([-0.0039, 0.2043, -0.0007])         # orificio que traía el modelo (se tapa en femur_limpio.py)
SURFACE_UP = 0.010
BONE_SCALE = float(__import__("os").environ.get("BONE_SCALE", 1.05))


def bone_transform():
    """p -> A + S·R·(p - entrada): traslación, giro (x, y, z, w) y escala del grupo Anatomia."""
    q = quat_between(CANAL_LINE, PIN_AXIS)
    R = quat_matrix(q)
    A = ENTRY + SURFACE_UP * PIN_AXIS
    t = A - BONE_SCALE * R @ ENTRY_POINT
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
        elif name.startswith(("Tunel_broca", "Canal_escariado_", "Abertura_punto_entrada", "Cortical_retirada_por_el_abridor")):
            # Lo hace el instrumental: sigue al instrumental, no al hueso. El túnel y el hueco de la abertura quedan
            # donde los dejó el instrumental (el hueco termina justo bajo la superficie, sin asomarse por fuera).
            delta = np.zeros(3) if name.startswith(("Tunel", "Canal_escariado_", "Abertura")) else SURFACE_UP * PIN_AXIS
            base = np.array(node.get("translation", [0, 0, 0]), float)
            node["translation"] = ((Ri @ (base + delta - t)) / s).tolist()
            node["rotation"] = quat_mul(np.array(inverse_q), np.array([node.get("rotation", [0, 0, 0, 1])], float))[0].tolist()
            node["scale"] = (np.array(node.get("scale", [1, 1, 1]), float) / s).tolist()
    g.doc.setdefault("extras", {})["orificio_a_tapar"] = OLD_HOLE.tolist()
    print(f"   hueso: punto de entrada AO en la entrada, girado {np.degrees(2 * np.arccos(min(1, q[3]))):.1f}°, escala {s}")


# ---------- Guía del paso 3.1 sobre la cima del trocánter (vista superior, como en AO) ----------
# Tres líneas en dirección medial-lateral: borde anterior, mitad (por la entrada) y borde posterior de la cima del
# trocánter; el travesaño de la pieza de bordes (de adelante hacia atrás) cruza justo en la entrada.
# Medido en la cima (10 mm por debajo de la punta): el borde anterior a 14,1 mm y el posterior a 15,3 mm de la
# entrada, así que la entrada queda en la mitad. Las líneas flotan 2 mm sobre la entrada y se mueven con el hueso.
SUPERIOR = np.array([0.0758, 0.992, 0.1006])
MEDIAL = np.array([0.9315, -0.1065, 0.3479])
GUIDE_HALF_WIDTH = 0.0147   # mitad de la distancia entre los bordes anterior y posterior
GUIDE_LIFT = 0.002
GUIDE_MEDIAL_SHIFT = 0.0    # el travesaño de la guía (centro de la pieza en la malla) queda sobre la entrada


def matrix_quat(M):
    w = np.sqrt(max(0.0, 1 + M[0, 0] + M[1, 1] + M[2, 2])) / 2
    x = np.copysign(np.sqrt(max(0.0, 1 + M[0, 0] - M[1, 1] - M[2, 2])) / 2, M[2, 1] - M[1, 2])
    y = np.copysign(np.sqrt(max(0.0, 1 - M[0, 0] + M[1, 1] - M[2, 2])) / 2, M[0, 2] - M[2, 0])
    z = np.copysign(np.sqrt(max(0.0, 1 - M[0, 0] - M[1, 1] + M[2, 2])) / 2, M[1, 0] - M[0, 1])
    return np.array([x, y, z, w])


def guia31(g):
    t, q, S = bone_transform()
    R = quat_matrix(q)
    sup = SUPERIOR / np.linalg.norm(SUPERIOR)
    ant = np.cross(MEDIAL, sup); ant /= np.linalg.norm(ant)
    med = np.cross(sup, ant)
    Rw = R @ np.column_stack([med, sup, ant])          # x de la malla -> medial, y -> arriba, z -> adelante
    qw = matrix_quat(Rw)
    guide = g.node("Guia_tercios_trocanter_mayor")
    pivot = -np.array(g.node("Bordes_AP_trocanter")["translation"])   # centro de la guía en la malla
    edges = g.doc["accessors"][g.doc["meshes"][g.node("Bordes_AP_trocanter")["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
    k = GUIDE_HALF_WIDTH / ((edges["max"][2] - edges["min"][2]) / 2)   # separa los bordes al ancho medido
    center = t + S * R @ (ENTRY_POINT + GUIDE_LIFT * sup)
    guide["translation"] = (center + S * GUIDE_MEDIAL_SHIFT * Rw[:, 0]).tolist()
    guide["rotation"] = qw.tolist()
    clip = g.doc["animations"][0]
    _, out = g.track(clip, "Guia_tercios_trocanter_mayor", "scale")
    g.set_array(out, (g.array(out).astype(float) * np.array([S, S, S * k])).astype(np.float32))
    # La línea del medio pasa por la entrada (antes iba en el tercio anterior).
    line = g.node("Linea_tercio_anterior_2_3_posterior")
    acc = g.doc["accessors"][g.doc["meshes"][line["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
    c = (np.array(acc["min"]) + np.array(acc["max"])) / 2
    line["translation"] = [line["translation"][0], line["translation"][1], float(-c[2])]
    line["name"] = "Linea_mitad_AP_por_la_entrada"
    # Anillo y flecha en la entrada, sobre la superficie del hueso.
    g.node("Marcador_punto_entrada")["translation"] = (ENTRY + SURFACE_UP * PIN_AXIS).tolist()
    print(f"   guía 3.1: bordes a ±{GUIDE_HALF_WIDTH*1000:.1f} mm de la entrada, línea del medio por la entrada")


def sin_lineas31(g):
    """Paso 3.1: solo quedan el anillo y la flecha del punto de entrada; las líneas guía no aparecen."""
    clip = g.doc["animations"][0]
    for name in ("Guia_tercios_trocanter_mayor", "Eje_trayectoria_abridor", "Indicador_profundidad"):
        _, out = g.track(clip, name, "scale")
        g.set_array(out, np.full_like(g.array(out), TINY))
    print("   3.1: líneas guía ocultas; quedan el anillo y la flecha")


def sin_sobrantes(g):
    """Quita los trocitos de cortical sobre la entrada (se veían como una sombra bajo el anillo) y el cono de
    hueso esponjoso de la abertura (quedaba por fuera del fémur). Los nodos quedan, sin malla."""
    removed = 0
    for node in g.doc["nodes"]:
        if node["name"].startswith("Cortical_entrada_") and "mesh" in node:
            del node["mesh"]
            removed += 1
    print(f"   sobrantes quitados: {removed}")


HOLE_ALPHA = 0.4


def perforaciones_translucidas(g):
    """El hueco de la abertura, el túnel de la broca y el canal escariado se ven, pero dejan ver lo de adentro
    (el pin, la broca, el escariador o el clavo)."""
    for m in g.doc["materials"]:
        if m["name"].startswith(("Hueso_esponjoso_abertura", "Hueso_escariado_marcado")):
            pbr = m.setdefault("pbrMetallicRoughness", {})
            pbr["baseColorFactor"] = list(pbr.get("baseColorFactor", [1, 1, 1, 1]))[:3] + [HOLE_ALPHA]
            m["alphaMode"] = "BLEND"
            m["doubleSided"] = True


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
    retirar_broca(g, clip, stop_time)


# Al final del 3.4 la broca canulada sale con el perforador por el mismo camino por donde entró (al doble de
# velocidad), mientras el protector de tejidos y el pin guía se quedan en su lugar.
RETRACT_PAUSE = 1.5       # s quieta en el tope antes de salir
RETRACT_SPEED = 2.0
RETRACT_TO_Y = 0.48       # sale hasta que la punta de la broca queda a esta altura (bien arriba del protector)
RETRACT_END_HOLD = 1.0
RETRACTING = ("Broca_canulada_16.5", "Perforador_quirurgico", "Portabrocas_giratorio")


def retirar_broca(g, clip, stop_time):
    ti, oi = g.track(clip, "Broca_canulada_16.5", "translation")
    t = g.array(ti)[:, 0].astype(float)
    y = g.array(oi)[:, 1].astype(float)
    above = np.nonzero((t < stop_time) & (y >= RETRACT_TO_Y))[0]
    t_out = t[above[-1]]
    start = stop_time + RETRACT_PAUSE
    end = start + (stop_time - t_out) / RETRACT_SPEED
    fps = 1 / np.median(np.diff(t))
    new_t = np.concatenate([t[t <= start], np.arange(start + 1 / fps, end + RETRACT_END_HOLD + 1e-9, 1 / fps)])
    source = np.where(new_t <= start, new_t, np.maximum(stop_time - (new_t - start) * RETRACT_SPEED, t_out))
    hold = np.minimum(new_t, t[-1])
    new_input = g.append(new_t[:, None], "SCALAR")
    for ch in clip["channels"]:
        sampler = clip["samplers"][ch["sampler"]]
        times = g.array(sampler["input"])[:, 0].astype(float)
        values = g.array(sampler["output"]).astype(float)
        name = g.doc["nodes"][ch["target"]["node"]]["name"]
        at = source if name in RETRACTING else hold
        if sampler.get("interpolation") == "STEP":
            out = values[np.clip(np.searchsorted(times, at, "right") - 1, 0, len(times) - 1)]
        else:
            out = np.stack([np.interp(at, times, values[:, c]) for c in range(values.shape[1])], axis=1)
            if ch["target"]["path"] == "rotation":
                out /= np.linalg.norm(out, axis=1, keepdims=True)
        sampler["output"] = g.append(out, {1: "SCALAR", 3: "VEC3", 4: "VEC4"}[out.shape[1]])
        sampler["input"] = new_input
    print(f"3.4: la broca sale de {start:.1f} a {end:.1f} s (hasta y={RETRACT_TO_Y}); dura {new_t[-1]:.1f} s")


# ---------- Paso 3.5: escariado flexible ----------
# La animación trae cuatro escariadores (Φ9,0; 9,5; 10,0; 10,5). Se dejan dos: Φ9,0 y Φ10,5, porque para el clavo
# corto de Φ9,4 × 240 mm el canal se escaria hasta ~1 mm más que el clavo. Se corta el tramo de los otros dos.
# El escariador llega hasta REAM_DEPTH (el clavo mide 240 mm; la punta del pin guía está a 250 mm).
# Al final se retiran el perforador con el escariador, el protector de tejidos y el pin guía: queda el canal listo.
CUT_FROM, CUT_TO = 44.3, 97.5          # s: del cambio Φ9,0 -> Φ9,5 al cambio Φ10,0 -> Φ10,5
REAM_DEPTH = 0.245
REAMER_HEAD = 0.28                      # la cabeza del escariador está a 280 mm de su origen, a lo largo de su eje z
KEEP, DROP = ("D9.0", "D10.5"), ("D9.5", "D10.0")


def paso35(g):
    clip = g.doc["animations"][0]
    for name in ("Femur_derecho", "Canal_medular_esquematico"):   # el hueso lo ubica anatomia(), como en los demás
        for k in ("translation", "rotation", "scale"):
            g.node(name).pop(k, None)
    names = {i: n["name"] for i, n in enumerate(g.doc["nodes"])}
    t = g.array(clip["samplers"][0]["input"])[:, 0].astype(float)
    assert all(sm["input"] == clip["samplers"][0]["input"] for sm in clip["samplers"])
    ia, ib = np.nonzero(t <= CUT_FROM)[0], np.nonzero(t > CUT_TO)[0]
    idx = np.concatenate([ia, ib])
    nt = np.concatenate([t[ia], t[ib] - (CUT_TO - CUT_FROM)])
    tracks = {}
    for ch in clip["channels"]:
        sm = clip["samplers"][ch["sampler"]]
        tracks[(names[ch["target"]["node"]], ch["target"]["path"])] = g.array(sm["output"]).astype(float)
    new = {key: v[idx].copy() for key, v in tracks.items()}
    # Los anillos del canal escariado con Φ9,0 se quedan hasta que pasa el Φ10,5 (antes los reemplazaba el Φ9,5).
    for (name, path), v in new.items():
        if name.startswith("Canal_escariado_D9.0_") and path == "scale":
            twin = (name.replace("D9.0", "D10.0"), path)
            if twin in tracks:
                v[len(ia):] = tracks[twin][ib]
        if any(f"_{d}" in name for d in DROP) and path == "scale":
            v[:] = TINY
    # Profundidad máxima del escariador.
    vis = lambda name: new[(name, "scale")][:, 0] > 0.01
    lift = np.zeros(len(nt))
    for d in KEEP:
        name = f"Escariador_flexible_{d}"
        pos, rot = new[(name, "translation")], new[(name, "rotation")]
        axis = np.array([quat_matrix(q) @ [0, 0, 1] for q in rot])
        tip = pos + REAMER_HEAD * axis
        A = ENTRY + SURFACE_UP * PIN_AXIS
        excess = np.clip((A - tip) @ PIN_AXIS - REAM_DEPTH, 0, None)
        pos += excess[:, None] * PIN_AXIS
        lift = np.where(vis(name), np.maximum(lift, excess), lift)
    new[("Perforador_quirurgico", "translation")] += lift[:, None] * PIN_AXIS
    # Anillos del canal escariado más hondos que el escariador: no aparecen.
    hidden = 0
    for i, name in names.items():
        if name.startswith("Canal_escariado_") and "mesh" in g.doc["nodes"][i]:
            acc = g.doc["accessors"][g.doc["meshes"][g.doc["nodes"][i]["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
            base = np.array(g.doc["nodes"][i].get("translation", [0, 0, 0]))
            corners = base + np.array([[x, y, z] for x in (acc["min"][0], acc["max"][0]) for y in (acc["min"][1], acc["max"][1]) for z in (acc["min"][2], acc["max"][2])])
            if ((ENTRY + SURFACE_UP * PIN_AXIS - corners) @ PIN_AXIS).max() > REAM_DEPTH + 0.008 and (name, "scale") in new:
                new[(name, "scale")][:] = TINY
                hidden += 1
    # Canal escariado marcado: un tubo continuo color hueso esponjoso (como el hueco del abridor) que se va
    # formando detrás de la cabeza del escariador, primero de Φ9 y luego de Φ10,5. Reemplaza los anillos sueltos.
    for name in names.values():
        if name.startswith("Canal_escariado_") and (name, "scale") in new:
            new[(name, "scale")][:] = TINY
    tube_nodes = canal_escariado(g, new, nt, vis)
    # Final: sale todo. 0,5 s: se va el perforador con el escariador; 3 s: sube y se va el protector; 3 s: sube y se
    # va el pin guía; 2 s con el canal listo.
    fps = 1 / np.median(np.diff(nt))
    end = nt[-1]
    extra = np.arange(end + 1 / fps, end + 8.5 + 1e-9, 1 / fps)
    nt2 = np.concatenate([nt, extra])
    for key, v in new.items():
        new[key] = np.concatenate([v, np.repeat(v[-1:], len(extra), axis=0)])
    gone = nt2 > end + 0.5
    for name in ("Perforador_quirurgico", "Escariador_flexible_D9.0", "Escariador_flexible_D10.5", "Llave_en_T_portabrocas"):
        if (name, "scale") not in new:
            new[(name, "scale")] = np.repeat([np.array(g.node(name).get("scale", [1, 1, 1]), float)], len(nt2), axis=0)
        new[(name, "scale")][gone] = TINY
    def leave(node_name, t0, t1, distance):
        node = g.node(node_name)
        base = np.array(node.get("translation", [0, 0, 0]), float)
        f = np.clip((nt2 - t0) / (t1 - t0), 0, 1)
        f = f * f * (3 - 2 * f)
        new[(node_name, "translation")] = base + (f * distance)[:, None] * PIN_AXIS
        sc = np.array(node.get("scale", [1, 1, 1]), float)
        new[(node_name, "scale")] = np.where((nt2 > t1)[:, None], TINY, sc[None, :])
    leave("Protector_tejidos_camisa", end + 0.8, end + 3.8, 0.20)
    leave("Threaded_Guide_Pin_3.2x400", end + 4.0, end + 7.0, 0.42)
    # Escribe todo de nuevo (más corto y con el final agregado).
    new_input = g.append(nt2[:, None], "SCALAR")
    node_index = {n["name"]: k for k, n in enumerate(g.doc["nodes"])}
    done = set()
    for ch in clip["channels"]:
        key = (names[ch["target"]["node"]], ch["target"]["path"])
        sm = clip["samplers"][ch["sampler"]]
        v = new[key]
        if key[1] == "rotation":
            v = v / np.linalg.norm(v, axis=1, keepdims=True)
        sm["input"] = new_input
        sm["output"] = g.append(v, {3: "VEC3", 4: "VEC4"}[v.shape[1]])
        done.add(key)
    for key, v in new.items():
        if key in done:
            continue
        clip["samplers"].append({"input": new_input, "output": g.append(v, "VEC3"),
                                 "interpolation": "STEP" if key[1] == "scale" else "LINEAR"})
        clip["channels"].append({"sampler": len(clip["samplers"]) - 1, "target": {"node": node_index[key[0]], "path": key[1]}})
    print(f"3.5: quedan Φ9,0 y Φ10,5; escariador hasta {REAM_DEPTH*1000:.0f} mm (subido hasta {lift.max()*1000:.0f} mm); "
          f"anillos ocultos {hidden}; dura {nt2[-1]:.1f} s (antes {t[-1]:.1f} s)")


REAMED_FROM = 0.050      # el tubo empieza dentro del túnel de la broca de Φ16,5 (que llega a ~66 mm)
REAMED_SEGMENT = 0.005


def canal_escariado(g, new, nt, vis):
    A = ENTRY + SURFACE_UP * PIN_AXIS
    base = next(m for m in g.doc["materials"] if m["name"] == "Hueso_esponjoso_abertura")
    g.doc["materials"].append({"name": "Hueso_escariado_marcado", "doubleSided": True,
                               "pbrMetallicRoughness": dict(base["pbrMetallicRoughness"]),   # sólido, como el hueco
                               "emissiveFactor": [0.35, 0.17, 0.11]})                         # algo de brillo propio
    material = len(g.doc["materials"]) - 1
    instrumental = next(i for i, n in enumerate(g.doc["nodes"]) if n["name"] == "Instrumental")
    rot = quat_between(np.array([0.0, 1.0, 0.0]), PIN_AXIS).tolist()
    count = 0
    for d, radius in (("D9.0", 0.0045), ("D10.5", 0.00525)):
        # malla: un tramo de tubo abierto de y=0 a y=-REAMED_SEGMENT
        ang = np.linspace(0, 2 * np.pi, 33)
        ring = np.stack([np.cos(ang), np.zeros_like(ang), np.sin(ang)], 1)
        pos = np.concatenate([ring * radius, ring * radius + [0, -REAMED_SEGMENT, 0]]).astype("<f4")
        nor = np.concatenate([ring, ring]).astype("<f4")
        idx = []
        for i in range(32):
            a, b, c, e = i, i + 1, 33 + i, 33 + i + 1
            idx += [a, c, b, b, c, e]
        idx = np.array(idx, "<u2")
        prim = {"attributes": {"POSITION": g.append_raw(pos, 5126, "VEC3", 34962), "NORMAL": g.append_raw(nor, 5126, "VEC3", 34962)},
                "indices": g.append_raw(idx, 5123, "SCALAR", 34963), "material": material}
        g.doc["meshes"].append({"name": f"Hueso_escariado_{d}", "primitives": [prim]})
        mesh = len(g.doc["meshes"]) - 1
        # profundidad de la cabeza del escariador en el tiempo (lo más hondo alcanzado hasta ese momento)
        name = f"Escariador_flexible_{d}"
        axis = np.array([quat_matrix(q) @ [0, 0, 1] for q in new[(name, "rotation")]])
        tip = new[(name, "translation")] + REAMER_HEAD * axis
        depth = np.where(vis(name), (A - tip) @ PIN_AXIS, 0)
        reached = np.maximum.accumulate(depth)
        for k in np.arange(REAMED_FROM, REAM_DEPTH - 1e-9, REAMED_SEGMENT):
            # Sin la palabra "canal": el visor oculta por defecto las piezas del canal esquemático, y esta debe verse.
            node_name = f"Hueso_escariado_Φ{d[1:].replace('.0', '').replace('.', ',')}_{int(round(k * 1000)):03d}"
            g.doc["nodes"].append({"name": node_name, "mesh": mesh, "translation": (A - k * PIN_AXIS).tolist(),
                                   "rotation": rot, "scale": [TINY] * 3})
            g.doc["nodes"][instrumental].setdefault("children", []).append(len(g.doc["nodes"]) - 1)
            shown = reached >= k + REAMED_SEGMENT * 0.5
            new[(node_name, "scale")] = np.where(shown[:, None], 1.0, TINY) * np.ones((len(nt), 3))
            count += 1
    print(f"   canal escariado marcado: {count} tramos de {REAMED_SEGMENT*1000:.0f} mm, de {REAMED_FROM*1000:.0f} a {REAM_DEPTH*1000:.0f} mm")
    return count


# ---------- Paso 4: montaje e inserción del clavo ----------
# Un solo archivo para dos pasos del instructivo (el visor muestra un tramo de tiempo y oculta piezas):
#   4.1 (10 a 32 s): se fija el clavo en el mango con el tornillo de conexión y su llave; sin el hueso.
#   4.2 (32 s al final): el clavo entra al canal con movimientos oscilantes del mango y se detiene con
#        NAIL_STOP de recorrido pendiente (30 mm del clavo por fuera), para terminar con el martillo en 4.3-4.4.
INSERT_FROM, INSERT_TO = 34.0, 50.0     # s: tramo de la inserción en la animación original
NAIL_SHORT = 0.040                      # el clavo para 40 mm antes del final original (punta a 210 mm)
OSC_PUSHES = 8
OSC_ANGLE = np.radians(15)


def hueso_escariado_fijo(g, radius=0.00525):
    """Canal escariado del paso 3.5, ya completo (Φ10,5 de 50 a 245 mm), quieto."""
    A = ENTRY + SURFACE_UP * PIN_AXIS
    base = next(m for m in g.doc["materials"] if m["name"] == "Hueso_esponjoso_abertura")
    g.doc["materials"].append({"name": "Hueso_escariado_marcado", "doubleSided": True,
                               "pbrMetallicRoughness": dict(base["pbrMetallicRoughness"]),
                               "emissiveFactor": [0.35, 0.17, 0.11]})
    length = REAM_DEPTH - REAMED_FROM
    ang = np.linspace(0, 2 * np.pi, 33)
    ring = np.stack([np.cos(ang), np.zeros_like(ang), np.sin(ang)], 1)
    pos = np.concatenate([ring * radius, ring * radius + [0, -length, 0]]).astype("<f4")
    nor = np.concatenate([ring, ring]).astype("<f4")
    idx = np.array([v for i in range(32) for v in (i, 33 + i, i + 1, i + 1, 33 + i, 34 + i)], "<u2")
    prim = {"attributes": {"POSITION": g.append_raw(pos, 5126, "VEC3", 34962), "NORMAL": g.append_raw(nor, 5126, "VEC3", 34962)},
            "indices": g.append_raw(idx, 5123, "SCALAR", 34963), "material": len(g.doc["materials"]) - 1}
    g.doc["meshes"].append({"name": "Hueso_escariado_D10.5", "primitives": [prim]})
    instrumental = next(i for i, n in enumerate(g.doc["nodes"]) if n["name"] == "Instrumental")
    g.doc["nodes"].append({"name": "Hueso_escariado_Φ10,5", "mesh": len(g.doc["meshes"]) - 1,
                           "translation": (A - REAMED_FROM * PIN_AXIS).tolist(),
                           "rotation": quat_between(np.array([0.0, 1.0, 0.0]), PIN_AXIS).tolist()})
    g.doc["nodes"][instrumental].setdefault("children", []).append(len(g.doc["nodes"]) - 1)


def paso4(g):
    clip = g.doc["animations"][0]
    for name in ("Femur_derecho", "Canal_medular_esquematico"):
        for k in ("translation", "rotation", "scale"):
            g.node(name).pop(k, None)
    for node in g.doc["nodes"]:                      # los anillos sueltos del escariado se reemplazan por el tubo
        if node["name"].startswith("Canal_escariado_"):
            node.pop("mesh", None)
    hueso_escariado_fijo(g)
    clavo_orificio_bajo(g)
    name = "Clavo_cefalomedular_conjunto"
    ti, oi = g.track(clip, name, "translation")
    t = g.array(ti)[:, 0].astype(float)
    pos = g.array(oi).astype(float)
    start = np.array([np.interp(INSERT_FROM, t, pos[:, c]) for c in range(3)])
    end = np.array([np.interp(INSERT_TO, t, pos[:, c]) for c in range(3)])
    travel = (start - end) @ PIN_AXIS - NAIL_SHORT
    tau = np.clip((t - INSERT_FROM) / (INSERT_TO - INSERT_FROM), 0, 1)
    n = OSC_PUSHES
    progress = tau - np.sin(2 * np.pi * n * tau) / (2 * np.pi * n)     # avanza a empujes, siempre hacia adentro
    new_pos = np.where((t < INSERT_FROM)[:, None], pos, start - (progress * travel)[:, None] * PIN_AXIS)
    g.set_array(oi, new_pos.astype(np.float32))
    # Oscilación del mango alrededor del eje del clavo mientras entra.
    q0 = np.array(g.node(name).get("rotation", [0, 0, 0, 1]), float)
    theta = OSC_ANGLE * np.sin(2 * np.pi * n * tau) * np.sin(np.pi * tau)
    rots = np.array([quat_mul(np.array([*(PIN_AXIS * np.sin(a / 2)), np.cos(a / 2)]), q0[None])[0] for a in theta])
    sampler_in = clip["samplers"][0]["input"]
    clip["samplers"].append({"input": sampler_in, "output": g.append(rots, "VEC4"), "interpolation": "LINEAR"})
    clip["channels"].append({"sampler": len(clip["samplers"]) - 1,
                             "target": {"node": next(i for i, x in enumerate(g.doc["nodes"]) if x["name"] == name), "path": "rotation"}})
    tip_depth = ((ENTRY + SURFACE_UP * PIN_AXIS) - new_pos[-1]) @ PIN_AXIS
    print(f"4: clavo hasta {tip_depth*1000:.0f} mm (queda {240 - tip_depth*1000:.0f} mm del clavo por fuera); "
          f"{n} empujes oscilando ±{np.degrees(OSC_ANGLE):.0f}°")



def paso43(g):
    """Paso 4.3 (vástago de inserción, llave combinada y extractor/impactador): el clavo ya viene como queda en el
    4.2 (30 mm por fuera); solo se ubica el hueso como en los demás pasos, con el canal escariado marcado."""
    for name in ("Femur_derecho", "Canal_medular_esquematico"):
        for k in ("translation", "rotation", "scale"):
            g.node(name).pop(k, None)
    for node in g.doc["nodes"]:
        if node["name"].startswith("Canal_escariado_"):
            node.pop("mesh", None)
    if not any(n["name"].startswith("Hueso_escariado") for n in g.doc["nodes"]):
        hueso_escariado_fijo(g)
    clavo_orificio_bajo(g)
    print("4.3: hueso ubicado y canal escariado marcado")


# ---------- Bloqueo proximal (pasos 6.1, 6.2 y 6.4): brazo de soporte, guías y pin guía hacia la cabeza ----------
# Como venían de Blender, el pin guía roscado cruzaba el orificio del clavo (NAIL_HOLE) pero pasaba 16 mm por encima
# del centro de la cabeza del fémur. Girar las guías chocaba el brazo con el mango, así que se conserva el ángulo del
# instrumental (el brazo dice CCD 130°) y se baja el orificio del clavo HOLE_DROP a lo largo del clavo:
#   * clavo (clavo_orificio_bajo): la parte proximal gruesa se alarga y el orificio queda 25 mm más abajo; la punta
#     de arriba (donde va el mango) y la parte distal no cambian. Se aplica en todos los pasos con el clavo.
#   * brazo de soporte (brazo_alargado): se alarga 25 mm en su tramo recto; la parte que se une al mango y la perilla
#     no se mueven, y el bloque de las guías baja sin girar.
#   * manguitos, casquillo, tuerca, trocar, perforador, pin e indicador bajan lo mismo (sin girar).
# Así el pin va por el centro del cuello y de la cabeza (como en la técnica de Kang-Li) y nada se atraviesa.
# Medido en las coordenadas del instrumental (el hueso ya ubicado con anatomia()).
NAIL_HOLE = np.array([-0.0040, 0.1658, -0.0026])         # donde el pin cruza el eje del clavo
HEAD_CENTER = np.array([0.0454, 0.1953, 0.0373])         # centro de la cabeza (esfera ajustada, radio 26,9 mm)
HEAD_RADIUS = 0.0269
PIN12_DIR = np.array([0.5783, 0.6653, 0.4721])           # dirección original del pin (hacia la cabeza)
PIN12_TIP = np.array([0.0371, 0.2130, 0.0309])           # punta original del pin al final del paso 12
GUIDE_ROT = np.eye(3)                                     # las guías ya no giran
NAIL_AXIS = np.array([-0.1053, 0.9942, -0.0222]) / np.linalg.norm([-0.1053, 0.9942, -0.0222])   # hacia arriba
HOLE_DROP = 0.0250                                        # medido: así la recta del pin pasa a 0,9 mm del centro
GUIDE_SHIFT = -HOLE_DROP * NAIL_AXIS
TIP_FROM_EDGE = 0.0125                                    # la punta queda a 10-15 mm del borde de la cabeza
# En coordenadas del clavo (Clavo_cefalomedular_conjunto; la malla del clavo no tiene transformación propia):
NAIL_AXIS_C = np.array([-0.0669, -0.0001, 0.9978])
HOLE_C = np.array([-0.0022, 0.0, 0.2017])
NAIL_RIGID = 0.012          # ±12 mm alrededor del orificio bajan enteros
NAIL_TOP_FIXED = 0.034      # desde 34 mm sobre el orificio (la punta de arriba está a 38 mm) no se mueve
NAIL_LOW_FIXED = -0.100     # desde 100 mm bajo el orificio no se mueve
ARM_BLOCK = np.array([-0.1183, 0.0, 0.1044])              # bloque del brazo por donde pasan las guías
ARM_UP = np.array([-0.025, 0.0, 1.0]) / np.linalg.norm([-0.025, 0.0, 1.0])   # del bloque hacia la unión con el mango
ARM_STRETCH = (0.040, 0.072)  # tramo recto que se alarga (el bloque llega a 40 mm; la unión con el mango empieza en 74)
GUIDE_PIECES = ("Conjunto_de_guias_Blade_Nail_Combination_Sleeve", "Blade_Nail_Combination_Sleeve_Tubo_malla",
                "Drill_Sleeve_3_2mm", "Blade_Nail_Combination_Sleeve_Roscado_tuerca", "Indicador_distancia_10_15mm",
                "Perforador_quirurgico", "Trocar_3_2mm")


def node_matrix(node):
    M = np.eye(4)
    M[:3, :3] = quat_matrix(np.array(node.get("rotation", [0, 0, 0, 1]), float)) @ np.diag(node.get("scale", [1, 1, 1]))
    M[:3, 3] = node.get("translation", [0, 0, 0])
    return M


def guias_bloqueo(g):
    nodes = g.doc["nodes"]
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    clip = g.doc["animations"][0]
    d = PIN12_DIR / np.linalg.norm(PIN12_DIR)
    new_dir = GUIDE_ROT @ d
    # Avance extra del pin para que su punta quede a TIP_FROM_EDGE del borde de la cabeza.
    tip = NAIL_HOLE + GUIDE_ROT @ (PIN12_TIP - NAIL_HOLE) + GUIDE_SHIFT
    extra = (HEAD_RADIUS - TIP_FROM_EDGE) - (tip - HEAD_CENTER) @ new_dir
    off = tip - HEAD_CENTER
    print(f"   pin a {np.linalg.norm(off - (off @ new_dir) * new_dir) * 1000:.1f} mm del centro de la cabeza")
    done = set()
    for k, node in enumerate(nodes):
        if node["name"] not in GUIDE_PIECES:
            continue
        i, up = k, []
        while i in parent:
            i = parent[i]
            up.append(nodes[i]["name"])
        if any(name in GUIDE_PIECES for name in up):   # ya gira con la pieza que lo contiene
            continue
        i, Mp = k, np.eye(4)
        while i in parent:                       # padres fijos (Instrumental, Clavo_cefalomedular_conjunto)
            i = parent[i]
            Mp = node_matrix(nodes[i]) @ Mp
            assert not any(g.doc["nodes"][ch["target"]["node"]] is nodes[i] for ch in clip["channels"]), nodes[i]["name"]
        Rp, tp = Mp[:3, :3], Mp[:3, 3]
        Rl = Rp.T @ GUIDE_ROT @ Rp               # el mismo giro, en las coordenadas del padre
        cl = Rp.T @ (GUIDE_ROT @ (tp - NAIL_HOLE) + NAIL_HOLE + GUIDE_SHIFT - tp)
        ql = matrix_quat(Rl)
        move = lambda T: T @ Rl.T + cl
        node["translation"] = move(np.array([node.get("translation", [0, 0, 0])], float))[0].tolist()
        node["rotation"] = quat_mul(ql, np.array([node.get("rotation", [0, 0, 0, 1])], float))[0].tolist()
        tr = g.track(clip, node["name"], "translation")
        if tr and tr[1] not in done:
            done.add(tr[1])
            values = move(g.array(tr[1]).astype(float))
            if node["name"] in ("Perforador_quirurgico", "Indicador_distancia_10_15mm"):
                # el pin entra los milímetros que faltan durante sus últimos 60 mm de avance
                s = values @ (Rp.T @ new_dir)
                progress = np.clip(1 - (s[-1] - s) / 0.060, 0, 1) if node["name"] == "Perforador_quirurgico" else 1
                values = values + (extra * np.atleast_1d(progress))[:, None] * (Rp.T @ new_dir)[None, :]
            g.set_array(tr[1], values.astype(np.float32))
        elif node["name"] == "Indicador_distancia_10_15mm":
            node["translation"] = (np.array(node["translation"]) + extra * (Rp.T @ new_dir)).tolist()
        ro = g.track(clip, node["name"], "rotation")
        if ro and ro[1] not in done:
            done.add(ro[1])
            g.set_array(ro[1], quat_mul(ql, g.array(ro[1]).astype(float)).astype(np.float32))
        print(f"   bajado: {node['name']}")
    brazo_alargado(g)
    print(f"   bloqueo proximal: guías {HOLE_DROP*1000:.0f} mm más abajo a lo largo del clavo; el pin entra {extra*1000:.0f} mm más")


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def shift_mesh(g, node_name, local_points, local_shift_fn):
    """Mueve los puntos de la malla de un nodo. local_points(v) pasa la malla a otras coordenadas y vuelve."""
    node = g.node(node_name)
    done = set()
    for prim in g.doc["meshes"][node["mesh"]]["primitives"]:
        index = prim["attributes"]["POSITION"]
        if index in done:
            continue
        done.add(index)
        v = g.array(index).astype(float)
        g.set_array(index, local_shift_fn(v).astype(np.float32))


def clavo_orificio_bajo(g):
    """Baja el orificio de la hoja HOLE_DROP: la parte gruesa proximal del clavo se alarga hacia abajo."""
    node = next((n for n in g.doc["nodes"] if n["name"] == "Clavo_malla" and "mesh" in n), None)
    if node is None:
        return
    assert np.allclose(node_matrix(node), np.eye(4), atol=1e-6), "la malla del clavo tiene transformación propia"
    def move(v):
        h = (v - HOLE_C) @ NAIL_AXIS_C
        above = smooth((NAIL_TOP_FIXED - h) / (NAIL_TOP_FIXED - NAIL_RIGID))
        below = smooth((h - NAIL_LOW_FIXED) / (-NAIL_RIGID - NAIL_LOW_FIXED))
        w = np.where(h >= 0, above, below)
        return v - (HOLE_DROP * w)[:, None] * NAIL_AXIS_C[None, :]
    shift_mesh(g, "Clavo_malla", None, move)
    print(f"   clavo: orificio de la hoja {HOLE_DROP*1000:.0f} mm más abajo (parte proximal más larga)")


def brazo_alargado(g):
    """Alarga el tramo recto del brazo de soporte para que el bloque de las guías baje HOLE_DROP sin girar."""
    name = "Varilla_Refuerzo_brazo_de_soporte"
    node = next((n for n in g.doc["nodes"] if n["name"] == name), None)
    if node is None:
        return
    clip = g.doc["animations"][0]
    T = np.array(node.get("translation", [0, 0, 0]), float)
    tr = g.track(clip, name, "translation")
    if tr:
        T = g.array(tr[1])[-1].astype(float)        # unido al mango: su posición al final del montaje
    R = quat_matrix(np.array(node.get("rotation", [0, 0, 0, 1]), float))
    def move(v):
        p = v @ R.T + T                              # en coordenadas del clavo
        s = (p - ARM_BLOCK) @ ARM_UP
        w = 1 - smooth((s - ARM_STRETCH[0]) / (ARM_STRETCH[1] - ARM_STRETCH[0]))
        p = p - (HOLE_DROP * w)[:, None] * NAIL_AXIS_C[None, :]
        return (p - T) @ R
    shift_mesh(g, name, None, move)
    print(f"   brazo de soporte: tramo recto {HOLE_DROP*1000:.0f} mm más largo; la unión con el mango no se mueve")


# ---------- Orden del 6.2 y el 6.3: primero se aprieta la tuerca; el trocar sale al comenzar el 6.3 ----------
# paso11 (6.2): entra el conjunto de guías (3-14 s), sale el trocar (15-21 s) y se aprieta la tuerca (22,5-32,5 s).
# El trocar se queda puesto y se quita ese tramo. paso12 (6.3): antes de montar el pin, sale el trocar.
TROCAR_OUT = (14.5, 22.0)          # s del paso11 que se quitan
TROCAR_LOCAL = np.array([0.0, 0.0, -0.0009])   # trocar dentro del conjunto de guías
TROCAR_TRAVEL = 0.79               # sale 790 mm a lo largo del manguito (como en el paso11)
TROCAR_LEAD = 6.5                  # s que se agregan al comienzo del paso12 para sacarlo


def resample(g, clip, new_t, source_t):
    """Vuelve a escribir todas las pistas del clip en new_t, tomando cada valor del tiempo source_t original."""
    new_input = g.append(new_t[:, None], "SCALAR")
    for ch in clip["channels"]:
        sm = clip["samplers"][ch["sampler"]]
        times = g.array(sm["input"])[:, 0].astype(float)
        values = g.array(sm["output"]).astype(float)
        if sm.get("interpolation") == "STEP":
            out = values[np.clip(np.searchsorted(times, source_t, "right") - 1, 0, len(times) - 1)]
        else:
            out = np.stack([np.interp(source_t, times, values[:, c]) for c in range(values.shape[1])], axis=1)
            if ch["target"]["path"] == "rotation":
                out /= np.linalg.norm(out, axis=1, keepdims=True)
        sm["output"] = g.append(out, {1: "SCALAR", 3: "VEC3", 4: "VEC4"}[out.shape[1]])
        sm["input"] = new_input


def guias_sin_retirar_trocar(g):
    clip = g.doc["animations"][0]
    for path in ("translation", "scale"):
        _, out = g.track(clip, "Trocar_3_2mm", path)
        values = g.array(out)
        g.set_array(out, np.repeat(values[:1], len(values), axis=0))
    t = g.array(clip["samplers"][0]["input"])[:, 0].astype(float)
    fps = 1 / np.median(np.diff(t))
    a, b = TROCAR_OUT
    new_t = np.arange(0, t[-1] - (b - a) + 1e-9, 1 / fps)
    resample(g, clip, new_t, np.where(new_t <= a, new_t, new_t + (b - a)))
    print(f"6.2: el trocar se queda; se aprieta la tuerca sin pausa; dura {new_t[-1]:.1f} s")


# Al comenzar el 6.2 se arma el conjunto de guías en línea: el manguito protector (por fuera), el casquillo para
# broca (en el medio) y el trocar (por dentro). Medidas a lo largo del eje (z = 0 en la punta, +z hacia afuera):
# manguito 0-246 mm, casquillo 22-252 mm, trocar -1-260 mm. Separados 15 mm entre sí y alineados.
ASSEMBLY_LEAD = 9.0        # s que se agregan al comienzo
SLEEVE_OFFSET = 0.240      # el casquillo empieza 240 mm hacia afuera (su punta queda 16 mm detrás del manguito)
TROCAR_OFFSET = 0.505      # el trocar empieza 505 mm hacia afuera (15 mm detrás del casquillo)


def armar_conjunto(g):
    clip = g.doc["animations"][0]
    t = g.array(clip["samplers"][0]["input"])[:, 0].astype(float)
    fps = 1 / np.median(np.diff(t))
    appear = 3.0                                  # el conjunto aparecía a los 3 s, ya armado
    new_t = np.arange(0, t[-1] - appear + ASSEMBLY_LEAD + 1e-9, 1 / fps)
    resample(g, clip, new_t, np.maximum(new_t - ASSEMBLY_LEAD + appear, appear))
    _, out = g.track(clip, "Conjunto_de_guias_Blade_Nail_Combination_Sleeve", "scale")
    g.set_array(out, np.where((new_t >= 0.3)[:, None], 1.0, TINY).astype(np.float32) * np.ones((len(new_t), 3), np.float32))
    def slide(t0, t1, offset):
        f = np.clip((new_t - t0) / (t1 - t0), 0, 1)
        return (1 - f * f * (3 - 2 * f)) * offset
    node_index = {n["name"]: k for k, n in enumerate(g.doc["nodes"])}
    new_input = clip["samplers"][0]["input"]
    for name, (t0, t1, offset) in (("Drill_Sleeve_3_2mm", (1.5, 4.5, SLEEVE_OFFSET)),
                                    ("Trocar_3_2mm", (5.0, 8.0, TROCAR_OFFSET))):
        base = np.array(g.node(name).get("translation", [0, 0, 0]), float)
        values = base + slide(t0, t1, offset)[:, None] * np.array([0, 0, 1.0])
        found = g.track(clip, name, "translation")
        if found:
            clip["samplers"][next(ch["sampler"] for ch in clip["channels"] if ch["target"]["node"] == node_index[name]
                                  and ch["target"]["path"] == "translation")]["output"] = g.append(values, "VEC3")
        else:
            clip["samplers"].append({"input": new_input, "output": g.append(values, "VEC3"), "interpolation": "LINEAR"})
            clip["channels"].append({"sampler": len(clip["samplers"]) - 1,
                                     "target": {"node": node_index[name], "path": "translation"}})
    print(f"6.2: se arma el conjunto en línea (casquillo 1,5-4,5 s; trocar 5-8 s); dura {new_t[-1]:.1f} s")


def read_any(g, index):
    acc = g.doc["accessors"][index]
    view = g.doc["bufferViews"][acc["bufferView"]]
    n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    dtype = {5121: "<u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}[acc["componentType"]]
    assert not view.get("byteStride")
    start = g.bin + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    return np.frombuffer(g.data, dtype=dtype, count=acc["count"] * n, offset=start).reshape(acc["count"], n), acc


# El medidor de profundidad marca de 70 a 120 mm (70 a 95 mm de su cara delantera, 120 a 48 mm). Con el pin de
# 400 mm su extremo quedaba a 35 mm, fuera de la escala, aunque el pin va 110-114 mm dentro del hueso (de la
# cortical lateral a la punta). Se alarga el tramo liso del pin PIN_EXTRA_LENGTH para que el medidor marque ~110.
PIN_EXTRA_LENGTH = 0.0      # ya no hace falta: se acortaron el manguito y las piezas que se apoyan en él
# Manguito protector más corto: el tramo liso entre la rosca (100-200 mm) y la cabeza (230-246 mm) pasa de 29 a 7 mm.
# El casquillo para broca y el trocar se apoyan en el extremo del manguito: se acortan lo mismo en su caña, así sus
# puntas quedan donde estaban. Con el pin real de 400 mm el medidor marca ~110.
SLEEVE_SHORTER = 0.022


def guias_cortas(g):
    S = SLEEVE_SHORTER
    def tubo(v):
        z = v[:, 2]
        a, b = 0.2005, 0.2295
        nz = np.where(z < a, z, np.where(z < b, a + (z - a) * (b - a - S) / (b - a), z - S))
        return np.c_[v[:, :2], nz]
    def cana(v):                                       # casquillo y trocar: se acorta la caña entre 20 y 200 mm
        z = v[:, 2]
        a, b = 0.020, 0.200
        nz = np.where(z < a, z, np.where(z < b, a + (z - a) * (b - a - S) / (b - a), z - S))
        return np.c_[v[:, :2], nz]
    names = {n["name"] for n in g.doc["nodes"]}
    if "Blade_Nail_Combination_Sleeve_Tubo_malla" in names:
        shift_mesh(g, "Blade_Nail_Combination_Sleeve_Tubo_malla", None, tubo)
    for name in ("Drill_Sleeve_3_2mm", "Trocar_3_2mm"):
        if name in names:
            shift_mesh(g, name, None, cana)
    # La tuerca empieza S más adentro en la rosca (antes ocupaba el tramo liso) y termina igual, apretada al brazo.
    clip = g.doc["animations"][0]
    tr = g.track(clip, "Blade_Nail_Combination_Sleeve_Roscado_tuerca", "translation")
    if tr:
        v = g.array(tr[1]).astype(float)
        end = v[-1, 2]
        if end < -1e-4:
            v[:, 2] = -S + (v[:, 2] / end) * (end + S)
            g.set_array(tr[1], v.astype(np.float32))
    print(f"   manguito protector, casquillo y trocar {S*1000:.0f} mm más cortos")
PIN_SMOOTH_FROM = 0.050     # el tramo liso empieza a 50 mm de la punta (la rosca y la punta no cambian)


def pin_mas_largo(g):
    node = next(n for n in g.doc["nodes"] if n["name"] == "Pin_guia_roscado_malla")
    def move(v):
        z = v[:, 2]
        stretch = np.clip((z - PIN_SMOOTH_FROM) / (0.400 - PIN_SMOOTH_FROM), 0, 1) * PIN_EXTRA_LENGTH
        return v + stretch[:, None] * np.array([0, 0, 1.0])
    shift_mesh(g, "Pin_guia_roscado_malla", None, move)
    print(f"   pin guía roscado: {400 + PIN_EXTRA_LENGTH*1000:.0f} mm (tramo liso más largo)")


def trocar_sale_al_inicio(g, source_path):
    """Copia el trocar del paso11 al paso12 y lo saca durante los primeros TROCAR_LEAD segundos."""
    src = Glb(source_path)
    snode = src.node("Trocar_3_2mm")
    mesh = src.doc["meshes"][snode["mesh"]]
    prims = []
    for p in mesh["primitives"]:
        new = {"attributes": {}}
        for key, index in p["attributes"].items():
            data, acc = read_any(src, index)
            new["attributes"][key] = g.append_raw(data.copy(), acc["componentType"], acc["type"], 34962)
        data, acc = read_any(src, p["indices"])
        new["indices"] = g.append_raw(data[:, 0].copy(), acc["componentType"], "SCALAR", 34963)
        if "material" in p:
            g.doc["materials"].append(src.doc["materials"][p["material"]])
            new["material"] = len(g.doc["materials"]) - 1
        prims.append(new)
    g.doc["meshes"].append({"name": mesh["name"], "primitives": prims})
    # Mismo lugar que en el 6.2: dentro del manguito, que en el paso12 es hijo directo del clavo.
    sleeve = g.node("Blade_Nail_Combination_Sleeve_Tubo_malla")
    q = np.array(sleeve["rotation"], float)
    R = quat_matrix(q)
    base = np.array(sleeve["translation"], float) + R @ TROCAR_LOCAL
    conjunto = next(i for i, n in enumerate(g.doc["nodes"]) if n["name"] == "Clavo_cefalomedular_conjunto")
    g.doc["nodes"].append({"name": "Trocar_3_2mm", "mesh": len(g.doc["meshes"]) - 1,
                           "translation": base.tolist(), "rotation": q.tolist()})
    node = len(g.doc["nodes"]) - 1
    g.doc["nodes"][conjunto]["children"].append(node)
    # Todo lo demás empieza TROCAR_LEAD segundos después.
    clip = g.doc["animations"][0]
    t = g.array(clip["samplers"][0]["input"])[:, 0].astype(float)
    fps = 1 / np.median(np.diff(t))
    new_t = np.arange(0, t[-1] + TROCAR_LEAD + 1e-9, 1 / fps)
    resample(g, clip, new_t, np.maximum(new_t - TROCAR_LEAD, 0))
    f = np.clip((new_t - 0.5) / (TROCAR_LEAD - 1.0), 0, 1)
    f = f * f * (3 - 2 * f)
    pos = base + (f * TROCAR_TRAVEL)[:, None] * (R @ [0, 0, 1])[None, :]
    scale = np.where((new_t >= TROCAR_LEAD - 0.5)[:, None], TINY, 1.0) * np.ones((len(new_t), 3))
    new_input = clip["samplers"][0]["input"]
    for path, values, interp in (("translation", pos, "LINEAR"), ("scale", scale, "STEP")):
        clip["samplers"].append({"input": new_input, "output": g.append(values, "VEC3"), "interpolation": interp})
        clip["channels"].append({"sampler": len(clip["samplers"]) - 1, "target": {"node": node, "path": path}})
    print(f"6.3: sale el trocar (0,5-{TROCAR_LEAD - 0.5:.1f} s) y luego se monta el pin; dura {new_t[-1]:.1f} s")


# ---------- Paso 6.4: retiro del casquillo y medidor de profundidad sobre el pin guía ----------
# Empieza como termina el 6.3. El perforador suelta el pin y sale por detrás (el pin queda quieto); sale el casquillo
# para broca por el eje del manguito y se deja a un lado; entra el medidor de profundidad (modelo
# Depth_Gauge_Medidor_Profundidad.stl, "Depth Gauge for D3.2 guide pin", en mm) deslizándose sobre el pin hasta que su
# cara delantera (Φ21,5) se apoya en el extremo del manguito protector. La lectura es donde queda el extremo del pin
# dentro del medidor; no se escribe ninguna cifra.
SLEEVE_END = 0.2458 - SLEEVE_SHORTER   # extremo exterior del manguito protector (z del manguito, desde su punta)
GAUGE_BORE = (0.007, 0.104)  # tramo del canal del medidor donde puede quedar el extremo del pin


def stl_mesh(g, path, name, color):
    raw = open(path, "rb").read()
    n = struct.unpack_from("<I", raw, 80)[0]
    tri = np.frombuffer(raw, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("x", "<u2")]), count=n, offset=84)
    v = tri["v"].reshape(-1, 3).astype(np.float64) / 1000          # mm -> m
    keys, inverse = np.unique(np.round(v / 2e-5).astype(np.int64), axis=0, return_inverse=True)   # une puntos iguales
    pos = np.zeros((len(keys), 3)); np.add.at(pos, inverse.ravel(), v); pos /= np.bincount(inverse.ravel())[:, None]
    faces = inverse.reshape(-1, 3)
    nor = np.zeros_like(pos)
    fn = np.cross(pos[faces[:, 1]] - pos[faces[:, 0]], pos[faces[:, 2]] - pos[faces[:, 0]])
    for k in range(3):
        np.add.at(nor, faces[:, k], fn)
    nor /= np.maximum(np.linalg.norm(nor, axis=1, keepdims=True), 1e-12)
    g.doc["materials"].append({"name": name, "pbrMetallicRoughness": {"baseColorFactor": color, "metallicFactor": 0.6,
                                                                      "roughnessFactor": 0.35}})
    prim = {"attributes": {"POSITION": g.append_raw(pos.astype("<f4"), 5126, "VEC3", 34962),
                           "NORMAL": g.append_raw(nor.astype("<f4"), 5126, "VEC3", 34962)},
            "indices": g.append_raw(faces.ravel().astype("<u4"), 5125, "SCALAR", 34963),
            "material": len(g.doc["materials"]) - 1}
    g.doc["meshes"].append({"name": name, "primitives": [prim]})
    print(f"   {name}: {len(pos)} puntos, {len(faces)} triángulos")
    return len(g.doc["meshes"]) - 1


def world_matrix(g, index, local=None):
    parent = {c: i for i, n in enumerate(g.doc["nodes"]) for c in n.get("children", [])}
    M = local if local is not None else node_matrix(g.doc["nodes"][index])
    while index in parent:
        index = parent[index]
        M = node_matrix(g.doc["nodes"][index]) @ M
    return M


def medidor(g, stl_path):
    nodes = g.doc["nodes"]
    idx = {n["name"]: k for k, n in enumerate(nodes)}
    clip = g.doc["animations"][0]
    t_end = max(g.array(s["input"])[-1, 0] for s in clip["samplers"])
    # 1) Todo queda como al final del 6.3 (cada pieza con su valor final, fijo).
    final = {}
    key_tracks = {}                                     # la llave en T del portabrocas, como se usó en el 6.3
    for ch in clip["channels"]:
        if nodes[ch["target"]["node"]]["name"] == "Llave_en_T_portabrocas":
            sm = clip["samplers"][ch["sampler"]]
            key_tracks[ch["target"]["path"]] = (g.array(sm["input"])[:, 0].astype(float), g.array(sm["output"]).astype(float),
                                               sm.get("interpolation", "LINEAR"))
    for ch in clip["channels"]:
        sm = clip["samplers"][ch["sampler"]]
        final[(ch["target"]["node"], ch["target"]["path"])] = g.array(sm["output"])[-1].astype(float)
    for (node, path), value in final.items():
        nodes[node][path] = value.tolist()
    # 2) El pin guía queda fijo en el hueso: deja de ser hijo del perforador.
    pin = idx["Pin_guia_roscado_3.2x400"]
    Mpin = world_matrix(g, pin)
    for n in nodes:
        if pin in n.get("children", []):
            n["children"].remove(pin)
    nodes[idx["Instrumental"]].setdefault("children", []).append(pin)
    R = Mpin[:3, :3]
    nodes[pin].update(translation=Mpin[:3, 3].tolist(), rotation=matrix_quat(R).tolist(), scale=[1, 1, 1])
    # 3) Marco del manguito protector (z hacia afuera, 0 en su punta).
    tubo = idx["Blade_Nail_Combination_Sleeve_Tubo_malla"]
    conj = idx["Clavo_cefalomedular_conjunto"]
    Mc = world_matrix(g, conj)
    Mt = node_matrix(nodes[tubo])                       # el manguito en coordenadas del clavo
    Rt, Tt = Mt[:3, :3], Mt[:3, 3]
    out_world = Mc[:3, :3] @ Rt[:, 2]                   # hacia afuera, en el mundo
    pin_mesh = g.doc["meshes"][next(n for n in nodes if n["name"] == "Pin_guia_roscado_malla")["mesh"]]
    length = max(g.doc["accessors"][p["attributes"]["POSITION"]]["max"][2] for p in pin_mesh["primitives"])
    tail = Mpin[:3, 3] + length * (Mpin[:3, :3] @ [0, 0, 1])   # extremo trasero del pin (la malla empieza en z 0)
    tail_z = (np.linalg.inv(Mc @ Mt) @ np.r_[tail, 1])[2]
    tip_z = (np.linalg.inv(Mc @ Mt) @ np.r_[Mpin[:3, 3], 1])[2]
    reading = tail_z - SLEEVE_END
    scale = 70 + (0.0954 - reading) * 50 / 0.0473      # marcas del medidor: 70 a 95,4 mm, 120 a 48,1 mm
    print(f"6.4: el pin sobresale {reading*1000:.1f} mm del manguito (canal del medidor {GAUGE_BORE[0]*1000:.0f}-"
          f"{GAUGE_BORE[1]*1000:.0f} mm); el medidor marca ~{scale:.0f}; pin de {length*1000:.0f} mm")
    assert GAUGE_BORE[0] < reading < GAUGE_BORE[1], "el extremo del pin no cae dentro del canal del medidor"
    # 4) Nueva línea de tiempo.
    # La llave en T afloja el portabrocas: es el mismo movimiento con que lo apretó en el 6.3, al revés (entra, gira
    # en sentido contrario y sale).
    scale_t, scale_v, _ = key_tracks["scale"]
    shown = scale_t[scale_v[:, 0] > 0.5]
    k0, k1 = shown[0] - 0.05, shown[-1] + 0.05
    KEY_FROM = 1.0
    loosen_end = KEY_FROM + (k1 - k0)
    T = loosen_end + 25.0
    fps = 30
    new_t = np.arange(0, T + 1e-9, 1 / fps)
    ease = lambda a, b: (lambda f: f * f * (3 - 2 * f))(np.clip((new_t - a) / (b - a), 0, 1))
    tracks = []                                          # (nodo, ruta, valores, interpolación)
    key = idx["Llave_en_T_portabrocas"]
    source = k1 - (new_t - KEY_FROM)
    inside = (new_t >= KEY_FROM) & (new_t <= loosen_end)
    for path, (kt, kv, interp) in key_tracks.items():
        if interp == "STEP":
            vals = kv[np.clip(np.searchsorted(kt, source, "right") - 1, 0, len(kt) - 1)]
        else:
            vals = np.stack([np.interp(source, kt, kv[:, c]) for c in range(kv.shape[1])], axis=1)
        if path == "scale":
            vals = np.where(inside[:, None], vals, TINY)
        tracks.append((key, path, vals, interp))
    # Perforador: con el portabrocas flojo, sale por detrás del pin y luego se aparta.
    a = loosen_end + 0.5
    perf = idx["Perforador_quirurgico"]
    p0 = np.array(nodes[perf]["translation"], float)
    Mp_parent = world_matrix(g, idx["Instrumental"])
    out_p = Mp_parent[:3, :3].T @ out_world
    side_p = Mp_parent[:3, :3].T @ (Mc[:3, :3] @ Rt[:, 0])
    tracks.append((perf, "translation", p0 + (ease(a, a + 2.5) * 0.30)[:, None] * out_p
                   + (ease(a + 2.5, a + 3.7) * 0.25)[:, None] * side_p, "LINEAR"))
    # Casquillo para broca: sale por el eje del manguito hasta pasar el extremo del pin y se deja a un lado.
    a += 4.5
    cas = idx["Drill_Sleeve_3_2mm"]
    c0 = np.array(nodes[cas]["translation"], float)
    pull = tail_z - 0.0223 + 0.040                      # su punta (z 22 mm) queda 40 mm más allá del pin
    tracks.append((cas, "translation", c0 + (ease(a, a + 5.0) * pull)[:, None] * Rt[:, 2]
                   + (ease(a + 5.0, a + 6.5) * 0.12)[:, None] * Rt[:, 0], "LINEAR"))
    a += 7.0
    # Medidor de profundidad: aparece alineado detrás del pin y se desliza hasta apoyarse en el manguito.
    mesh = stl_mesh(g, stl_path, "Medidor_de_profundidad_D3.2", [0.80, 0.81, 0.83, 1.0])
    # Se gira sobre su eje para que la ventana con la escala (su lado +x) mire hacia adelante (vista anterior).
    anterior = np.array([-0.35, -0.154, 0.924])
    best = max(np.radians(np.arange(0, 360, 2)), key=lambda a: (Mc[:3, :3] @ Rt @ [np.cos(a), np.sin(a), 0]) @ anterior)
    spin = np.array([0, 0, np.sin(best / 2), np.cos(best / 2)])
    gauge_rot = quat_mul(np.array(nodes[tubo]["rotation"], float), spin[None])[0].tolist()
    nodes.append({"name": "Medidor_de_profundidad", "mesh": mesh, "rotation": gauge_rot,
                  "translation": (Tt + Rt @ [0, 0, SLEEVE_END]).tolist(), "scale": [TINY] * 3})
    gauge = len(nodes) - 1
    nodes[conj]["children"].append(gauge)
    start = reading + 0.035                              # su cara delantera empieza 35 mm más allá del pin
    z = SLEEVE_END + start * (1 - ease(a + 2.0, a + 7.5))
    tracks.append((gauge, "translation", Tt[None, :] + z[:, None] * Rt[:, 2][None, :], "LINEAR"))
    tracks.append((gauge, "scale", np.where((new_t >= a)[:, None], 1.0, TINY) * np.ones((len(new_t), 3)), "STEP"))
    # Se reemplaza la animación: solo estas pistas (la cámara animada y lo demás quedan quietos).
    new_input = g.append(new_t[:, None], "SCALAR")
    clip["channels"], clip["samplers"] = [], []
    for node, path, values, interp in tracks:
        if path == "rotation":
            values = values / np.linalg.norm(values, axis=1, keepdims=True)
        clip["samplers"].append({"input": new_input, "output": g.append(values, "VEC4" if path == "rotation" else "VEC3"),
                                 "interpolation": interp})
        clip["channels"].append({"sampler": len(clip["samplers"]) - 1, "target": {"node": node, "path": path}})
    clip["name"] = "Paso6_4_retiro_casquillo_y_medidor_de_profundidad"
    print(f"6.4: llave en T afloja {KEY_FROM:.1f}-{loosen_end:.1f} s; medidor aparece a los {a:.1f} s y llega a los "
          f"{a + 7.5:.1f} s; dura {T:.1f} s")


# ---------- Paso 6.5: retiro del medidor y broca canulada para la primera cortical proximal ----------
# Broca_Canulada_Cortical_Proximal.stl (mm): punta cortante Φ9,2 (0-22 mm), cuerpo Φ10, tope Φ18,8 (219-232 mm),
# vástago al perforador (236-350 mm) y canal de 3,2 mm para el pin. Con el tope apoyado en el manguito protector
# (224 mm) la punta quedaba 5 mm dentro del manguito, así que se alarga 17,2 mm el cuerpo liso (aprobado): con el
# tope en el manguito, la cabeza cortante entra en la cortical lateral justo en todo su ancho (la superficie, inclinada,
# está entre 1,5 y 12,2 mm más allá de la punta del manguito dentro del ancho de la broca) y no sigue.
BIT_STRETCH = 0.0210        # 17,2 mm para llegar a la cortical + 3,8 mm para que entre un poco más (hasta z -16 mm,
                            # junto al costado del clavo; dentro del ancho de la broca no hay clavo hasta -37,8 mm)
BIT_STOP = 0.2188 + BIT_STRETCH     # de la punta a la cara del tope
BIT_LENGTH = 0.350 + BIT_STRETCH
BONE_FIRST = -0.0015                # primer contacto con el hueso (z del manguito)


def freeze_final(g):
    """Deja cada pieza con su valor final, fijo, y devuelve las pistas originales por (nombre, ruta)."""
    nodes = g.doc["nodes"]
    clip = g.doc["animations"][0]
    tracks = {}
    for ch in clip["channels"]:
        sm = clip["samplers"][ch["sampler"]]
        node = nodes[ch["target"]["node"]]
        tracks[(node["name"], ch["target"]["path"])] = (g.array(sm["input"])[:, 0].astype(float),
                                                        g.array(sm["output"]).astype(float), sm.get("interpolation", "LINEAR"))
    for (name, path), (_, values, _) in tracks.items():
        g.node(name)[path] = values[-1].tolist()
    return tracks


def sample(track, at):
    times, values, interp = track
    if interp == "STEP":
        return values[np.clip(np.searchsorted(times, at, "right") - 1, 0, len(times) - 1)]
    out = np.stack([np.interp(at, times, values[:, c]) for c in range(values.shape[1])], axis=1)
    return out / np.linalg.norm(out, axis=1, keepdims=True) if values.shape[1] == 4 else out


def broca_cortical(g, stl_path):
    nodes = g.doc["nodes"]
    idx = {n["name"]: k for k, n in enumerate(nodes)}
    old = freeze_final(g)
    clip = g.doc["animations"][0]
    # Marcos: manguito (z hacia afuera, 0 en su punta) y perforador.
    tubo, conj = idx["Blade_Nail_Combination_Sleeve_Tubo_malla"], idx["Clavo_cefalomedular_conjunto"]
    Mc = world_matrix(g, conj)
    Mt = node_matrix(nodes[tubo])
    Rt, Tt = Mt[:3, :3], Mt[:3, 3]
    to_sleeve = np.linalg.inv(Mc @ Mt)
    out_world = Mc[:3, :3] @ Rt[:, 2]
    side_world = Mc[:3, :3] @ Rt[:, 0]
    pin = idx["Pin_guia_roscado_3.2x400"]
    Mpin = world_matrix(g, pin)
    tail_z = (to_sleeve @ np.r_[Mpin[:3, 3] + 0.400 * (Mpin[:3, :3] @ [0, 0, 1]), 1])[2]
    # Perforador: en el 6.4 salió de p0 (donde sostenía el pin) a p0 + 0,30 hacia afuera + 0,25 a un lado.
    perf, chuck = idx["Perforador_quirurgico"], idx["Portabrocas_giratorio"]
    p0 = old[("Perforador_quirurgico", "translation")][1][0]
    nodes[perf]["translation"] = p0.tolist()
    Wchuck0 = world_matrix(g, chuck)                      # el portabrocas con el perforador en p0
    pin_in_chuck = np.linalg.inv(Wchuck0) @ Mpin           # donde estaba el pin dentro del portabrocas
    T = 36.0
    fps = 30
    t = np.arange(0, T + 1e-9, 1 / fps)
    ease = lambda a, b: smooth((t - a) / (b - a))
    tracks = []
    # 1) El medidor sale por el eje hasta pasar el extremo del pin y se aparta (1,5-6,5 s).
    gauge = idx["Medidor_de_profundidad"]
    g0 = np.array(nodes[gauge]["translation"], float)
    gpull = (tail_z - SLEEVE_END) + 0.025
    tracks.append((gauge, "translation", g0 + (ease(1.5, 5.0) * gpull)[:, None] * Rt[:, 2]
                   + (ease(5.0, 6.5) * 0.06)[:, None] * Rt[:, 0], "LINEAR"))
    # Una vez fuera, el medidor y el casquillo para broca (que quedó a un lado en el 6.4) ya no se ven.
    gone = np.where((t >= 6.5)[:, None], TINY, 1.0) * np.ones((len(t), 3))
    tracks.append((gauge, "scale", gone, "STEP"))
    tracks.append((idx["Drill_Sleeve_3_2mm"], "scale", gone, "STEP"))
    # 2) La broca entra en el portabrocas del perforador (que está a un lado) y la llave en T la aprieta.
    mesh = stl_mesh(g, stl_path, "Broca_canulada_cortical_proximal", [0.78, 0.79, 0.81, 1.0])
    def alargar(v):
        z = v[:, 2]
        a, b = 0.044, 0.215
        return np.c_[v[:, :2], np.where(z < a, z, np.where(z < b, a + (z - a) * (b - a + BIT_STRETCH) / (b - a), z + BIT_STRETCH))]
    pos_acc = g.doc["meshes"][mesh]["primitives"][0]["attributes"]["POSITION"]
    g.set_array(pos_acc, alargar(g.array(pos_acc).astype(float)).astype(np.float32))
    Rpin = pin_in_chuck[:3, :3]
    tail_in_chuck = pin_in_chuck[:3, 3] + 0.400 * Rpin[:, 2]
    bit_base = tail_in_chuck - BIT_LENGTH * Rpin[:, 2]
    nodes.append({"name": "Broca_canulada_cortical_proximal", "mesh": mesh, "translation": bit_base.tolist(),
                  "rotation": matrix_quat(Rpin).tolist(), "scale": [TINY] * 3})
    bit = len(nodes) - 1
    nodes[chuck]["children"].append(bit)
    tracks.append((bit, "translation", bit_base - ((1 - ease(7.5, 9.5)) * 0.07)[:, None] * Rpin[:, 2], "LINEAR"))
    tracks.append((bit, "scale", np.where((t >= 7.0)[:, None], 1.0, TINY) * np.ones((len(t), 3)), "STEP"))
    key_t, key_v, _ = old[("Llave_en_T_portabrocas", "scale")]
    shown = key_t[key_v[:, 0] > 0.5]
    k0, k1 = shown[0] - 0.05, shown[-1] + 0.05
    KEY_AT = 10.0
    src = k0 + (k1 - (t - KEY_AT)) - k0                    # el 6.4 aflojaba: al revés, aprieta
    inside = (t >= KEY_AT) & (t <= KEY_AT + (k1 - k0))
    key = idx["Llave_en_T_portabrocas"]
    for path in ("translation", "rotation", "scale"):
        vals = sample(old[("Llave_en_T_portabrocas", path)], src)
        if path == "scale":
            vals = np.where(inside[:, None], vals, TINY)
        tracks.append((key, path, vals, "STEP" if path == "scale" else "LINEAR"))
    a = KEY_AT + (k1 - k0) + 0.5
    # 3) El conjunto vuelve detrás del pin, se alinea y se desliza sobre él hasta tocar el hueso; luego perfora
    #    girando hasta que el tope se apoya en el manguito.
    Mi = world_matrix(g, idx["Instrumental"])
    pin_out = Mpin[:3, :3] @ [0, 0, 1]                              # se avanza por el eje del pin, exacto
    out_p, side_p = Mi[:3, :3].T @ pin_out, Mi[:3, :3].T @ side_world
    k_end = (SLEEVE_END - BIT_STOP) + BIT_LENGTH - tail_z           # tope en el extremo del manguito
    k_touch = BONE_FIRST + BIT_LENGTH - tail_z                       # la punta toca el hueso
    k_clear = 0.020 + BIT_LENGTH                                     # punta 20 mm más allá del extremo del pin
    k_t = np.full(len(t), 0.30)
    k_t = np.where(t >= a, 0.30 + (k_clear - 0.30) * ease(a, a + 2.0), k_t)
    side_t = 0.25 * (1 - ease(a + 2.0, a + 4.0))
    b = a + 4.5
    k_t = np.where(t >= b, k_clear + (k_touch - k_clear) * ease(b, b + 5.0), k_t)
    c = b + 5.5
    k_t = np.where(t >= c, k_touch + (k_end - k_touch) * smooth((t - c) / 4.5), k_t)
    tracks.append((perf, "translation", p0 + k_t[:, None] * out_p + side_t[:, None] * side_p, "LINEAR"))
    # Giro de la broca (con el portabrocas) mientras perfora; se detiene al llegar al tope.
    # La broca gira sobre su propio eje (el del pin), así no cabecea.
    turns = np.clip((t - (c - 0.5)) / (5.5), 0, 1) * 2 * np.pi * 9
    qb = matrix_quat(Rpin)
    tracks.append((bit, "rotation", np.array([quat_mul(qb, np.array([[0, 0, np.sin(x / 2), np.cos(x / 2)]]))[0]
                                              for x in turns]), "LINEAR"))
    # Perforación de la cortical: se va marcando detrás de la punta (mismo color translúcido que las demás).
    depth_total = BONE_FIRST - (SLEEVE_END - BIT_STOP)
    tip_z = tail_z - BIT_LENGTH + k_t
    cut = np.clip((BONE_FIRST - tip_z) / depth_total, 0, 1)
    base = next(m for m in g.doc["materials"] if m["name"].startswith("Hueso_esponjoso_abertura"))
    g.doc["materials"].append({"name": "Hueso_esponjoso_abertura_cortical", "doubleSided": True, "alphaMode": "BLEND",
                               "pbrMetallicRoughness": dict(base["pbrMetallicRoughness"]), "emissiveFactor": [0.35, 0.17, 0.11]})
    ang = np.linspace(0, 2 * np.pi, 41)
    ring = np.stack([np.cos(ang), np.sin(ang), np.zeros_like(ang)], 1) * 0.0047
    posc = np.concatenate([ring, ring + [0, 0, -depth_total]]).astype("<f4")
    nor = np.concatenate([ring, ring]).astype("<f4") / 0.0047
    ids = np.array([v for i in range(40) for v in (i, i + 1, 41 + i, i + 1, 42 + i, 41 + i)], "<u2")
    prim = {"attributes": {"POSITION": g.append_raw(posc, 5126, "VEC3", 34962), "NORMAL": g.append_raw(nor, 5126, "VEC3", 34962)},
            "indices": g.append_raw(ids, 5123, "SCALAR", 34963), "material": len(g.doc["materials"]) - 1}
    g.doc["meshes"].append({"name": "Perforacion_cortical_proximal", "primitives": [prim]})
    nodes.append({"name": "Perforacion_cortical_proximal", "mesh": len(g.doc["meshes"]) - 1,
                  "translation": (Tt + Rt @ [0, 0, BONE_FIRST]).tolist(), "rotation": nodes[tubo]["rotation"], "scale": [TINY] * 3})
    hole = len(nodes) - 1
    nodes[conj]["children"].append(hole)
    tracks.append((hole, "scale", np.where((cut > 0.02)[:, None], np.c_[np.ones(len(t)), np.ones(len(t)), np.maximum(cut, TINY)], TINY), "LINEAR"))
    new_input = g.append(t[:, None], "SCALAR")
    clip["channels"], clip["samplers"] = [], []
    for node, path, values, interp in tracks:
        clip["samplers"].append({"input": new_input, "output": g.append(values, "VEC4" if path == "rotation" else "VEC3"),
                                 "interpolation": interp})
        clip["channels"].append({"sampler": len(clip["samplers"]) - 1, "target": {"node": node, "path": path}})
    clip["name"] = "Paso6_5_retiro_medidor_y_broca_cortical_proximal"
    print(f"6.5: medidor fuera 1,5-6,5 s; broca montada y apretada {KEY_AT - 3:.1f}-{a:.1f} s; sobre el pin {b:.1f}-{c:.1f} s; "
          f"perfora {depth_total*1000:.1f} mm hasta el tope ({c:.1f}-{c + 4.5:.1f} s); dura {T:.0f} s")


if __name__ == "__main__":
    action, src, dst = sys.argv[1:4]
    if action == "broca_cortical":           # paso 6.5, a partir del 6.4 ya ajustado (tmp-a13)
        glb = Glb(src)
        broca_cortical(glb, sys.argv[4])
        glb.save(dst)
        sys.exit()
    if action == "medidor":                  # paso 6.4, a partir del 6.3 ya ajustado (tmp-a12)
        glb = Glb(src)
        medidor(glb, sys.argv[4])
        glb.save(dst)
        sys.exit()
    if action == "bloqueo":                  # pasos 6.1, 6.2 y 6.3: hueso como en 4.3 y guías hacia la cabeza
        glb = Glb(src)
        if "paso11" in src:
            guias_sin_retirar_trocar(glb)
            armar_conjunto(glb)
            guias_cortas(glb)
        if "paso12" in src:
            trocar_sale_al_inicio(glb, sys.argv[4])
            pin_mas_largo(glb)
            guias_cortas(glb)
        guias_bloqueo(glb)
        paso43(glb)
        anatomia(glb)
        sin_sobrantes(glb)
        perforaciones_translucidas(glb)
        glb.save(dst)
        sys.exit()
    glb = Glb(src)
    if action == "paso31":
        guia31(glb)
        sin_lineas31(glb)
        anatomia(glb)
    else:
        {"paso32": paso32, "paso33": paso33, "paso34": paso34, "paso35": paso35, "paso4": paso4, "paso43": paso43}[action](glb)
        anatomia(glb)
    sin_sobrantes(glb)
    perforaciones_translucidas(glb)
    glb.save(dst)
