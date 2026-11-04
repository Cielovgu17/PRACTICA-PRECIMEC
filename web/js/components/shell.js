// Barra superior y aviso de vista previa. El instructivo va dentro del LMS: quien consulta no ve menús.
import { h } from '../core/dom.js';
import { api } from '../core/api.js';
import { navigate } from '../core/router.js';
import { loadProgress, state } from '../core/store.js';
import { icon } from './icons.js';

function adminLinks(active) {
  return h('nav', { class: 'topbar-admin', 'aria-label': 'Cuenta' },
    h('a', { class: 'btn', href: '/' }, icon('eye'), h('span', {}, 'Ver el instructivo')),
    h('a', { class: 'btn', href: '/editar' }, icon('edit'), h('span', {}, 'Modo edición')),
    h('a', { class: 'btn', href: '/perfil', 'aria-current': active === 'perfil' ? 'page' : null }, icon('user'), h('span', {}, 'Mi cuenta')),
    h('button', {
      class: 'btn',
      type: 'button',
      onClick: async () => {
        await api('POST', '/api/logout');
        state.user = null;
        await loadProgress();
        navigate('/');
      },
    }, 'Salir'),
  );
}

export function topbar(active) {
  const doc = state.doc;
  const isManaging = active === 'admin' || active === 'perfil';
  const title = isManaging ? 'Administrador' : `Técnica quirúrgica: ${doc?.technique.name || ''}`;
  return [
    h('header', { class: 'topbar' },
      // Sin logotipo: la barra lleva solo el nombre de la técnica.
      active === 'instructivo'
        ? h('h1', { class: 'topbar-title', id: 'titulo-tecnica' }, title)
        : h('p', { class: 'topbar-title' }, title),
      isManaging && adminLinks(active),
      // Quien consulta no ve este botón; se entra por la dirección /editar.
      active === 'instructivo' && !state.preview && state.user?.role === 'admin' && h('a', { class: 'btn topbar-edit', href: '/editar' }, icon('edit'), 'Modo edición'),
    ),
    state.preview && !state.editing && h('div', { class: 'preview-banner', role: 'status' },
      h('span', {}, 'Vista previa del borrador. Quienes consultan aún no ven estos cambios.'),
      h('a', {
        href: '/admin',
        onClick: async (event) => {
          event.preventDefault();
          event.stopPropagation();
          const { exitPreview } = await import('../main.js');
          await exitPreview();
          navigate('/admin');
        },
      }, 'Salir de la vista previa'),
    ),
  ].filter(Boolean);
}

export function pill(text, kind = 'neutral') {
  return h('span', { class: `pill pill-${kind}` }, text);
}

export const SAMPLE = 'Por validar';

export function errorBlock(message, onRetry) {
  return h('div', { class: 'notice-error', role: 'alert' },
    h('p', {}, message),
    onRetry && h('button', { class: 'btn btn-text', type: 'button', onClick: onRetry }, 'Reintentar'),
  );
}

export function layout(active, ...content) {
  document.getElementById('app').classList.remove('is-learning');
  return [...topbar(active), ...content.flat().filter(Boolean)];
}

export function setTitle(text) {
  const technique = `Técnica quirúrgica: ${state.doc?.technique.name || 'Instructivo'}`;
  document.title = text ? `${text} · ${technique}` : technique;
}
