// Escenas 3D de las etapas 1 a 4. Se abre con ?escena=<nombre> y se fotografía con generar3d.py.
// Unidades en metros. Paciente: cabeza hacia -x, cara hacia +y, lado derecho (afectado) hacia +z.
// Fémur del modelo del proyecto: arriba +y, medial +x, anterior +z (es un fémur derecho).
import * as THREE from '/vendor/three/three.module.js';
import { GLTFLoader } from '/vendor/three/GLTFLoader.js';
import { RoomEnvironment } from '/vendor/three/RoomEnvironment.js';
import { RoundedBoxGeometry } from '/vendor/three/RoundedBoxGeometry.js';
import { STLLoader } from '/vendor/three/STLLoader.js';
import { mergeVertices } from '/vendor/three/BufferGeometryUtils.js';

const W = 1600;
const H = 1000;
const NAVY = 0x021a35;
const ORANGE = 0xf56f0d;
const C = { white: '#ffffff', muted: '#b3c1d0', orange: '#ff8a33', navy: '#021a35', panel: '#0d2c4f', line: '#3a5f86' };
const TABLE_Y = 0.92;

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(W, H, false);
renderer.setPixelRatio(1);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setClearColor(NAVY, 1);
renderer.localClippingEnabled = true;
document.getElementById('lienzo').append(renderer.domElement);

const environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;

// ---------- Materiales ----------

const std = (color, roughness = 0.6, metalness = 0, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
const M = {
  skin: std(0xe0ad8a, 0.62),
  gown: std(0x2f8f86, 0.85),
  cap: std(0x5b9fd6, 0.85),
  boot: std(0x4a3128, 0.72),
  strap: std(0x2c1e18, 0.6),
  pad: std(0x6b6775, 0.75),
  tableFrame: std(0x9b8a93, 0.5, 0.15),
  base: std(0xa98f9b, 0.55),
  metal: std(0xc9ced4, 0.3, 0.85),
  metalDark: std(0x3a3f46, 0.45, 0.6),
  shell: std(0xe6e3de, 0.42),
  accent: std(0x7f9fd0, 0.45),
  bone: std(0xeadfca, 0.58),
  canal: std(0xc77b4a, 0.6),
  orange: std(ORANGE, 0.4, 0, { emissive: ORANGE, emissiveIntensity: 0.55 }),
  nail: std(0xf56f0d, 0.28, 0.55, { emissive: ORANGE, emissiveIntensity: 0.25 }),
  red: std(0xd6281e, 0.5, 0, { emissive: 0xd6281e, emissiveIntensity: 0.6 }),
  white: std(0xffffff, 0.5, 0, { emissive: 0xffffff, emissiveIntensity: 0.35 }),
};

function glass(color, opacity) {
  return new THREE.MeshPhysicalMaterial({ color, roughness: 0.45, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide });
}

// ---------- Formas ----------

function shadowed(mesh) {
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function box(w, h, d, material, position = [0, 0, 0], radius = 0.012) {
  const mesh = shadowed(new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 4, Math.min(radius, Math.min(w, h, d) / 2.01)), material));
  mesh.position.set(...position);
  return mesh;
}

function ball(radius, material, position, scale = [1, 1, 1]) {
  const mesh = shadowed(new THREE.Mesh(new THREE.SphereGeometry(radius, 48, 32), material));
  mesh.position.set(...position);
  mesh.scale.set(...scale);
  return mesh;
}

// Barra entre dos puntos.
function rod(a, b, radius, material, radial = 24) {
  const start = new THREE.Vector3(...a);
  const end = new THREE.Vector3(...b);
  const length = start.distanceTo(end);
  const mesh = shadowed(new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, radial), material));
  mesh.position.copy(start).add(end).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.sub(start).normalize());
  return mesh;
}

function tube(points, radius, material, closed = false) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), closed);
  return shadowed(new THREE.Mesh(new THREE.TubeGeometry(curve, 96, radius, 16, closed), material));
}

