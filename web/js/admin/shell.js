// Marco del administrador: control de acceso, secciones, estado del borrador y publicación.
import { h, confirmDialog, formatDate, replace, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { navigate } from '../core/router.js';
import { state } from '../core/store.js';
import { icon } from '../components/icons.js';
import { errorBlock, layout, setTitle } from '../components/shell.js';

const SECTIONS = [
  ['/admin', 'Pasos y subpasos', 'list'],
  ['/admin/instrumental', 'Instrumental', 'tool'],
  ['/admin/archivos', 'Modelos y archivos', 'cube'],
  ['/admin/general', 'Información general', 'gear'],
  ['/admin/usuarios', 'Usuarios', 'users'],
];

export function requireAdmin() {
  if (state.user?.role === 'admin') return true;
  const next = encodeURIComponent(location.pathname);
  if (state.user) {
    // Con la cuenta de consulta no se puede editar: se cierra esa sesión y se pide la de administración.
    api('POST', '/api/logout').catch(() => {});
    state.user = null;
    toast('Esa cuenta no puede editar. Ingresa con la cuenta de administración.', true);
  }
  navigate(`/ingresar?siguiente=${next}`, { replace: true });
  return false;
}

export function refreshDraft() {
  return api('GET', '/api/admin/draft');
}

function statusBar(status) {
  const holder = h('div', { class: 'admin-status', role: 'status' });

  function paint(current) {
    replace(holder,
      h('div', { class: 'admin-status-text' },
        h('span', { class: `admin-dot${current.has_changes ? ' is-dirty' : ''}` }),
        current.has_changes
          ? `Hay cambios guardados en el borrador, sin publicar. Última publicación: ${formatDate(current.published_at)}`
          : `Todo está publicado. Última publicación: ${formatDate(current.published_at)}`,
      ),
      h('a', { class: 'btn', href: '/', onClick: startPreview }, icon('eye'), 'Previsualizar'),
      h('button', { class: 'btn btn-primary', type: 'button', disabled: !current.has_changes, onClick: publish }, 'Publicar'),
    );
  }

  async function startPreview(event) {
    event.preventDefault();
    event.stopPropagation();
    const { enterPreview } = await import('../main.js');
    await enterPreview();
    navigate('/');
  }

  async function publish() {
    const ok = await confirmDialog({
      title: 'Publicar los cambios',
      message: 'Todas las personas que consultan el instructivo verán esta versión del borrador.',
      confirm: 'Publicar',
    });
    if (!ok) return;
    try {
      paint(await api('POST', '/api/admin/publish'));
      toast('Cambios publicados.');
    } catch (error) {
      toast(error.message, true);
    }
  }

  paint(status);
  holder.update = async () => paint((await refreshDraft()).status);
  return holder;
}

// Crea la vista: render recibe el borrador y una función para recargarlo tras cada cambio.
export async function adminView(active, title, render) {
  if (!requireAdmin()) return null;
  setTitle(title);
  const canvas = h('div', { class: 'admin-canvas' });
  let bar;

  async function reload() {
    const { document: doc, status } = await refreshDraft();
    if (bar) bar.update();
    return { doc, status };
  }

  async function paint() {
    try {
      const { doc } = await reload();
      const node = await render({ doc, refresh: paint });
      replace(canvas, node);
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        state.user = null;
        requireAdmin();
        return;
      }
      replace(canvas, errorBlock(error.message, paint));
    }
  }

  let first;
  try {
    first = await refreshDraft();
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      state.user = null;
      requireAdmin();
      return null;
    }
    return layout('admin', errorBlock(error.message));
  }
  bar = statusBar(first.status);
  replace(canvas, await render({ doc: first.document, refresh: paint }));

  return layout('admin',
    h('div', { class: 'admin' },
      h('nav', { class: 'admin-nav', 'aria-label': 'Secciones del administrador' },
        SECTIONS.map(([href, label, name]) => h('a', { href, 'aria-current': active === href ? 'page' : null, title: label }, icon(name), h('span', {}, label))),
      ),
      h('main', { class: 'admin-main' }, bar, canvas),
    ),
  );
}

export function guarded(action, success) {
  return async (...args) => {
    try {
      const result = await action(...args);
      if (success) toast(success);
      return result;
    } catch (error) {
      toast(error.message, true);
      return undefined;
    }
  };
}
