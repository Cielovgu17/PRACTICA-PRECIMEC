// Motor 3D del visor (Three.js). Abre STL y GLB/GLTF, con o sin animaciones.
// Un GLB exportado desde Blender puede traer varias escenas, cada una con su animación (p. ej. el paso
// anterior y el actual). Aquí se muestra una sola escena a la vez, la que indique cada animación.
import * as THREE from '/vendor/three/three.module.js';
import { OrbitControls } from '/vendor/three/OrbitControls.js';
import { GLTFLoader } from '/vendor/three/GLTFLoader.js';
import { STLLoader } from '/vendor/three/STLLoader.js';

const MATERIAL = { color: 0xc9d3dd, metalness: 0.3, roughness: 0.45 };

// "Hoja_helicoidal_1" se muestra como "Hoja helicoidal" y "Femur_derecho001" como "Femur derecho".
// Los nombres que ya se habían cambiado a mano siguen la misma regla (ver piece_names).
export function pieceName(mesh) {
  const raw = mesh.name || mesh.parent?.name || '';
  const clean = raw
    // Blender agrega .001, .002… a las copias; los números de referencia (92100708) no se tocan.
    .replace(/(?<=.)\.?0\d{2}$/, '')
    .replace(/_\d+$/, '')
    .replace(/[_-]+/g, ' ')
    .trim();
  return clean || 'Pieza';
}

// Mientras no se indique otra cosa, el canal medular esquemático queda oculto: lo importante es el hueso.
export function defaultHidden(pieces) {
  return pieces.filter((name) => /canal/i.test(name));
}

