// Cuentas y roles.
import { h, confirmDialog, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { state } from '../core/store.js';
import { icon } from '../components/icons.js';
import { adminView, guarded } from './shell.js';

export function usersView() {
  return adminView('/admin/usuarios', 'Usuarios', async ({ refresh }) => {
    const { users } = await api('GET', '/api/admin/users');
    const error = h('p', { class: 'form-error is-wide', role: 'alert', hidden: true });

    return h('div', {},
      h('div', { class: 'admin-title-row' },
        h('div', {},
          h('h1', { class: 'page-title' }, 'Usuarios'),
          h('p', { class: 'page-sub' }, 'Administrador edita y publica. Consulta estudia el instructivo y guarda su avance.'),
        ),
      ),
      h('section', { class: 'panel' },
        h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
          h('thead', {}, h('tr', {},
            h('th', {}, 'Nombre'),
            h('th', {}, 'Correo'),
            h('th', {}, 'Rol'),
            h('th', {}, h('span', { class: 'sr-only' }, 'Acciones')),
          )),
          h('tbody', {}, users.map((user) => h('tr', {},
            h('td', { class: 'is-name' }, user.name),
            h('td', { style: 'overflow-wrap:anywhere' }, user.email),
            h('td', {}, user.role === 'admin' ? 'Administrador' : 'Consulta'),
            h('td', { class: 'is-actions' }, user.id === state.user.id
              ? 'Tu cuenta'
              : h('button', {
                  class: 'btn btn-danger',
                  type: 'button',
                  onClick: async () => {
                    const ok = await confirmDialog({ title: 'Eliminar la cuenta', message: `Se eliminará la cuenta de ${user.name} y su avance.`, confirm: 'Eliminar', danger: true });
                    if (ok) await guarded(async () => { await api('DELETE', `/api/admin/users/${user.id}`); await refresh(); }, 'Cuenta eliminada.')();
                  },
                }, 'Eliminar')),
          ))),
        )),
        h('form', {
          class: 'inline-form',
          style: 'margin:0 var(--card-pad) var(--card-pad)',
          onSubmit: async (event) => {
            event.preventDefault();
            const data = Object.fromEntries(new FormData(event.target));
            error.hidden = true;
            try {
              await api('POST', '/api/admin/users', data);
              toast('Cuenta creada.');
              await refresh();
            } catch (failure) {
              error.textContent = failure.message;
              error.hidden = false;
            }
          },
        },
          h('div', { class: 'field' }, h('label', { for: 'u-name' }, 'Nombre'), h('input', { class: 'input', id: 'u-name', name: 'name', required: true })),
          h('div', { class: 'field' }, h('label', { for: 'u-email' }, 'Correo'), h('input', { class: 'input', id: 'u-email', name: 'email', type: 'email', required: true })),
          h('div', { class: 'field' }, h('label', { for: 'u-role' }, 'Rol'), h('select', { class: 'select', id: 'u-role', name: 'role' },
            h('option', { value: 'consulta' }, 'Consulta'),
            h('option', { value: 'admin' }, 'Administrador'),
          )),
          h('div', { class: 'field' }, h('label', { for: 'u-pass' }, 'Contraseña inicial (mínimo 10 caracteres)'), h('input', { class: 'input', id: 'u-pass', name: 'password', type: 'password', autocomplete: 'new-password', minlength: 10, required: true })),
          error,
          h('div', { class: 'inline-actions' }, h('button', { class: 'btn', type: 'submit' }, icon('plus'), 'Crear la cuenta')),
        ),
      ),
    );
  });
}
