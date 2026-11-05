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
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
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

  view(name) {
    // El campo de visión horizontal puede ser menor que el vertical en pantallas angostas: se usa el menor.
    const vertical = THREE.MathUtils.degToRad(this.camera.fov / 2);
    const horizontal = Math.atan(Math.tan(vertical) * Math.min(this.camera.aspect, 1));
    const distance = (this.radius / Math.sin(Math.min(vertical, horizontal))) * 1.08;
    const direction = {
      iso: new THREE.Vector3(1, 0.7, 1),
      front: new THREE.Vector3(0, 0, 1),
      side: new THREE.Vector3(1, 0, 0),
      top: new THREE.Vector3(0, 1, 0.001),
    }[name].normalize();
    this.camera.position.copy(this.center).addScaledVector(direction, distance);
    this.controls.target.copy(this.center);
    this.controls.update();
  }

  zoom(factor) {
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