export class Engine3D {
  constructor(container) {
    this.container = container;
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.playing = false;
    this.speed = 1;
    this.clock = new THREE.Clock();
    this.allMeshes = [];
    this.meshes = [];
    this.roots = [];
    this.clips = [];
    this.mixer = null;
    this.clip = null;
    this.time = 0;
    this.start = 0;
    this.end = 0;
    this.onEnd = null;
    // Cámara automática: durante la animación se acerca a lo que se está moviendo. Se apaga cuando la persona
    // mueve la cámara con el ratón, la rueda o los botones de acercar, y se vuelve a encender con su botón.
    this.autoCamera = true;
    this.onAutoChange = null;
    this.focus = null;

    try {
      this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      throw new Error('webgl');
    }
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.append(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x274466, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(1, 2, 1.5);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.8);
    fill.position.set(-1.5, -0.5, -1);
    this.scene.add(fill);

    this.camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.watchControls();

    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(container);
    this.resize();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  resize() {
    const { clientWidth: width, clientHeight: height } = this.container;
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  frame() {
    const delta = this.clock.getDelta();
    if (this.mixer && this.playing) {
      this.time = Math.min(this.time + delta * this.speed, this.end);
      this.applyTime();
      // Se reproduce una vez y se detiene al final: así no vuelve a empezar como si se repitiera el paso.
      if (this.time >= this.end) {
        this.playing = false;
        this.onEnd?.();
      }
    }
    if (this.autoCamera && this.focus && (this.playing || this.time > this.start + 0.05)) this.followFocus(delta);
    this.controls.update();
    this.fitClipping();
    this.renderer.render(this.scene, this.camera);
  }

  // Si la persona toma la cámara (arrastrar o rueda), la cámara automática se apaga.
  watchControls() {
    this.controls.addEventListener('start', () => this.setAutoCamera(false));
  }

  setAutoCamera(on) {
    if (this.autoCamera === on) return;
    this.autoCamera = on;
    this.onAutoChange?.(on);
  }

  // Recorre la animación una vez y anota, cada 0,2 s, la caja de las piezas que se están moviendo (cambian de
  // lugar, giran o aparecen). En cada instante el foco es lo que se mueve desde poco antes hasta 1,2 s después,
  // para llegar a tiempo; si en un tramo nada se mueve, se queda en el último foco.
  computeFocus() {
    this.focus = null;
    if (!this.mixer || !this.clip || this.end - this.start < 0.5) return;
    const keep = this.time;
    const step = 0.2;
    const times = [];
    for (let t = this.start; t < this.end; t += step) times.push(t);
    times.push(this.end);
    const meshes = this.meshes.filter((mesh) => mesh.visible);
    // Zona del hueso: si lo que se mueve llega al fémur, el foco es esa zona (la punta que perfora, la pieza que
    // entra) y no todo el instrumento que la sostiene.
    this.model.updateMatrixWorld(true);
    const bone = new THREE.Box3();
    meshes.filter((mesh) => /femur/i.test(`${mesh.name} ${mesh.parent?.name || ''}`) && !/canal/i.test(mesh.name))
      .forEach((mesh) => bone.expandByObject(mesh));
    if (!bone.isEmpty()) bone.expandByScalar(this.radius * 0.04);
    const previous = new Map();
    const pos = new THREE.Vector3();
    const quat = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    const corner = new THREE.Vector3();
    let lastCenter = null;
    const moving = times.map((t) => {
      this.time = t;
      this.applyTime();
      this.model.updateMatrixWorld(true);
      const box = new THREE.Box3();
      const corners = [];
      for (const mesh of meshes) {
        const e = mesh.matrixWorld.elements;
        const before = previous.get(mesh);
        previous.set(mesh, e.slice());
        if (!before) continue;
        mesh.matrixWorld.decompose(pos, quat, scale);
        if (Math.min(scale.x, scale.y, scale.z) < 0.01) continue;           // todavía oculta
        let change = 0;
        for (let i = 0; i < 16; i += 1) change = Math.max(change, Math.abs(e[i] - before[i]) * (i >= 12 && i < 15 ? 1 / this.radius : 1));
        if (change <= 1e-4) continue;
        box.expandByObject(mesh);
        const geometry = mesh.geometry;
        if (!geometry.boundingBox) geometry.computeBoundingBox();
        const { min, max } = geometry.boundingBox;
        for (let c = 0; c < 8; c += 1) {
          corners.push(corner.set(c & 1 ? max.x : min.x, c & 2 ? max.y : min.y, c & 4 ? max.z : min.z).applyMatrix4(mesh.matrixWorld).clone());
        }
      }
      if (box.isEmpty()) { lastCenter = null; return null; }
      // Si avanza y su punta delantera ya llegó al hueso, el foco es esa punta (lo que perfora o entra).
      const center = box.getCenter(new THREE.Vector3());
      const advance = lastCenter ? center.clone().sub(lastCenter) : null;
      lastCenter = center;
      if (advance && advance.length() > this.radius * 0.002 && !bone.isEmpty()) {
        advance.normalize();
        const front = corners.reduce((best, p) => (p.dot(advance) > best.dot(advance) ? p : best));
        if (bone.containsPoint(front)) {
          const near = new THREE.Box3().setFromCenterAndSize(front, new THREE.Vector3().setScalar(this.radius * 0.1));
          near.contact = true;
          return near;
        }
      }
      return box;
    });
    this.time = keep;
    this.applyTime();
    // Si en la ventana hay contacto con el hueso, manda el contacto; si no, todo lo que se mueve.
    const raw = moving.map((_, i) => {
      const near = new THREE.Box3();
      const all = new THREE.Box3();
      for (let k = Math.max(0, i - 1); k <= Math.min(moving.length - 1, i + 6); k += 1) {
        if (!moving[k]) continue;
        (moving[k].contact ? near : all).union(moving[k]);
      }
      const box = near.isEmpty() ? all : near;
      return box.isEmpty() ? null : box;
    });
    const first = raw.find(Boolean);
    if (!first) return;
    // Dirección del movimiento en cada instante (para mirarlo de costado): cómo se corre el centro de lo que se
    // mueve. Los giros en el sitio no tienen dirección y no cambian el ángulo.
    const step3 = moving.map((box, i) => {
      const before = moving[i - 1];
      if (!box || !before) return null;
      const d = box.getCenter(new THREE.Vector3()).sub(before.getCenter(new THREE.Vector3()));
      return d.length() > this.radius * 0.002 ? d.normalize() : null;
    });
    const axes = step3.map((_, i) => {
      const acc = new THREE.Vector3();
      let ref = null;
      for (let k = Math.max(0, i - 2); k <= Math.min(step3.length - 1, i + 8); k += 1) {
        const v = step3[k];
        if (!v) continue;
        ref = ref || v;
        acc.addScaledVector(v, v.dot(ref) < 0 ? -1 : 1);       // ida y vuelta por el mismo eje cuentan igual
      }
      return acc.length() > 0.5 ? acc.normalize() : null;
    });
    let last = first;
    const minRadius = this.radius * 0.06;
    const centers = [];
    const radii = [];
    raw.forEach((box) => {
      last = box || last;
      centers.push(last.getCenter(new THREE.Vector3()));
      radii.push(Math.max(last.getSize(new THREE.Vector3()).length() / 2, minRadius));
    });
    // Suavizado de ±0,6 s para que el foco no salte de una pieza a otra.
    const smooth = (values, add, scaleBy) => values.map((_, i) => {
      let acc = null;
      let n = 0;
      for (let k = Math.max(0, i - 3); k <= Math.min(values.length - 1, i + 3); k += 1) { acc = add(acc, values[k]); n += 1; }
      return scaleBy(acc, n);
    });
    this.focus = {
      times,
      centers: smooth(centers, (a, v) => (a ? a.add(v) : v.clone()), (a, n) => a.divideScalar(n)),
      radii: smooth(radii, (a, v) => (a ?? 0) + v, (a, n) => a / n),
      axes,
    };
  }

  focusAt(t) {
    const { times, centers, radii } = this.focus;
    const x = THREE.MathUtils.clamp((t - times[0]) / 0.2, 0, times.length - 1);
    const i = Math.min(Math.floor(x), times.length - 2);
    const f = x - i;
    const axis = this.focus.axes[Math.round(x)];
    if (times.length < 2) return { center: centers[0], radius: radii[0], axis };
    return { center: centers[i].clone().lerp(centers[i + 1], f), radius: radii[i] + (radii[i + 1] - radii[i]) * f, axis };
  }

  // Lleva la cámara poco a poco hacia el foco. Si lo que se mueve avanza en una dirección, la cámara gira lo justo
  // para verlo de costado (si no, una pieza que viene hacia la cámara se vería corta).
  followFocus(delta) {
    const { center, radius, axis } = this.focusAt(this.time);
    const k = 1 - Math.exp(-Math.min(delta, 0.1) * 1.6);
    const vertical = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const horizontal = Math.atan(Math.tan(vertical) * Math.min(this.camera.aspect, 1));
    const wanted = (radius / Math.sin(Math.min(vertical, horizontal))) * 1.3;
    const offset = this.camera.position.clone().sub(this.controls.target);
    const distance = offset.length();
    offset.normalize();
    if (axis) {
      // Se mira de costado al movimiento: la dirección horizontal perpendicular a él (del lado donde ya está la
      // cámara), a la altura actual de la cámara pero entre 10° y 40°.
      const up = this.camera.up;
      const across = new THREE.Vector3().crossVectors(up, axis);
      if (across.lengthSq() > 1e-4) {
        across.normalize();
        if (across.dot(offset) < 0) across.negate();
        const height = THREE.MathUtils.clamp(Math.asin(THREE.MathUtils.clamp(offset.dot(up), -1, 1)), THREE.MathUtils.degToRad(10), THREE.MathUtils.degToRad(40));
        const side = across.multiplyScalar(Math.cos(height)).addScaledVector(up, Math.sin(height));
        offset.lerp(side, k * 0.6).normalize();
      }
    }
    this.controls.target.lerp(center, k);
    this.camera.position.copy(this.controls.target).addScaledVector(offset, distance + (wanted - distance) * k);
  }

  // El plano de recorte cercano sigue al acercamiento: si quedara fijo según el tamaño de toda la escena (que
  // crece cuando una pieza se aleja mucho), al acercarse a una pieza se cortaría y se vería su interior.
  fitClipping() {
    if (!this.radius) return;
    const distance = this.camera.position.distanceTo(this.controls.target);
    const near = Math.max(distance / 200, this.radius / 100000);
    if (Math.abs(near - this.camera.near) > near * 0.05) {
      this.camera.near = near;
      this.camera.updateProjectionMatrix();
    }
  }

  applyTime() {
    // El clip se reproduce en modo repetición: justo en su último instante volvería a la pose inicial.
    // Por eso nunca se pide el instante exacto del final, sino uno apenas antes (el último cuadro).
    if (this.mixer) this.mixer.setTime(Math.min(this.time, Math.max(0, (this.clip?.duration ?? 0) - 1e-3)));
  }

  async fetchBuffer(url, onProgress) {
    const response = await fetch(url);
    if (!response.ok) throw new Error('archivo');
    const total = Number(response.headers.get('Content-Length')) || 0;
    const reader = response.body.getReader();
    const chunks = [];
    let loaded = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      loaded += value.length;
      onProgress(total ? Math.round((loaded / total) * 100) : null);
    }
    const buffer = new Uint8Array(loaded);
    let offset = 0;
    for (const chunk of chunks) {
      buffer.set(chunk, offset);
      offset += chunk.length;
    }
    return buffer.buffer;
  }

  async load(source, onProgress) {
    const { asset, title } = source;
    const buffer = await this.fetchBuffer(asset.url, onProgress);
    const object = /\.stl$/i.test(asset.filename) ? this.parseStl(buffer, title) : await this.parseGltf(buffer);
    this.scene.add(object);
    this.model = object;
    this.roots = object.isMesh ? [object] : [...object.children];
    object.traverse((node) => {
      if (!node.isMesh) return;
      this.allMeshes.push(node);
      node.userData.piece = pieceName(node);
      // Cada pieza con su propio material, para resaltar una sin encender las demás.
      node.material = [node.material].flat().map((material) => {
        const own = material.clone();
        // Sin un entorno que reflejar, el metal se vería casi negro sobre el fondo oscuro.
        if ('metalness' in own) own.metalness = Math.min(own.metalness, 0.3);
        return own;
      });
      if (node.material.length === 1) node.material = node.material[0];
    });
    this.configure(source.settings || {}, { refit: true });
  }

  parseStl(buffer, title) {
    const geometry = new STLLoader().parse(buffer);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial(MATERIAL));
    mesh.name = title || 'Pieza';
    return mesh;
  }

