// Estado de la aplicación: sesión, contenido y progreso.
import { api } from './api.js';

const LOCAL_KEY = 'precimec-progreso';

export const state = {
  user: null,
  doc: null,
  preview: false,
  editing: false,
  readOnly: false, // copia publicada en internet, sin edición
  done: new Set(),
  lastStepId: null,
};

function readLocal() {
  try {
    const saved = JSON.parse(localStorage.getItem(LOCAL_KEY) || '{}');
    return { done: Array.isArray(saved.done) ? saved.done : [], last: saved.last ?? null };
  } catch {
    return { done: [], last: null };
  }
}

function writeLocal() {
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify({ done: [...state.done], last: state.lastStepId }));
  } catch { /* sin almacenamiento local: el progreso dura solo esta visita */ }
}

export async function loadSession() {
  const me = await api('GET', '/api/me');
  state.user = me.user;
  state.readOnly = Boolean(me.read_only);
  await loadProgress();
}

export async function loadProgress() {
  const local = readLocal();
  state.done = new Set(local.done);
  state.lastStepId = local.last;
  if (!state.user) return;
  // Al iniciar sesión se conserva lo que la persona ya había avanzado en este navegador.
  const remote = await api('GET', '/api/progress');
  remote.done.forEach((id) => state.done.add(id));
  state.lastStepId = remote.last_step_id ?? state.lastStepId;
  if (local.done.length) saveProgress();
}

export async function loadContent() {
  state.doc = await api('GET', state.preview ? '/api/content?version=draft' : '/api/content');
  return state.doc;
}

let saveTimer;
function saveProgress() {
  if (state.preview) return;
  writeLocal();
  if (!state.user) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    api('PUT', '/api/progress', { done: [...state.done], last_step_id: state.lastStepId }).catch(() => {});
  }, 300);
}

export function setCurrent(stepId) {
  if (state.lastStepId === stepId) return;
  state.lastStepId = stepId;
  saveProgress();
}

export function setDone(stepId, value) {
  if (value) state.done.add(stepId);
  else state.done.delete(stepId);
  saveProgress();
}

// La secuencia de pantallas: cada paso seguido de sus subpasos, con su numeración.
export function pages(doc = state.doc) {
  const list = [];
  doc.steps.forEach((step, i) => {
    const number = `${i + 1}`;
    list.push({ step, number, parent: null, isLeaf: step.children.length === 0 });
    step.children.forEach((child, j) => {
      list.push({ step: child, number: `${number}.${j + 1}`, parent: step, isLeaf: true });
    });
  });
  return list;
}

export function findPage(stepId) {
  return pages().find((page) => page.step.id === stepId) || null;
}

// El avance se cuenta sobre las pantallas finales; un paso con subpasos se completa con ellos.
export function progress() {
  const leaves = pages().filter((page) => page.isLeaf);
  const done = leaves.filter((page) => state.done.has(page.step.id)).length;
  return { done, total: leaves.length, percent: leaves.length ? Math.round((done / leaves.length) * 100) : 0 };
}

export function isComplete(step) {
  if (step.children.length) return step.children.every((child) => state.done.has(child.id));
  return state.done.has(step.id);
}

export function resumePage() {
  const all = pages();
  const last = all.find((page) => page.step.id === state.lastStepId);
  if (last) return last;
  return all.find((page) => page.isLeaf && !state.done.has(page.step.id)) || all[0] || null;
}

export function assetOf(id) {
  return id ? state.doc.assets[String(id)] || null : null;
}

export function instrumentSteps(instrumentId) {
  return pages().filter((page) => page.step.instrument_ids.includes(instrumentId));
}