// Forma orgánica: anillos elípticos a lo largo de un recorrido suave.
// Cada estación: [x, y, z, ancho, alto]. "side" es la dirección del ancho.
function loft(stations, material, { side = [0, 0, 1], radial = 40, steps = 80 } = {}) {
  const curve = new THREE.CatmullRomCurve3(stations.map((s) => new THREE.Vector3(s[0], s[1], s[2])));
  const widths = new THREE.CatmullRomCurve3(stations.map((s, i) => new THREE.Vector3(i, s[3], s[4])));
  const sideVector = new THREE.Vector3(...side).normalize();
  const positions = [];
  const indices = [];
  const rings = steps + 3;
  for (let i = 0; i < rings; i += 1) {
    const raw = (i - 1) / steps;
    const t = THREE.MathUtils.clamp(raw, 0, 1);
    const center = curve.getPoint(t);
    const size = widths.getPoint(t);
    const tangent = curve.getTangent(t);
    const u = sideVector.clone().addScaledVector(tangent, -sideVector.dot(tangent)).normalize();
    const v = new THREE.Vector3().crossVectors(tangent, u).normalize();
    const shrink = i === 0 || i === rings - 1 ? 0.001 : 1;
    for (let j = 0; j < radial; j += 1) {
      const angle = (j / radial) * Math.PI * 2;
      const p = center.clone()
        .addScaledVector(u, Math.cos(angle) * size.y * shrink)
        .addScaledVector(v, Math.sin(angle) * size.z * shrink);
      positions.push(p.x, p.y, p.z);
    }
  }
  for (let i = 0; i < rings - 1; i += 1) {
    for (let j = 0; j < radial; j += 1) {
      const a = i * radial + j;
      const b = i * radial + (j + 1) % radial;
      const c = (i + 1) * radial + j;
      const d = (i + 1) * radial + (j + 1) % radial;
      indices.push(a, b, c, b, d, c);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return shadowed(new THREE.Mesh(geometry, material));
}

function canvasTexture(width, height, draw) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  draw(canvas.getContext('2d'));
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// ---------- Paciente, mesa y arco en C ----------

const HIP_X = 0.1;
const LEG_LENGTH = 0.86;
const BODY_Y = TABLE_Y + 0.12;

function leg(side, materialSkin = M.skin) {
  const group = new THREE.Group();
  const z = 0;
  group.add(loft([
    [-0.04, 0, z, 0.105, 0.11],
    [0.14, 0, z, 0.098, 0.105],
    [0.32, -0.01, z, 0.08, 0.085],
    [0.44, -0.015, z, 0.062, 0.066],
    [0.52, -0.01, z, 0.06, 0.066],
    [0.64, -0.03, z, 0.055, 0.058],
    [0.76, -0.04, z, 0.04, 0.042],
    [0.83, -0.05, z, 0.033, 0.035],
  ], materialSkin));
  return group;
}

function boot(strapMaterial = M.strap) {
  const group = new THREE.Group();
  group.add(loft([
    [0.6, -0.03, 0, 0.066, 0.07],
    [0.72, -0.04, 0, 0.056, 0.058],
    [0.83, -0.052, 0, 0.05, 0.052],
    [0.865, -0.05, 0, 0.056, 0.062],
  ], M.boot));
  group.add(loft([
    [0.86, -0.1, 0, 0.05, 0.052],
    [0.87, -0.04, 0, 0.052, 0.06],
    [0.875, 0.05, 0, 0.05, 0.05],
    [0.87, 0.14, 0, 0.044, 0.032],
    [0.862, 0.2, 0, 0.034, 0.018],
  ], M.boot, { side: [0, 0, 1] }));
  group.add(tube([[0.66, 0.035, 0.0], [0.66, -0.03, 0.068], [0.66, -0.1, 0.0], [0.66, -0.03, -0.068]], 0.012, strapMaterial, true));
  group.add(tube([[0.8, 0.0, 0.0], [0.8, -0.05, 0.056], [0.8, -0.105, 0.0], [0.8, -0.05, -0.056]], 0.012, strapMaterial, true));
  return group;
}

function tractionArm(strapMaterial) {
  const group = new THREE.Group();
  const y = -0.12;
  group.add(rod([0.05, y, 0], [1.12, y - 0.02, 0], 0.016, M.metal));
  group.add(box(0.2, 0.04, 0.13, M.metalDark, [0.78, y + 0.02, 0]));
  group.add(box(0.05, 0.24, 0.15, M.shell, [0.93, y + 0.1, 0]));
  group.add(box(0.08, 0.05, 0.09, M.metalDark, [1.05, y - 0.02, 0]));
  group.add(rod([1.05, y - 0.02, 0], [1.05, -0.9, 0], 0.016, M.metal));
  group.add(box(0.2, 0.025, 0.2, M.metalDark, [1.05, -0.9, 0]));
  group.add(boot(strapMaterial));
  return group;
}

function table(width = 0.56) {
  const group = new THREE.Group();
  const y = TABLE_Y;
  for (const [cx, w] of [[-0.7, 0.4], [-0.25, 0.46], [0.1, 0.22]]) {
    group.add(box(w - 0.015, 0.05, width, M.pad, [cx, y, 0], 0.02));
    group.add(box(w - 0.01, 0.045, width + 0.03, M.tableFrame, [cx, y - 0.045, 0], 0.008));
  }
  group.add(box(0.26, 0.56, 0.3, M.base, [-0.32, y - 0.36, 0], 0.02));
  group.add(box(0.96, 0.06, 0.62, M.base, [-0.32, 0.04, 0], 0.03));
  for (const [x, z] of [[-0.75, 0.27], [-0.75, -0.27], [0.11, 0.27], [0.11, -0.27]]) {
    group.add(ball(0.03, M.metalDark, [x, 0.03, z]));
  }
  return group;
}

function patient({ bulk = 1, torsoRotation = 0, skinMaterial = M.skin, gownMaterial = M.gown } = {}) {
  const group = new THREE.Group();
  const y = BODY_Y;
  const upper = new THREE.Group();
  const w = bulk;
  // Tronco con bata
  upper.add(loft([
    [-0.56, y, 0, 0.13 * w, 0.075],
    [-0.5, y + 0.01, 0, 0.235 * w, 0.11],
    [-0.36, y + 0.03, 0, 0.225 * w, 0.125 * w],
    [-0.16, y + 0.015, 0, 0.18 * w, 0.115 * w],
    [0.02, y + 0.01, 0, 0.2 * w, 0.115 * w],
    [0.14, y + 0.0, 0, 0.215 * w, 0.115],
  ], gownMaterial));
  // Brazos
  for (const s of [1, -1]) {
    const shoulderZ = 0.245 * w;
    upper.add(loft([
      [-0.46, y + 0.02, s * shoulderZ, 0.058, 0.058],
      [-0.28, y - 0.01, s * (shoulderZ + 0.03), 0.046, 0.046],
      [-0.12, y - 0.03, s * (shoulderZ + 0.05), 0.04, 0.04],
      [0.02, y - 0.04, s * (shoulderZ + 0.06), 0.03, 0.028],
    ], skinMaterial));
    upper.add(loft([
      [-0.47, y + 0.02, s * (shoulderZ - 0.015), 0.07, 0.07],
      [-0.34, y + 0.005, s * (shoulderZ + 0.015), 0.062, 0.062],
    ], gownMaterial));
    upper.add(ball(0.05, skinMaterial, [0.07, y - 0.045, s * (shoulderZ + 0.062)], [1.25, 0.42, 0.8]));
  }
  // Cuello y cabeza
  upper.add(loft([[-0.62, y + 0.015, 0, 0.055, 0.052], [-0.53, y + 0.01, 0, 0.065, 0.06]], skinMaterial));
  upper.add(ball(0.105, skinMaterial, [-0.71, y + 0.04, 0], [1.08, 0.98, 0.88]));
  upper.add(ball(0.11, M.cap, [-0.775, y + 0.035, 0], [0.92, 0.98, 0.98]));
  // Rasgos de la cara, mirando hacia arriba
  upper.add(ball(0.016, skinMaterial, [-0.675, y + 0.145, 0], [1.3, 0.9, 0.75]));
  upper.add(ball(0.03, skinMaterial, [-0.625, y + 0.075, 0], [1, 0.8, 1.15]));
  for (const s of [1, -1]) upper.add(ball(0.009, M.metalDark, [-0.715, y + 0.135, s * 0.032], [1.5, 0.35, 0.9]));
  upper.rotation.y = torsoRotation;
  upper.position.set(HIP_X, 0, 0);
  upper.applyMatrix4(new THREE.Matrix4().makeTranslation(-HIP_X, 0, 0));
  group.add(upper);
  return group;
}

// Piernas con su brazo de tracción. El ángulo positivo lleva la pierna hacia la línea media.
function limb(side, angle, { skin = M.skin, strap = M.strap, withArm = true } = {}) {
  const z = side * 0.1;
  const group = new THREE.Group();
  group.position.set(HIP_X, BODY_Y, z);
  group.rotation.y = side * THREE.MathUtils.degToRad(angle);
  group.add(leg(side, skin));
  if (withArm) group.add(tractionArm(strap));
  return group;
}

function cArm({ highlight = false } = {}) {
  const group = new THREE.Group();
  const center = new THREE.Vector3(HIP_X, 1.03, 0);
  const radius = 0.62;
  // La C se abre hacia quien mira (+z) y su lomo pasa por detrás de la mesa (-z).
  const start = -Math.PI / 2;
  const end = Math.PI / 2;
  const shape = new THREE.Shape();
  shape.absarc(0, 0, radius + 0.06, start, end, false);
  shape.absarc(0, 0, radius - 0.03, end, start, true);
  const geometry = new THREE.ExtrudeGeometry(shape, { depth: 0.13, bevelEnabled: true, bevelSize: 0.012, bevelThickness: 0.012, bevelSegments: 4, curveSegments: 96 });
  geometry.translate(0, 0, -0.065);
  const arc = shadowed(new THREE.Mesh(geometry, highlight ? std(0xf08a3c, 0.38) : M.shell));
  arc.rotation.y = Math.PI / 2;
  arc.position.copy(center);
  group.add(arc);
  // Detector arriba y emisor abajo
  const top = shadowed(new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.18, 64), M.shell));
  top.position.set(center.x, center.y + radius + 0.05, 0);
  group.add(top);
  const ring = shadowed(new THREE.Mesh(new THREE.CylinderGeometry(0.175, 0.175, 0.03, 64), M.accent));
  ring.position.set(center.x, center.y + radius - 0.05, 0);
  group.add(ring);
  const bottom = shadowed(new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.13, 64), M.shell));
  bottom.position.set(center.x, center.y - radius - 0.03, 0);
  group.add(bottom);
  // Haz
  const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.1, 2 * radius - 0.14, 48, 1, true), glass(0xffe7a0, 0.2));
  beam.position.set(center.x, center.y, 0);
  group.add(beam);
  // Soporte y carro
  group.add(box(0.2, 0.14, 0.3, M.shell, [center.x, center.y, -radius - 0.13]));
  group.add(box(0.12, 0.11, 0.34, M.shell, [center.x, center.y, -radius - 0.4]));
  const cz = -1.25;
  group.add(box(0.56, 0.86, 0.5, M.shell, [center.x, 0.56, cz], 0.04));
  group.add(box(0.5, 0.42, 0.015, M.accent, [center.x, 0.42, cz + 0.255]));
  group.add(box(0.62, 0.05, 0.56, M.accent, [center.x, 0.1, cz], 0.02));
  for (const [dx, dz] of [[-0.24, 0.22], [0.24, 0.22], [-0.24, -0.22], [0.24, -0.22]]) group.add(ball(0.04, M.metalDark, [center.x + dx, 0.04, cz + dz]));
  group.add(rod([center.x, 1.0, cz], [center.x, 1.28, cz], 0.03, M.shell));
  // Monitor con la silueta del hueso
  group.add(box(0.72, 0.42, 0.04, M.shell, [center.x, 1.5, cz + 0.02], 0.02));
  const screenTexture = canvasTexture(720, 420, (ctx) => {
    ctx.fillStyle = '#0a0d10';
    ctx.fillRect(0, 0, 720, 420);
    ctx.fillStyle = '#c9ced2';
    ctx.beginPath();
    FEMUR_AP.forEach(([x, y], i) => {
      const px = 360 + (x + 0) * 2.1;
      const py = 480 - y * 1.9;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.closePath();
    ctx.fill();
  });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.66, 0.37), new THREE.MeshStandardMaterial({ map: screenTexture, roughness: 0.3, emissive: 0xffffff, emissiveMap: screenTexture, emissiveIntensity: 0.55 }));
  screen.position.set(center.x, 1.5, cz + 0.042);
  group.add(screen);
  return group;
}