  async parseGltf(buffer) {
    const gltf = await new GLTFLoader().parseAsync(buffer, '');
    this.clips = gltf.animations;
    if (this.clips.length) this.mixer = new THREE.AnimationMixer(gltf.scene);
    return gltf.scene;
  }

  // La escena (grupo raíz) que mueve una animación: la que contiene los objetos de sus pistas.
  rootsOf(clip) {
    const owners = new Set();
    for (const track of clip.tracks) {
      const nodeName = THREE.PropertyBinding.parseTrackName(track.name).nodeName;
      let node = this.model.getObjectByName(nodeName);
      while (node && node.parent && node.parent !== this.model) node = node.parent;
      if (node && node.parent === this.model) owners.add(node);
    }
    return owners;
  }

  // settings: { clip, start, end, hidden }. Cambia de escena, de tramo o de piezas ocultas sin recargar.
  configure(settings, { refit = false } = {}) {
    const previousClip = this.clip;
    this.clip = this.clips.find((clip) => clip.name === settings.clip) || this.clips[this.clips.length - 1] || null;

    // Solo se ve la escena de la animación elegida; las que no tienen animación propia se comparten.
    let active = new Set(this.roots);
    if (this.clip && this.roots.length > 1) {
      const owned = new Map(this.clips.map((clip) => [clip, this.rootsOf(clip)]));
      const mine = owned.get(this.clip);
      const anyOwner = new Set([...owned.values()].flatMap((set) => [...set]));
      if (mine.size) active = new Set(this.roots.filter((root) => mine.has(root) || !anyOwner.has(root)));
      this.roots.forEach((root) => { root.visible = active.has(root); });
    }
    const rootOf = (mesh) => {
      if (mesh === this.model) return mesh;
      let node = mesh;
      while (node.parent && node.parent !== this.model) node = node.parent;
      return node;
    };
    this.meshes = this.allMeshes.filter((mesh) => active.has(rootOf(mesh)));

    const hidden = new Set(settings.hidden ?? defaultHidden(this.pieces()));
    this.meshes.forEach((mesh) => { mesh.visible = !hidden.has(mesh.userData.piece); });
    this.hidden = hidden;

    if (this.mixer) {
      if (this.clip !== previousClip) {
        this.mixer.stopAllAction();
        if (this.clip) this.mixer.clipAction(this.clip).play();
      }
      const duration = this.clip?.duration || 0;
      this.start = THREE.MathUtils.clamp(settings.start ?? 0, 0, duration);
      this.end = THREE.MathUtils.clamp(settings.end ?? duration, this.start, duration);
      if (this.clip !== previousClip || this.time < this.start || this.time > this.end) this.time = this.start;
      this.applyTime();
    }
    if (refit || this.clip !== previousClip) this.fit();
    this.computeFocus();
  }

