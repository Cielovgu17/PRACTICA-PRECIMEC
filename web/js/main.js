// Arranque de la aplicación y mapa de rutas.
import { h } from './core/dom.js';
import { addRoute, setNotFound, startRouter } from './core/router.js';
import { loadContent, loadSession, state } from './core/store.js';
import { instructivoView } from './views/instructivo.js';
import { loginView, profileView } from './views/account.js';
import { notFoundView } from './views/notFound.js';
import { layout } from './components/shell.js';
import { requireAdmin } from './admin/shell.js';
import { structureView } from './admin/structure.js';
import { stepEditorView } from './admin/stepEditor.js';
import { adminInstrumentsView, instrumentEditorView } from './admin/instruments.js';
import { filesView } from './admin/files.js';
import { generalView } from './admin/general.js';
import { usersView } from './admin/users.js';

const PREVIEW_KEY = 'precimec-vista-previa';

function readPreview() {
  try { return sessionStorage.getItem(PREVIEW_KEY) === '1'; } catch { return false; }
}

function writePreview(on) {
  try {
    if (on) sessionStorage.setItem(PREVIEW_KEY, '1');
    else sessionStorage.removeItem(PREVIEW_KEY);
  } catch { /* la vista previa dura hasta recargar */ }
}

export async function enterPreview() {
  writePreview(true);
  state.preview = true;
  await loadContent();
}

export async function exitPreview() {
  writePreview(false);
  state.preview = false;
  await loadContent();
}

// Lo que se edita en el administrador se ve al volver sin tener que recargar.
const learner = (view) => async (...args) => {
  if (state.editing) {
    state.editing = false;
    state.preview = readPreview() && state.user?.role === 'admin';
  }
  await loadContent();
  return view(...args);
};

// El modo edición trabaja sobre el borrador y exige la cuenta de administrador.
const editor = (view) => async (...args) => {
  if (!requireAdmin()) return null;
  state.editing = true;
  state.preview = true;
  await loadContent();
  return view(...args);
};

// La copia publicada en internet (exportar.py) es solo para ver: allí no hay edición.
function readOnlyNotice() {
  return layout('',
    h('main', { class: 'page' },
      h('h1', { class: 'page-title' }, 'Esta versión es solo para consulta'),
      h('p', { class: 'page-sub' }, 'El instructivo se edita en el computador de quien lo administra y luego se vuelve a publicar.'),
      h('p', { style: 'margin-top:16px' }, h('a', { class: 'btn', href: '/' }, 'Ir al instructivo')),
    ),
  );
}
const managed = (view) => (...args) => (state.readOnly ? readOnlyNotice() : view(...args));

addRoute('/', learner(instructivoView));
addRoute('/paso/:id', learner(instructivoView));
addRoute('/editar', managed(editor(instructivoView)));
addRoute('/editar/paso/:id', managed(editor(instructivoView)));
addRoute('/ingresar', managed(loginView));
addRoute('/perfil', managed(learner(profileView)));
addRoute('/admin', managed(structureView));
addRoute('/admin/paso/:id', managed(stepEditorView));
addRoute('/admin/instrumental', managed(adminInstrumentsView));
addRoute('/admin/instrumental/:id', managed(instrumentEditorView));
addRoute('/admin/archivos', managed(filesView));
addRoute('/admin/general', managed(generalView));
addRoute('/admin/usuarios', managed(usersView));
setNotFound(notFoundView);

async function boot() {
  const root = document.getElementById('app');
  try {
    await loadSession();
    state.preview = readPreview() && state.user?.role === 'admin';
    await loadContent();
    await startRouter(root);
  } catch (error) {
    console.error(error);
    root.replaceChildren(h('div', { class: 'notice-error', role: 'alert' },
      h('p', {}, error.message || 'No se pudo cargar el instructivo.'),
      h('button', { class: 'btn', type: 'button', onClick: () => location.reload() }, 'Reintentar'),
    ));
  }
}

boot();
