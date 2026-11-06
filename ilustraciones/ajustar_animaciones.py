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
    node_index = {v: k for k, v in names.items()}
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


if __name__ == "__main__":
    action, src, dst = sys.argv[1:4]
    glb = Glb(src)
    if action == "paso31":
        guia31(glb)
        sin_lineas31(glb)
        anatomia(glb)
    else:
        {"paso32": paso32, "paso33": paso33, "paso34": paso34, "paso35": paso35}[action](glb)
        anatomia(glb)
    sin_sobrantes(glb)
    glb.save(dst)