  info() {
    return {
      clips: this.clips.map((clip) => clip.name),
      clip: this.clip?.name ?? null,
      duration: this.clip?.duration ?? 0,
      start: this.start,
      end: this.end,
      time: this.time,
      hidden: [...(this.hidden || [])],
    };
  }

  pieces() {
    return [...new Set(this.meshes.map((mesh) => mesh.userData.piece))];
  }

  highlight(name) {
    for (const mesh of this.meshes) {
      const on = name !== null && mesh.userData.piece === name;
      [mesh.material].flat().forEach((material) => {
        if (material.emissive) {
          material.emissive.setHex(on ? 0xf56f0d : 0x000000);
          material.emissiveIntensity = on ? 0.45 : 1;
        }
      });
    }
  }

  pick(x, y) {
    const box = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((x - box.left) / box.width) * 2 - 1, -((y - box.top) / box.height) * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObjects(this.meshes.filter((mesh) => mesh.visible), false)[0];
    return hit ? hit.object.userData.piece : null;
  }

  // Avisa qué pieza hay bajo el cursor y cuál se tocó. Arrastrar para girar no cuenta como tocar.
  enablePicking({ onHover, onSelect }) {
    const canvas = this.renderer.domElement;
    let down = null;
    let waiting = false;
    let last = null;
    canvas.addEventListener('pointermove', (event) => {
      if (event.pointerType !== 'mouse' || down) return;
      last = event;
      if (waiting) return;
      waiting = true;
      requestAnimationFrame(() => {
        waiting = false;
        if (this.renderer && last) onHover(this.pick(last.clientX, last.clientY), last.clientX, last.clientY);
      });
    });
    canvas.addEventListener('pointerleave', () => {
      last = null;
      onHover(null, 0, 0);
    });
    canvas.addEventListener('pointerdown', (event) => { down = { x: event.clientX, y: event.clientY }; });
    window.addEventListener('pointerup', this.onPointerUp = (event) => {
      if (!down) return;
      const moved = Math.hypot(event.clientX - down.x, event.clientY - down.y);
      down = null;
      if (moved < 5 && event.target === canvas && event.button === 0) onSelect(this.pick(event.clientX, event.clientY), event.clientX, event.clientY);
    });
  }

