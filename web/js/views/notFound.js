import { h } from '../core/dom.js';
import { layout, setTitle } from '../components/shell.js';

export function notFoundView() {
  setTitle('Página no encontrada');
  return layout('',
    h('main', { class: 'page' },
      h('h1', { class: 'page-title' }, 'Esta página no existe'),
      h('p', { class: 'page-sub' }, 'Puede que el paso se haya movido o eliminado.'),
      h('p', { style: 'margin-top:16px' }, h('a', { class: 'btn', href: '/' }, 'Volver al instructivo')),
    ),
  );
}