const FEMUR_AP = [[-45, 191], [-44, 176], [-34, 160], [-30, 149], [-27, 122], [-26, 110], [-32, 48], [-31, 14], [-33, -14], [-2, -8], [-1, 31], [-3, 52], [1, 73], [2, 93], [8, 118], [12, 126], [23, 135], [24, 138], [23, 145], [18, 152], [16, 156], [18, 167], [20, 172], [23, 175], [36, 175], [44, 179], [48, 183], [52, 188], [53, 198], [52, 205], [48, 211], [43, 216], [34, 221], [27, 222], [19, 221], [9, 217], [3, 213], [-3, 209], [-18, 214], [-23, 213], [-36, 204], [-42, 198]];

function floorAndLights(scene, { key = [1.6, 3.6, 2.6], span = 3.5, floorY = 0 } = {}) {
  scene.environment = environment;
  scene.background = new THREE.Color(NAVY);
  const light = new THREE.DirectionalLight(0xffffff, 2.3);
  light.position.set(...key);
  light.castShadow = true;
  light.shadow.mapSize.set(4096, 4096);
  light.shadow.camera.left = -span;
  light.shadow.camera.right = span;
  light.shadow.camera.top = span;
  light.shadow.camera.bottom = -span;
  light.shadow.bias = -0.0002;
  light.shadow.radius = 5;
  scene.add(light);
  const fill = new THREE.DirectionalLight(0xbcd2ee, 0.5);
  fill.position.set(-2, 2, -1);
  scene.add(fill);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.ShadowMaterial({ opacity: 0.42 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = floorY;
  floor.receiveShadow = true;
  scene.add(floor);
}

function perspective(position, target, { fov = 30, up = [0, 1, 0] } = {}) {
  const camera = new THREE.PerspectiveCamera(fov, W / H, 0.02, 40);
  camera.position.set(...position);
  camera.up.set(...up);
  camera.lookAt(...target);
  camera.updateMatrixWorld();
  return camera;
}


// ---------- Plantilla radiográfica (modelo de Cielo) ----------
// STL en milímetros: 25 de ancho (x), 246 de largo (y, proximal arriba), 2 de grosor (z).
// Ranura del ángulo cuello-diáfisis centrada en y = 205 mm; corchetes de diámetro (centro y):
// 12 mm a 74.5, 11 mm a 95, 10 mm a 115.5 y 9.4 mm a 136; muescas de largo cada 20 mm abajo.
const TEMPLATE = { slotY: 0.205, bracket12Y: 0.0745, length: 0.246, halfWidth: 0.0125 };
let templateGeometry = null;

async function loadTemplate() {
  if (templateGeometry) return;
  const buffer = await (await fetch('/ilustraciones3d/plantilla.stl')).arrayBuffer();
  templateGeometry = new STLLoader().parse(buffer);
  templateGeometry.scale(0.001, 0.001, 0.001);
  templateGeometry.computeVertexNormals();
}

// La plantilla es de acetato transparente: se ve el hueso a través y los cortes quedan marcados.
function radiographicTemplate({ mirror = false, opacity = 0.5 } = {}) {
  const group = new THREE.Group();
  const sheet = new THREE.Mesh(templateGeometry, new THREE.MeshPhysicalMaterial({
    color: 0xf7a35c, roughness: 0.3, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide,
    emissive: ORANGE, emissiveIntensity: 0.18,
  }));
  group.add(sheet);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(templateGeometry, 25), new THREE.LineBasicMaterial({ color: 0xff8a33 }));
  group.add(edges);
  if (mirror) group.scale.x = -1;
  return group;
}

// ---------- Fémur del modelo ----------

let femurGeometries = null;
let canalGeometry = null;

async function loadFemur() {
  if (femurGeometries) return;
  const content = await (await fetch('/api/content')).json();
  const asset = Object.values(content.assets).find((item) => item.filename.startsWith('apertura'));
  const buffer = await (await fetch(asset.url)).arrayBuffer();
  const gltf = await new GLTFLoader().parseAsync(buffer, '');
  // En las animaciones el grupo Anatomia acomoda el hueso al instrumental (corrido, girado y agrandado);
  // las ilustraciones están medidas sobre el fémur original, así que ese ajuste se deshace aquí.
  gltf.scene.traverse((node) => {
    if (node.name.startsWith('Anatomia')) { node.position.set(0, 0, 0); node.quaternion.identity(); node.scale.set(1, 1, 1); }
  });
  gltf.scene.updateMatrixWorld(true);
  femurGeometries = [];
  gltf.scene.traverse((node) => {
    if (!node.isMesh) return;
    if (node.name.startsWith('Femur')) femurGeometries.push(node.geometry.clone().applyMatrix4(node.matrixWorld));
    if (node.name.startsWith('Canal')) canalGeometry = node.geometry.clone().applyMatrix4(node.matrixWorld);
  });
  femurGeometries = femurGeometries.map(closeEntry);
  femurGeometries.forEach((g) => g.computeVertexNormals());
  canalGeometry.computeVertexNormals();
}

// El modelo trae abierto el orificio de entrada (resultado de la apertura del canal, etapa posterior).
// Aquí se rellena el borde de esa abertura con una tapa, para que el fémur se vea entero y normal.
function closeEntry(source) {
  let geometry = source.clone();
  for (const name of Object.keys(geometry.attributes)) if (name !== 'position') geometry.deleteAttribute(name);
  geometry = mergeVertices(geometry, 1e-6);
  const index = Array.from(geometry.index.array);
  const pos = geometry.attributes.position;
  const count = new Map();
  const directed = [];
  for (let i = 0; i < index.length; i += 3) {
    for (let k = 0; k < 3; k += 1) {
      const a = index[i + k];
      const b = index[i + ((k + 1) % 3)];
      const key = a < b ? `${a}_${b}` : `${b}_${a}`;
      count.set(key, (count.get(key) || 0) + 1);
      directed.push([a, b, key]);
    }
  }
  const near = (i) => Math.hypot(pos.getX(i) - ENTRY_HOLE.x, pos.getY(i) - ENTRY_HOLE.y, pos.getZ(i) - ENTRY_HOLE.z) < 0.02;
  const rim = directed.filter(([a, b, key]) => count.get(key) === 1 && near(a) && near(b));
  if (!rim.length) return source;
  const center = new THREE.Vector3();
  const used = new Set();
  rim.forEach(([a, b]) => { used.add(a); used.add(b); });
  used.forEach((i) => center.add(new THREE.Vector3(pos.getX(i), pos.getY(i), pos.getZ(i))));
  center.divideScalar(used.size);
  const positions = Array.from(pos.array);
  const c = positions.length / 3;
  positions.push(center.x, center.y + 0.0006, center.z);
  rim.forEach(([a, b]) => index.push(b, a, c));
  const closed = new THREE.BufferGeometry();
  closed.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  closed.setIndex(index);
  return closed;
}

// El modelo trae ya abierto el orificio de entrada (es el resultado de la etapa 5).
// En las etapas anteriores el hueso aún está cerrado, así que se tapa.
function femur(material = M.bone, { mirror = false, closed = false } = {}) {
  const group = new THREE.Group();
  femurGeometries.forEach((geometry) => {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = !material.transparent;
    mesh.receiveShadow = true;
    group.add(mesh);
  });
  if (closed) {
    const plug = new THREE.Mesh(new THREE.SphereGeometry(0.0095, 32, 16), material);
    plug.position.set(-0.0045, 0.2045, -0.0012);
    plug.scale.set(1.05, 0.3, 1.05);
    group.add(plug);
  }
  if (mirror) group.scale.x = -1;
  return group;
}

function canal() {
  return shadowed(new THREE.Mesh(canalGeometry, M.canal));
}

// Canal intramedular esquemático: un tubo recto siguiendo el eje del canal del modelo, de diámetro parejo,
// cuyas puntas se desvanecen (no se ve dónde empieza ni dónde termina).
// Por defecto el canal mide 12 mm y va paralelo a la regla (vertical), centrado en su corchete de Φ12 mm
// (la regla se ubica en x = -0,5 mm): así sus dos paredes coinciden con los bordes del corchete.
function straightCanal({ radius = 0.006, through = [-0.0005, 0.02], parallel = true, clippingPlanes } = {}) {
  const pos = canalGeometry.attributes.position;
  const bins = new Map();
  for (let i = 0; i < pos.count; i += 1) {
    const key = Math.round(pos.getY(i) / 0.01);
    const b = bins.get(key) || { x: 0, z: 0, y: 0, n: 0 };
    b.x += pos.getX(i); b.y += pos.getY(i); b.z += pos.getZ(i); b.n += 1;
    bins.set(key, b);
  }
  const centers = [...bins.values()].map((b) => [b.x / b.n, b.y / b.n, b.z / b.n]).sort((a, b) => a[1] - b[1]);
  // Recta por mínimos cuadrados: x y z en función de y.
  const n = centers.length;
  const my = centers.reduce((s, c) => s + c[1], 0) / n;
  const fit = (k) => {
    const m = centers.reduce((s, c) => s + c[k], 0) / n;
    const slope = centers.reduce((s, c) => s + (c[1] - my) * (c[k] - m), 0) / centers.reduce((s, c) => s + (c[1] - my) ** 2, 0);
    return { m, slope };
  };
  const fx = fit(0);
  const fz = fit(2);
  const [tx, ty] = through;
  const sx = parallel ? 0 : fx.slope;
  const at = (y) => new THREE.Vector3(tx + sx * (y - ty), y, fz.m + fz.slope * (y - my));
  const bottom = at(centers[0][1]);
  const top = at(centers[n - 1][1]);
  const length = top.distanceTo(bottom);
  const geometry = new THREE.CylinderGeometry(radius, radius, length, 48, 1, true);
  const canvas = document.createElement('canvas');
  canvas.width = 4;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0, '#000');
  grad.addColorStop(0.2, '#fff');
  grad.addColorStop(0.8, '#fff');
  grad.addColorStop(1, '#000');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 4, 256);
  const alphaMap = new THREE.CanvasTexture(canvas);
  const material = std(0xc77b4a, 0.6, 0, { transparent: true, alphaMap, depthWrite: false, side: THREE.DoubleSide, ...(clippingPlanes ? { clippingPlanes } : {}) });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(top).add(bottom).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), top.clone().sub(bottom).normalize());
  return mesh;
}