  // El encuadre abarca todo lo que se ve durante el tramo: piezas largas o que se desplazan no quedan cortadas.
  fit() {
    const box = new THREE.Box3();
    const visible = () => this.meshes.filter((mesh) => mesh.visible);
    const grow = () => {
      this.model.updateMatrixWorld(true);
      visible().forEach((mesh) => box.expandByObject(mesh));
    };
    if (this.mixer && this.clip && this.end > this.start) {
      const keep = this.time;
      for (let i = 0; i <= 24; i += 1) {
        this.time = this.start + ((this.end - this.start) * i) / 24;
        this.applyTime();
        grow();
      }
      this.time = keep;
      this.applyTime();
    } else {
      grow();
    }
    if (box.isEmpty()) box.setFromObject(this.model);
    const size = box.getSize(new THREE.Vector3());
    this.center = box.getCenter(new THREE.Vector3());
    this.radius = Math.max(size.length() / 2, 0.001);
    this.camera.near = this.radius / 100;
    this.camera.far = this.radius * 100;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(this.center);
    this.view('iso');
  }

  // Ejes anatómicos del fémur, medidos en el modelo (sus coordenadas propias no coinciden con la anatomía:
  // está girado ~21° sobre su eje y ~7° inclinado). Superior: del centro de la rodilla al centro de la cabeza
  // femoral (eje mecánico, vertical en posición anatómica). Medial: línea condílea posterior, la referencia
  // rotacional más estable del fémur distal. Anterior: perpendicular a ambos.
  static FEMUR_AXES = {
    superior: [0.0758, 0.992, 0.1006],
    medial: [0.9315, -0.1065, 0.3479],
    anterior: [-0.3558, -0.0673, 0.9321],
  };

  anatomicalFrame() {
    const femur = this.meshes.find((mesh) => mesh.visible && /femur/i.test(`${mesh.name} ${mesh.parent?.name || ''}`) && !/canal/i.test(mesh.name));
    if (!femur) return null;
    femur.updateMatrixWorld(true);
    const rotation = new THREE.Matrix3().setFromMatrix4(femur.matrixWorld);
    const axis = (v) => new THREE.Vector3(...v).applyMatrix3(rotation).normalize();
    const a = Engine3D.FEMUR_AXES;
    return { superior: axis(a.superior), medial: axis(a.medial), anterior: axis(a.anterior) };
  }

  // La cámara gira alrededor del objetivo con "arriba" fijo; para que el eje del fémur quede vertical en la
  // pantalla, el control de cámara se rehace con el "arriba" de la vista elegida.
  setCameraUp(up) {
    if (this.camera.up.distanceTo(up) < 1e-6) return;
    const target = this.controls.target.clone();
    this.controls.dispose();
    this.camera.up.copy(up);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.target.copy(target);
    this.watchControls();
  }

  view(name) {
    // El campo de visión horizontal puede ser menor que el vertical en pantallas angostas: se usa el menor.
    const vertical = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const horizontal = Math.atan(Math.tan(vertical) * Math.min(this.camera.aspect, 1));
    const distance = (this.radius / Math.sin(Math.min(vertical, horizontal))) * 1.08;
    const f = this.anatomicalFrame() || { superior: new THREE.Vector3(0, 1, 0), medial: new THREE.Vector3(1, 0, 0), anterior: new THREE.Vector3(0, 0, 1) };
    // Anterior: la cara de adelante, con la cabeza femoral a la derecha (fémur derecho). Posterior: al revés.
    // Superior: desde arriba, con la cabeza arriba en la pantalla y lo anterior a la derecha.
    const views = {
      iso: { direction: new THREE.Vector3(1, 0.7, 1), up: new THREE.Vector3(0, 1, 0) },
      anterior: { direction: f.anterior.clone(), up: f.superior.clone() },
      posterior: { direction: f.anterior.clone().negate(), up: f.superior.clone() },
      superior: { direction: f.superior.clone(), up: f.medial.clone() },
    };
    const { direction, up } = views[name];
    direction.normalize();
    this.setCameraUp(up.normalize());
    this.camera.position.copy(this.center).addScaledVector(direction, distance);
    this.controls.target.copy(this.center);
    this.controls.update();
  }

  zoom(factor) {
    this.setAutoCamera(false);
    const offset = this.camera.position.clone().sub(this.controls.target).multiplyScalar(factor);
    this.camera.position.copy(this.controls.target).add(offset);
  }

  hasAnimation() {
    return Boolean(this.mixer && this.clip);
  }

  setPlaying(value) {
    // Si ya terminó, reproducir vuelve a empezar desde el inicio del tramo.
    if (value && this.time >= this.end) this.time = this.start;
    this.playing = value;
    this.clock.getDelta();
  }

  setSpeed(value) {
    this.speed = value;
  }

  restart() {
    this.seek(this.start);
    this.setAutoCamera(true);
  }

  seek(seconds) {
    if (!this.mixer) return;
    this.time = THREE.MathUtils.clamp(seconds, this.start, this.end);
    this.applyTime();
  }

  seekRatio(ratio) {
    this.seek(this.start + ratio * (this.end - this.start));
  }

  ratio() {
    const span = this.end - this.start;
    return span > 0 ? (this.time - this.start) / span : 0;
  }

  dispose() {
    if (this.onPointerUp) window.removeEventListener('pointerup', this.onPointerUp);
    this.observer.disconnect();
    this.renderer.setAnimationLoop(null);
    this.controls.dispose();
    this.allMeshes.forEach((mesh) => {
      mesh.geometry?.dispose();
      [mesh.material].flat().forEach((material) => material?.dispose());
    });
    this.renderer.dispose();
    this.renderer.domElement.remove();
    this.renderer = null;
  }
}