const boneDouble = () => std(0xeadfca, 0.58, 0, { side: THREE.DoubleSide });
const boneGlass = (opacity) => new THREE.MeshPhysicalMaterial({ color: 0xeadfca, roughness: 0.5, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide });

// Puntos medidos en el modelo (metros)
const ENTRY_HOLE = new THREE.Vector3(-0.004, 0.205, -0.001);
const ENTRY = new THREE.Vector3(-0.004, 0.2135, -0.001);
const SHAFT_X = 0.002;
const LESSER_Y = 0.138;

// ---------- Etiquetas ----------

let svgLayer;

function resetLabels() {
  svgLayer = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgLayer.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svgLayer.setAttribute('width', W);
  svgLayer.setAttribute('height', H);
  document.getElementById('lienzo').append(svgLayer);
}

function add(tag, attrs, content) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  if (content) el.textContent = content;
  svgLayer.append(el);
  return el;
}

// Texto con un fondo oscuro detrás, para que se lea sobre la imagen.
function label(x, y, lines, { size = 30, color = C.white, weight = 500, anchor = 'start', plate = false } = {}) {
  const rows = [lines].flat();
  const lineHeight = size * 1.25;
  const backing = plate ? add('rect', { rx: 6, fill: C.navy, 'fill-opacity': 0.82 }) : null;
  const texts = rows.map((row, i) => add('text', { x, y: y + i * lineHeight, 'font-size': size, 'font-weight': weight, fill: color, 'text-anchor': anchor }, row));
  if (backing) {
    // El fondo se mide con el texto ya dibujado.
    const boxes = texts.map((el) => el.getBBox());
    const left = Math.min(...boxes.map((b) => b.x)) - 12;
    const right = Math.max(...boxes.map((b) => b.x + b.width)) + 12;
    const top = Math.min(...boxes.map((b) => b.y)) - 6;
    const bottom = Math.max(...boxes.map((b) => b.y + b.height)) + 6;
    Object.entries({ x: left, y: top, width: right - left, height: bottom - top }).forEach(([k, v]) => backing.setAttribute(k, v));
  }
}

function title(main, sub, x = 72) {
  label(x, 92, main, { size: 42, weight: 600 });
  if (sub) label(x, 144, sub, { size: 30, color: C.muted, weight: 400 });
}

function note() {
  label(W - 44, H - 34, 'Ilustración 3D esquemática, no está a escala', { size: 23, color: C.muted, weight: 400, anchor: 'end' });
}

function chip(x, y, text) {
  const width = text.length * 13.8 + 32;
  add('rect', { x, y, width, height: 46, rx: 6, fill: C.panel, stroke: C.line, 'stroke-width': 2 });
  add('text', { x: x + 16, y: y + 31, 'font-size': 25, fill: C.muted }, text);
}

function projector(camera, view = { x: 0, y: 0, w: W, h: H }) {
  return (point) => {
    const v = new THREE.Vector3(...(point.isVector3 ? point.toArray() : point)).project(camera);
    return [view.x + ((v.x + 1) / 2) * view.w, view.y + ((1 - v.y) / 2) * view.h];
  };
}

function callout(from, tx, ty, lines, { color = C.white, anchor = 'start', size = 30 } = {}) {
  add('line', { x1: from[0], y1: from[1], x2: tx, y2: ty, stroke: color, 'stroke-width': 2.5 });
  add('circle', { cx: from[0], cy: from[1], r: 7, fill: color });
  label(tx + (anchor === 'start' ? 12 : -12), ty + size * 0.35, lines, { size, color, anchor, plate: true });
}

function arrow2d(x1, y1, x2, y2, color = C.orange, width = 6) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const head = 20;
  add('line', { x1, y1, x2, y2, stroke: color, 'stroke-width': width, 'stroke-linecap': 'round' });
  const a = [x2 - head * Math.cos(angle - 0.45), y2 - head * Math.sin(angle - 0.45)];
  const b = [x2 - head * Math.cos(angle + 0.45), y2 - head * Math.sin(angle + 0.45)];
  add('path', { d: `M${a}L${x2} ${y2}L${b}`, fill: 'none', stroke: color, 'stroke-width': width, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
}

function render(scene, camera, view) {
  if (view) {
    renderer.setScissorTest(true);
    renderer.setViewport(view.x, H - view.y - view.h, view.w, view.h);
    renderer.setScissor(view.x, H - view.y - view.h, view.w, view.h);
  }
  renderer.render(scene, camera);
}

// ---------- Escenas ----------

function basePatient(scene, { rightAngle = 0, leftAngle = 0, patientOptions = {}, strap } = {}) {
  scene.add(table());
  scene.add(patient(patientOptions));
  scene.add(limb(1, rightAngle, { strap }));
  scene.add(limb(-1, leftAngle));
}

const ESCENAS = {
  '1-1-posicion-supina'() {
    const scene = new THREE.Scene();
    floorAndLights(scene);
    basePatient(scene, { leftAngle: -14, rightAngle: 0 });
    const camera = perspective([0.75, 2.5, 3.5], [0.02, 0.8, 0], { fov: 31 });
    render(scene, camera);
    const p = projector(camera);
    title('Paciente en posición supina', 'Boca arriba, en una mesa de tracción.');
    callout(p([-0.32, BODY_Y + 0.14, 0]), 560, 245, 'Boca arriba');
    callout(p([-0.32, 0.6, 0.15]), 200, 800, ['Mesa de tracción'], { color: C.orange });
    note();
  },
  '1-2-intensificador'() {
    const scene = new THREE.Scene();
    floorAndLights(scene);
    basePatient(scene, { leftAngle: -14 });
    scene.add(cArm());
    const camera = perspective([2.45, 2.55, 3.1], [0.05, 0.85, -0.35], { fov: 33 });
    render(scene, camera);
    const p = projector(camera);
    title('Usar el intensificador de imágenes', 'Para vigilar la cirugía.');
    callout(p([HIP_X, 1.03, -0.68]), 1240, 250, ['Fluoroscopio', '(arco en C)'], { color: C.orange });
    note();
  },
  'etapa1-paciente-obeso'() {
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [0.8, 4, 1.5] });
    const tilt = THREE.MathUtils.degToRad(8);
    scene.add(table(0.78));
    scene.add(patient({ bulk: 1.28, torsoRotation: tilt }));
    scene.add(limb(1, 9));
    scene.add(limb(-1, -16));
    const troch = [HIP_X - 0.03, BODY_Y + 0.11, 0.24];
    scene.add(ball(0.03, M.orange, troch));
    const camera = perspective([0.32, 3.6, 1.15], [0.28, 0.9, 0.03], { fov: 31 });
    render(scene, camera);
    const p = projector(camera);
    title('En un paciente obeso', 'Inclinar el cuerpo hacia el lado sano y aducir el miembro inferior.');
    callout(p(troch), 860, 845, ['Trocánter mayor destacado: cuesta menos', 'introducir el clavo'], { color: C.orange, size: 28 });
    const head = p([-0.62, BODY_Y, -0.1]);
    arrow2d(head[0] - 60, head[1] - 20, head[0] - 60, head[1] - 150);
    label(head[0] - 90, head[1] - 180, 'Hacia el lado sano', { color: C.orange, plate: true });
    label(1390, 300, 'Lado sano', { color: C.muted, plate: true });
    label(1390, 690, 'Lado afectado', { plate: true, anchor: 'start', size: 28 });
    note();
  },
  '2-1-aduccion'() {
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [0.8, 4, 1.2] });
    const angle = 12;
    basePatient(scene, { rightAngle: angle, leftAngle: -14 });
    const hip = [HIP_X, BODY_Y + 0.14, 0.1];
    const a = THREE.MathUtils.degToRad(angle);
    const end = [hip[0] + Math.cos(a) * 1.02, hip[1], hip[2] - Math.sin(a) * 1.02];
    scene.add(tube([hip, end], 0.008, M.orange));
    for (let t = 0; t < 1; t += 0.1) scene.add(rod([hip[0] + t * 1.05, hip[1], hip[2]], [hip[0] + (t + 0.055) * 1.05, hip[1], hip[2]], 0.006, M.white));
    const arcPoints = [];
    for (let i = 0; i <= 12; i += 1) {
      const b = a * (i / 12);
      arcPoints.push([hip[0] + Math.cos(b) * 0.72, hip[1], hip[2] - Math.sin(b) * 0.72]);
    }
    scene.add(tube(arcPoints, 0.01, M.orange));
    const camera = perspective([0.3, 3.75, 0.85], [0.3, 0.9, 0.0], { fov: 31 });
    render(scene, camera);
    const p = projector(camera);
    title('Reducir (alinear) la fractura', 'Aducir el miembro afectado de 10 a 15 grados.');
    const mid = p([hip[0] + 0.72, hip[1], hip[2] - Math.sin(a / 2) * 0.72]);
    callout(mid, 1060, 760, '10 a 15°', { color: C.orange, size: 42, anchor: 'end' });
    callout(p([hip[0] + 1.02, hip[1], hip[2]]), 1300, 620, ['Línea sin', 'aducción'], { color: C.muted, size: 28 });
    label(1400, 250, 'Lado sano', { color: C.muted, plate: true });
    label(1300, 790, 'Lado afectado', { plate: true, size: 28 });
    note();
  },
  '2-2-fijar-miembro'() {
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [2.2, 3.2, 2.2] });
    basePatient(scene, { rightAngle: 12, leftAngle: -14, strap: M.orange });
    const a = THREE.MathUtils.degToRad(12);
    const toWorld = (d, y) => [HIP_X + Math.cos(a) * d, BODY_Y + y, 0.1 - Math.sin(a) * d];
    const camera = perspective([2.05, 1.9, 2.05], [0.72, 1.02, 0.0], { fov: 30 });
    render(scene, camera);
    const p = projector(camera);
    title('Fijar el miembro a la mesa de tracción', 'El pie queda sujeto con la bota al brazo de tracción.');
    callout(p(toWorld(0.8, 0)), 170, 800, ['Correas de la bota'], { color: C.orange });
    callout(p(toWorld(1.0, -0.14)), 1120, 820, ['Brazo de tracción'], { color: C.white });
    note();
  },
  async '2-3-traccion'() {
    await loadFemur();
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [1, 3, 3], span: 1 , floorY: -2 });
    const toLeg = new THREE.Group();
    toLeg.rotation.set(0, 0, Math.PI / 2);
    // Eje del fémur en horizontal: proximal a la izquierda
    const upperClip = [new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.0)];
    const proximal = std(0xeadfca, 0.58, 0, { side: THREE.DoubleSide, clippingPlanes: [new THREE.Plane(new THREE.Vector3(-1, 0, 0), -0.05)] });
    const distal = std(0xeadfca, 0.58, 0, { side: THREE.DoubleSide, clippingPlanes: [new THREE.Plane(new THREE.Vector3(1, 0, 0), -0.05)] });
    const a = femur(proximal);
    const b = femur(distal);
    a.rotation.z = Math.PI / 2;
    b.rotation.z = Math.PI / 2;
    a.position.y = 0;
    b.position.y = 0;
    scene.add(a, b);
    void toLeg;
    void upperClip;
    const fragments = [[-0.03, 0.03, 0.01], [0.0, -0.022, 0.012], [0.03, 0.027, 0.0], [-0.01, 0.0, -0.022], [0.022, -0.012, -0.014]];
    fragments.forEach(([x, y, z], i) => {
      const piece = shadowed(new THREE.Mesh(new THREE.DodecahedronGeometry(0.0145 + i * 0.0012, 0), M.bone));
      piece.position.set(x, y, z);
      piece.scale.set(1.25, 0.8, 0.9);
      piece.rotation.set(i, i * 1.7, i * 0.6);
      scene.add(piece);
    });
    // Piel transparente alrededor
    const shell = loft([[-0.34, 0, 0, 0.1, 0.1], [-0.16, 0, 0, 0.098, 0.1], [0.02, 0, 0, 0.086, 0.09], [0.18, 0, 0, 0.07, 0.074], [0.32, 0, 0, 0.066, 0.07]], glass(0xe0ad8a, 0.28));
    shell.castShadow = false;
    scene.add(shell);
    const camera = perspective([0, 0.14, 0.92], [0, -0.01, 0], { fov: 34 });
    render(scene, camera);
    const p = projector(camera);
    title('Ajustar la tracción en una fractura conminuta', 'El miembro puede acortarse o alargarse.');
    callout(p([0.0, 0.03, 0.03]), 500, 800, ['Fractura conminuta:', 'varios fragmentos']);
    arrow2d(1140, 790, 1440, 790);
    label(1190, 850, 'Alargamiento', { size: 32, color: C.orange });
    arrow2d(1100, 790, 800, 790, C.white);
    label(830, 850, 'Acortamiento', { size: 32 });
    note();
  },
  // Revisión: el fémur tal como viene en el archivo (con sus normales originales), desde las cuatro caras.
  // Revisión: último cuadro de una animación, de frente (vista anterior del fémur), hueso transparente.
  async 'ver-pin'() {
    const params = new URLSearchParams(location.search);
    const gltf = await new GLTFLoader().parseAsync(await (await fetch(params.get('url'))).arrayBuffer(), '');
    const mixer = new THREE.AnimationMixer(gltf.scene);
    // Un archivo puede traer varias escenas (una por movimiento): se deja solo la del movimiento elegido.
    const clip = gltf.animations[Number(params.get('clip') || gltf.animations.length - 1)];
    const targets = new Set(clip.tracks.map((tr) => tr.name.split('.')[0]));
    const roots = gltf.scene.children.length === 1 && gltf.scene.children[0].children.length > 1 ? gltf.scene.children[0].children : gltf.scene.children;
    if (gltf.animations.length > 1) roots.forEach((root) => {
      let used = false;
      root.traverse((n) => { if (targets.has(n.name)) used = true; });
      root.visible = used;
    });
    mixer.clipAction(clip).play();
    mixer.setTime(Number(params.get('t') || clip.duration - 1e-3));
    gltf.scene.updateMatrixWorld(true);
    let femurNode = null;
    gltf.scene.traverseVisible((node) => {
      if (!node.isMesh) return;
      if (/^Femur/.test(node.name)) { femurNode = femurNode || node; node.material = boneGlass(0.28); }
      if (/^Canal_medular/.test(node.name)) node.material = new THREE.MeshStandardMaterial({ color: 0x4f8fd8, transparent: true, opacity: 0.45, depthWrite: false, side: THREE.DoubleSide });
      if (/Camara|Vista_/.test(node.name)) node.visible = false;
      // doble=1: como el visor del instructivo, las piezas opacas se dibujan por las dos caras.
      if (params.get('doble') && !/^Femur|^Canal_medular/.test(node.name)) {
        [node.material].flat().forEach((m) => { if (!m.transparent) m.side = THREE.DoubleSide; });
      }
      if (params.get('sin_canal') && /^Canal_medular/.test(node.name)) node.visible = false;
    });
    const q = new THREE.Quaternion(); femurNode.getWorldQuaternion(q);
    const S = new THREE.Vector3(0.0758, 0.992, 0.1006).normalize().applyQuaternion(q);
    const A = new THREE.Vector3(-0.3558, -0.0673, 0.9321).normalize().applyQuaternion(q);
    const Md = new THREE.Vector3(0.9315, -0.1065, 0.3479).normalize().applyQuaternion(q);
    // Encuadre: los 280 mm de arriba del hueso (donde va el pin).
    const box3 = new THREE.Box3().setFromObject(femurNode);
    let top = -Infinity; const topPoint = new THREE.Vector3();
    const v = new THREE.Vector3();
    gltf.scene.traverseVisible((node) => {
      if (!node.isMesh || !/^Femur/.test(node.name)) return;
      const pos = node.geometry.attributes.position;
      for (let i = 0; i < pos.count; i += 7) { v.fromBufferAttribute(pos, i).applyMatrix4(node.matrixWorld); if (v.dot(S) > top) { top = v.dot(S); topPoint.copy(v); } }
    });
    let c = topPoint.clone().addScaledVector(S, Number(params.get('alto') || -0.13));
    // foco=NombreDePieza: el encuadre se centra en esa pieza (para revisar detalles de cerca).
    const focusNode = params.get('foco') && gltf.scene.getObjectByName(params.get('foco'));
    if (focusNode) c = new THREE.Box3().setFromObject(focusNode).getCenter(new THREE.Vector3());
    // reves=1: las mismas vistas desde el lado contrario (posterior y externa).
    if (params.get('reves')) { A.negate(); Md.negate(); }
    const views = [['De frente (anterior)', A, S], ['De lado (interna)', Md, S]];
    views.forEach(([name, dir, up], i) => {
      const scene = new THREE.Scene();
      floorAndLights(scene, { key: [dir.x + 0.3, 1.5, dir.z + 0.3], span: 1, floorY: -2 });
      scene.add(gltf.scene.clone());
      const cam = new THREE.PerspectiveCamera(20, 800 / 1000, 0.01, 10);
      // mx, my: corren el encuadre (en metros) hacia la derecha y hacia arriba de cada vista, para revisar detalles.
      const right = new THREE.Vector3().crossVectors(up, dir).normalize();
      const look = c.clone().addScaledVector(right, Number(params.get('mx') || 0)).addScaledVector(up, Number(params.get('my') || 0));
      cam.position.copy(look).addScaledVector(dir, Number(params.get('dist') || 0.9));
      cam.up.copy(up);
      cam.lookAt(look);
      cam.updateMatrixWorld();
      render(scene, cam, { x: i * 800, y: 0, w: 800, h: 1000 });
      label(i * 800 + 24, 48, name, { size: 30, weight: 600 });
    });
  },
  async 'ver-femur'() {
    const content = await (await fetch('/api/content')).json();
    const params = new URLSearchParams(location.search);
    const asset = Object.values(content.assets).find((item) => item.filename.startsWith(params.get('archivo') || 'apertura'));
    const gltf = await new GLTFLoader().parseAsync(await (await fetch(params.get('url') || asset.url)).arrayBuffer(), '');
    gltf.scene.updateMatrixWorld(true);
    const bone = new THREE.Group();
    gltf.scene.traverse((node) => {
      if (node.isMesh && /^Femur/.test(node.name)) {
        const mesh = new THREE.Mesh(node.geometry.clone().applyMatrix4(node.matrixWorld), M.bone);
        bone.add(mesh);
      }
    });
    const box3 = new THREE.Box3().setFromObject(bone);
    const c = box3.getCenter(new THREE.Vector3());
    // Mismos ejes anatómicos que el visor (Engine3D.FEMUR_AXES).
    const S = new THREE.Vector3(0.0758, 0.992, 0.1006).normalize();
    const Md = new THREE.Vector3(0.9315, -0.1065, 0.3479).normalize();
    const A = new THREE.Vector3(-0.3558, -0.0673, 0.9321).normalize();
    const views = [['Anterior', A, S], ['Posterior', A.clone().negate(), S], ['Interna', Md, S], ['Superior', S, Md]];
    views.forEach(([name, dir, up], i) => {
      const scene = new THREE.Scene();
      floorAndLights(scene, { key: [dir.x + 0.3, 1.5, dir.z + 0.3], span: 1, floorY: -2 });
      scene.add(bone.clone());
      const cam = new THREE.PerspectiveCamera(22, 400 / 1000, 0.01, 10);
      cam.position.copy(c).addScaledVector(dir, 1.3);
      cam.up.copy(up);
      cam.lookAt(c);
      cam.updateMatrixWorld();
      render(scene, cam, { x: i * 400, y: 0, w: 400, h: 1000 });
      label(i * 400 + 20, 40, name, { size: 26, weight: 600 });
    });
  },
  async '3-1-angulo-cuello-diafisis'() {
    await loadFemur();
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [-1, 2, 3], span: 0.6, floorY: -2 });
    const group = femur(boneDouble(), { mirror: true });
    scene.add(group);
    // Hueso izquierdo (espejo): la cabeza queda hacia -x
    const corner = [-0.002, 0.162, 0.012];
    const head = [-0.042, 0.197, 0.02];
    const neckEnd = [corner[0] + (head[0] - corner[0]) * 1.25, corner[1] + (head[1] - corner[1]) * 1.25, 0.05];
    scene.add(tube([[corner[0], corner[1], 0.05], neckEnd], 0.0022, M.orange));
    scene.add(tube([[corner[0], corner[1], 0.05], [corner[0], 0.02, 0.05]], 0.0022, M.orange));
    const start = -Math.PI / 2;
    const end = Math.atan2(head[1] - corner[1], head[0] - corner[0]);
    const finish = end < 0 ? end : end - Math.PI * 2;
    const arcPoints = [];
    for (let i = 0; i <= 18; i += 1) {
      const b = start + (finish - start) * (i / 18);
      arcPoints.push([corner[0] + Math.cos(b) * 0.032, corner[1] + Math.sin(b) * 0.032, 0.05]);
    }
    scene.add(tube(arcPoints, 0.0018, M.orange));
    scene.add(ball(0.003, M.orange, [corner[0], corner[1], 0.05]));
    // Plantilla radiográfica: la ranura del ángulo queda sobre el eje del cuello (hueso izquierdo, por eso en espejo).
    await loadTemplate();
    const plantilla = radiographicTemplate({ mirror: true, opacity: 0.45 });
    plantilla.position.set(corner[0] + 0.0003, corner[1] - TEMPLATE.slotY, 0.046);
    scene.add(plantilla);
    const camera = perspective([0.0, 0.1, 0.62], [0.0, 0.135, 0], { fov: 34 });
    render(scene, camera);
    const p = projector(camera);
    title('Estimar el ángulo cuello-diáfisis', 'Con la regla ubicada en la pierna sana.');
    const mid = (start + finish) / 2;
    callout(p([corner[0] + Math.cos(mid) * 0.032, corner[1] + Math.sin(mid) * 0.032, 0.05]), 240, 470, ['Ángulo', 'cuello-diáfisis'], { color: C.orange, anchor: 'end', size: 32 });
    callout(p([corner[0] + TEMPLATE.halfWidth, corner[1] - 0.075, 0.048]), 1160, 650, 'Regla radiográfica', { color: C.orange });
    callout(p([0.02, 0.06, 0.02]), 1160, 480, ['Fémur de la', 'pierna sana']);
    note();
  },
  async '3-2-largo-del-clavo'() {
    await loadFemur();
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [1, 2, 3], span: 0.7, floorY: -2 });
    scene.add(femur(M.bone));
    // Plantilla frente al fémur: su parte proximal en el punto de entrada y la distal en la posición esperada.
    await loadTemplate();
    // Totalmente vertical, desde la punta del trocánter mayor hacia abajo. Se corre un poco hacia la
    // diáfisis para que cubra a la vez el trocánter (arriba) y el centro del hueso (abajo).
    const tipX = 0.008;
    const tipY = ENTRY.y - TEMPLATE.length;
    const plantilla = radiographicTemplate({ opacity: 0.5 });
    plantilla.position.set(tipX, tipY, 0.055);
    scene.add(plantilla);
    const edge = TEMPLATE.halfWidth;
    scene.add(ball(0.0055, M.orange, [tipX, ENTRY.y, 0.058]));
    scene.add(ball(0.0055, M.orange, [tipX, tipY, 0.058]));
    const camera = perspective([0.23, 0.0, 1.05], [0.15, 0, 0], { fov: 28 });
    render(scene, camera);
    const p = projector(camera);
    title('Leer la longitud del clavo', 'Regla frente al fémur.', 860);
    callout(p([tipX + edge, ENTRY.y - 0.004, 0.057]), 860, 290, ['Parte proximal:', 'en el punto de entrada'], { color: C.orange, size: 32 });
    callout(p([tipX + edge, (ENTRY.y + tipY) / 2, 0.057]), 860, 510, ['Regla radiográfica:', 'se lee la longitud del clavo'], { size: 32 });
    callout(p([tipX + edge, tipY + 0.004, 0.057]), 860, 760, ['Parte distal:', 'en la posición esperada'], { color: C.orange, size: 32 });
    note();
  },
  async '3-3-diametro-del-canal'() {
    await loadFemur();
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [1, 2, 3], span: 0.7, floorY: -2 });
    const shell = boneGlass(0.32);
    scene.add(femur(shell));
    scene.add(straightCanal());
    await loadTemplate();
    const level0 = 0.02;
    const plantillaA = radiographicTemplate({ opacity: 0.4 });
    plantillaA.position.set(-0.0005, level0 - TEMPLATE.bracket12Y, 0.04);
    scene.add(plantillaA);
    const left = { x: 40, y: 0, w: 560, h: 1000 };
    const overview = new THREE.PerspectiveCamera(30, left.w / left.h, 0.02, 10);
    overview.position.set(0.012, 0, 0.98);
    overview.lookAt(0.012, 0, 0);
    overview.updateMatrixWorld();
    renderer.setClearColor(NAVY, 1);
    render(scene, overview, left);
    // Detalle del hueso cortado por la mitad
    const clip = [new THREE.Plane(new THREE.Vector3(0, 0, -1), -0.0)];
    const scene2 = new THREE.Scene();
    floorAndLights(scene2, { key: [0.4, 1, 2.5], span: 0.2, floorY: -2 });
    scene2.add(femur(std(0xeadfca, 0.6, 0, { side: THREE.DoubleSide, clippingPlanes: clip })));
    scene2.add(straightCanal({ clippingPlanes: clip }));
    const level = 0.02;
    const plantillaB = radiographicTemplate({ opacity: 0.35 });
    plantillaB.position.set(-0.0005, level - TEMPLATE.bracket12Y, 0.03);
    scene2.add(plantillaB);
    // Paredes del canal = bordes del corchete de Φ12 mm (regla en x = -0,5 mm, corchete de ±6 mm).
    const leftWall = -0.0065;
    const rightWall = 0.0055;
    scene2.add(tube([[leftWall, level, 0.012], [rightWall, level, 0.012]], 0.0008, M.orange));
    for (const x of [leftWall, rightWall]) scene2.add(tube([[x, level - 0.0034, 0.012], [x, level + 0.0034, 0.012]], 0.0007, M.orange));
    const zoom = { x: 700, y: 240, w: 620, h: 620 };
    // Vista de frente sin perspectiva: la regla queda delante del canal y, con perspectiva, el canal se vería
    // más angosto que el corchete aunque midan lo mismo. Así las paredes coinciden con el corchete.
    const half = 0.21 * Math.tan(THREE.MathUtils.degToRad(13));
    const close = new THREE.OrthographicCamera(-half, half, half, -half, 0.01, 5);
    close.position.set(0, level, 0.21);
    close.lookAt(0, level, 0);
    close.updateMatrixWorld();
    render(scene2, close, zoom);
    const pz = projector(close, zoom);
    const po = projector(overview, left);
    const a = po([-0.024, level + 0.03, 0.01]);
    const b = po([0.026, level - 0.03, 0.01]);
    add('rect', { x: a[0], y: a[1], width: b[0] - a[0], height: b[1] - a[1], fill: 'none', stroke: C.orange, 'stroke-width': 4, rx: 6 });
    add('line', { x1: b[0], y1: a[1], x2: zoom.x, y2: zoom.y, stroke: C.orange, 'stroke-width': 2 });
    add('line', { x1: b[0], y1: b[1], x2: zoom.x, y2: zoom.y + zoom.h, stroke: C.orange, 'stroke-width': 2 });
    add('rect', { x: zoom.x, y: zoom.y, width: zoom.w, height: zoom.h, fill: 'none', stroke: C.line, 'stroke-width': 2, rx: 8 });
    title('Estimar el diámetro (Φ) del canal', null, 700);
    callout(pz([0.0085, level + 0.0068, 0.032]), 1345, 300, ['Corchete de la', 'regla (Φ12 mm)'], { color: C.orange, size: 28 });
    callout(pz([rightWall, level, 0.012]), 1345, 470, 'Diámetro (Φ)', { color: C.orange, size: 32 });
    callout(pz([-0.0005, level - 0.03, 0.005]), 1345, 690, ['Canal', 'intramedular'], { size: 28 });
    chip(700, 880, 'Diámetros disponibles: Φ9,4, Φ10, Φ11 o Φ12 mm');
    note();
  },
  async '3-4-clavo-principal-extendido'() {
    await loadFemur();
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [1, 2, 3], span: 1, floorY: -2 });
    const build = (offset, tipY, fractureY) => {
      const group = new THREE.Group();
      group.position.x = offset;
      group.add(femur(boneGlass(0.42)));
      group.add(tube([[ENTRY.x, ENTRY.y + 0.012, 0.0], [SHAFT_X - 0.002, 0.15, 0.0], [SHAFT_X, 0.09, 0.0], [SHAFT_X, tipY, 0.0]], 0.0052, M.nail));
      const zig = [];
      for (let i = 0; i <= 8; i += 1) {
        const x = -0.034 + (0.066 * i) / 8;
        zig.push([x, fractureY + (i % 2 ? 0.006 : -0.006) - (x + 0.034) * 0.25, 0.03]);
      }
      const path = new THREE.CatmullRomCurve3(zig.map((v) => new THREE.Vector3(...v)), false, 'catmullrom', 0.05);
      group.add(new THREE.Mesh(new THREE.TubeGeometry(path, 80, 0.0014, 8), M.red));
      group.add(rod([-0.075, LESSER_Y, 0.03], [0.085, LESSER_Y, 0.03], 0.0007, M.white));
      scene.add(group);
    };
    const a = -0.19;
    const b = 0.19;
    build(a, 0.03, 0.17);
    build(b, -0.17, 0.08);
    const camera = perspective([0, 0, 1.28], [0.02, 0, 0], { fov: 26 });
    render(scene, camera);
    const p = projector(camera);
    title('Elegir la longitud del clavo');
    const la = p([a + 0.09, LESSER_Y, 0.03]);
    const lb = p([b + 0.09, LESSER_Y, 0.03]);
    label(la[0], la[1] + 8, ['Trocánter', 'menor'], { size: 25, color: C.muted, plate: true });
    label(lb[0], lb[1] + 8, ['Trocánter', 'menor'], { size: 25, color: C.muted, plate: true });
    const na = p([a + 0.07, -0.03, 0]);
    const nb = p([b + 0.07, -0.03, 0]);
    label(na[0], na[1], ['Clavo', 'corto'], { size: 34, color: C.orange, weight: 600 });
    label(na[0], na[1] + 100, ['Si la línea de fractura', 'no baja del', 'trocánter menor'], { size: 25, weight: 400 });
    label(nb[0], nb[1], ['Clavo', 'largo'], { size: 34, color: C.orange, weight: 600 });
    label(nb[0], nb[1] + 100, ['Se usa si la línea', 'de fractura baja', 'del trocánter menor'], { size: 25, weight: 400 });
    note();
  },
  async '4-1-incision'() {
    await loadFemur();
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [0.4, 2, 2.4], span: 0.8, floorY: -2 });
    // Cadera y muslo vistos desde afuera: proximal a la izquierda, anterior arriba
    const holder = new THREE.Group();
    const matrix = new THREE.Matrix4().set(0, -1, 0, 0, 0, 0, 1, 0, -1, 0, 0, 0, 0, 0, 0, 1);
    holder.applyMatrix4(matrix);
    holder.add(femur(M.bone));
    scene.add(holder);
    const vertex = new THREE.Vector3(-0.03, 0.214, -0.016).applyMatrix4(matrix);
    const skinZ = vertex.z + 0.052;
    const skin = loft([
      [vertex.x - 0.34, vertex.y - 0.002, 0, 0.16, 0.13],
      [vertex.x - 0.16, vertex.y - 0.002, 0, 0.18, 0.15],
      [vertex.x, vertex.y - 0.002, 0, 0.175, 0.145],
      [vertex.x + 0.14, vertex.y - 0.003, 0, 0.14, 0.125],
      [vertex.x + 0.32, vertex.y - 0.003, 0, 0.11, 0.1],
      [vertex.x + 0.46, vertex.y - 0.003, 0, 0.09, 0.08],
    ], new THREE.MeshPhysicalMaterial({ color: 0xe8b592, roughness: 0.5, transparent: true, opacity: 0.5, depthWrite: false, side: THREE.FrontSide, emissive: 0x5a3020, emissiveIntensity: 0.25 }));
    skin.castShadow = false;
    scene.add(skin);
    const start = [vertex.x, vertex.y, skinZ + 0.135];
    const end = [vertex.x - 0.055, vertex.y, skinZ + 0.135];
    const cut = tube([start, end], 0.0034, M.orange);
    scene.add(cut);
    scene.add(ball(0.006, M.white, vertex.toArray()));
    const camera = perspective([vertex.x + 0.075, vertex.y + 0.015, 0.92], [vertex.x + 0.075, vertex.y - 0.01, 0], { fov: 34 });
    render(scene, camera);
    const p = projector(camera);
    title('Asistir la incisión','De 5 a 6 cm en dirección proximal, a partir del vértice del trocánter mayor.');
    const s = p(start);
    const e = p(end);
    add('line', { x1: e[0], y1: s[1] + 46, x2: s[0], y2: s[1] + 46, stroke: C.white, 'stroke-width': 3 });
    add('line', { x1: e[0], y1: s[1] + 34, x2: e[0], y2: s[1] + 58, stroke: C.white, 'stroke-width': 3 });
    add('line', { x1: s[0], y1: s[1] + 34, x2: s[0], y2: s[1] + 58, stroke: C.white, 'stroke-width': 3 });
    label((s[0] + e[0]) / 2, s[1] + 98, '5 a 6 cm', { size: 38, weight: 600, anchor: 'middle', plate: true });
    callout([(s[0] + e[0]) / 2, s[1]], 280, 330, 'Incisión', { color: C.orange, anchor: 'end', size: 34 });
    callout(p(vertex), 1020, 860, 'Vértice del trocánter mayor', { size: 32 });
    arrow2d(290, 870, 90, 870, C.white, 5);
    label(310, 882, 'Hacia proximal (la cabeza)', { weight: 400 });
    note();
  },
  async '4-2-punto-de-entrada'() {
    await loadFemur();
    // Punto de entrada como en AO: de frente en la punta del trocánter mayor; desde arriba, en la mitad entre
    // sus bordes anterior y posterior, en línea con el canal (el mismo punto que usan las animaciones).
    const point = new THREE.Vector3(-0.0055, 0.2133, -0.0129);
    const scene = new THREE.Scene();
    floorAndLights(scene, { key: [0.6, 2, 2], span: 0.5, floorY: -2 });
    scene.add(femur(M.bone));
    const entryBall = ball(0.0058, M.orange, point.toArray());   // solo en la vista de frente
    const front = { x: 40, y: 200, w: 660, h: 730 };

    // Vista superior como la de Kangli: cabeza justo arriba del trocánter (el cuello vertical en la imagen), tres
    // líneas paralelas a ese eje: borde anterior, borde posterior y la del tercio anterior (1/3 adelante, 2/3 atrás).
    const top = { x: 780, y: 200, w: 780, h: 730 };
    const SUP = new THREE.Vector3(0.0758, 0.992, 0.1006).normalize();
    const ANT = new THREE.Vector3(-0.3558, -0.0673, 0.9321).normalize();
    const HEAD = new THREE.Vector3(0.0429, 0.1977, 0.0245);
    const upTop = HEAD.clone().sub(point).projectOnPlane(SUP).normalize();
    const focus = point.clone().lerp(HEAD, 0.5);
    const camTop = new THREE.PerspectiveCamera(16, top.w / top.h, 0.02, 10);
    camTop.position.copy(focus).addScaledVector(SUP, 0.5);
    camTop.up.copy(upTop);
    camTop.lookAt(focus);
    camTop.updateMatrixWorld();
    render(scene, camTop, top);
    // De frente: la vista anterior del visor (cabeza a la derecha, eje mecánico vertical).
    const frontFocus = new THREE.Vector3(0.006, 0.165, 0.004);
    const camFront = new THREE.PerspectiveCamera(22, front.w / front.h, 0.02, 10);
    camFront.position.copy(frontFocus).addScaledVector(ANT, 0.52);
    camFront.up.copy(SUP);
    camFront.lookAt(frontFocus);
    camFront.updateMatrixWorld();
    scene.add(entryBall);
    render(scene, camFront, front);
    const pf = projector(camFront, front);
    const pt = projector(camTop, top);
    // Silueta vista desde arriba (parte alta del fémur): bordes izquierdo y derecho en la imagen.
    let xMin = Infinity, xMax = -Infinity;
    const v = new THREE.Vector3();
    femurGeometries.forEach((g) => {
      const pos = g.attributes.position;
      for (let i = 0; i < pos.count; i += 3) {
        v.fromBufferAttribute(pos, i);
        if (v.clone().sub(point).dot(SUP) < -0.09) continue;
        const [x] = pt(v.toArray());
        xMin = Math.min(xMin, x); xMax = Math.max(xMax, x);
      }
    });
    const antRight = pt(point.clone().addScaledVector(ANT, 0.02).toArray())[0] > pt(point.toArray())[0];
    const xFront = antRight ? xMax : xMin, xBack = antRight ? xMin : xMax;
    const xThird = xFront + (xBack - xFront) / 3;
    const [ex, ey] = pt(point.toArray());
    window.TERCIO = ((ex - xFront) / (xBack - xFront)).toFixed(3);   // dónde cae la entrada (0 adelante, 1 atrás)
    const yTop = top.y + 70, yBottom = top.y + top.h - 20;
    const vline = (x, w) => add('line', { x1: x, y1: yTop, x2: x, y2: yBottom, stroke: C.orange, 'stroke-width': w, 'stroke-linecap': 'round' });
    vline(xFront, 4); vline(xBack, 4); vline(xThird, 4);
    const arrowRow = yTop + 22;
    const span = (x1, x2, text) => {
      add('line', { x1: x1 + 6, y1: arrowRow, x2: x2 - 6, y2: arrowRow, stroke: C.orange, 'stroke-width': 3 });
      [[x1 + 6, 1], [x2 - 6, -1]].forEach(([x, d]) => add('path', { d: `M${x + 12 * d} ${arrowRow - 7}L${x} ${arrowRow}L${x + 12 * d} ${arrowRow + 7}`, fill: 'none', stroke: C.orange, 'stroke-width': 3 }));
      label((x1 + x2) / 2, arrowRow - 12, text, { size: 26, color: C.orange, weight: 600, anchor: 'middle' });
    };
    const [l1, r1] = [Math.min(xFront, xThird), Math.max(xFront, xThird)];
    const [l2, r2] = [Math.min(xThird, xBack), Math.max(xThird, xBack)];
    span(l1, r1, '1/3'); span(l2, r2, '2/3');
    add('circle', { cx: xThird, cy: ey, r: 12, fill: C.orange, stroke: C.white, 'stroke-width': 3 });
    title('Ubicar el punto de entrada', 'De frente, en la punta del trocánter mayor; desde arriba, en el tercio anterior.');
    label(72, 240, 'De frente', { size: 34, weight: 600 });
    label(830, 240, 'Superior', { size: 34, weight: 600 });
    callout(pf(point.toArray()), 250, 330, ['Punta del', 'trocánter', 'mayor'], { color: C.orange, anchor: 'end', size: 28 });
    label(xFront + (antRight ? 14 : -14), yBottom - 40, 'Anterior', { size: 28, anchor: antRight ? 'start' : 'end', plate: true });
    label(xBack + (antRight ? -14 : 14), yBottom - 40, 'Posterior', { size: 28, anchor: antRight ? 'end' : 'start', plate: true });
    callout([xThird, ey], antRight ? xFront + 40 : xFront - 40, ey - 90, ['Punto de', 'entrada'], { color: C.orange, anchor: antRight ? 'start' : 'end', size: 28 });
    note();
  },
};

async function main() {
  const name = new URLSearchParams(location.search).get('escena');
  resetLabels();
  try {
    await document.fonts.ready;
    await ESCENAS[name]();
    document.title = 'listo';
  } catch (error) {
    console.error(error);
    document.title = `error: ${error.message}`;
    label(40, 60, `Error: ${error.message}`, { color: '#ff6666' });
  }
}

main();
