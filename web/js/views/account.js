// Ingreso al administrador y cuenta. Quien consulta el instructivo no necesita ingresar.
import { h, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { navigate } from '../core/router.js';
import { loadProgress, state } from '../core/store.js';
import { layout, setTitle } from '../components/shell.js';

export function loginView() {
  setTitle('Ingresar');
  const params = new URLSearchParams(location.search);
  const nextPath = params.get('siguiente');
  const safeNext = nextPath && nextPath.startsWith('/') && !nextPath.startsWith('//') ? nextPath : null;
  if (state.user) {
    navigate(safeNext || (state.user.role === 'admin' ? '/admin' : '/'), { replace: true });
    return null;
  }
  const error = h('p', { class: 'form-error', role: 'alert', hidden: true });
  const submit = h('button', { class: 'btn btn-primary btn-large', type: 'submit' }, 'Ingresar');

  async function onSubmit(event) {
    event.preventDefault();
    const data = new FormData(event.target);
    submit.disabled = true;
    error.hidden = true;
    try {
      const { user } = await api('POST', '/api/login', { email: data.get('email'), password: data.get('password') });
      state.user = user;
      await loadProgress();
      navigate(safeNext || (user.role === 'admin' ? '/admin' : '/'), { replace: true });
    } catch (failure) {
      error.textContent = failure.message;
      error.hidden = false;
      submit.disabled = false;
    }
  }

  return layout('',
    h('main', { class: 'auth' },
      h('form', { class: 'panel auth-card', onSubmit },
        h('h1', {}, 'Ingresar al administrador'),
        h('p', {}, 'Solo para quienes editan el contenido del instructivo. Usa la cuenta de administración (admin@precimec.local).'),
        h('div', { class: 'field' }, h('label', { for: 'email' }, 'Correo'), h('input', { class: 'input', id: 'email', name: 'email', type: 'email', autocomplete: 'username', required: true })),
        h('div', { class: 'field' }, h('label', { for: 'password' }, 'Contraseña'), h('input', { class: 'input', id: 'password', name: 'password', type: 'password', autocomplete: 'current-password', required: true })),
        error,
        submit,
      ),
    ),
  );
}

export function profileView() {
  if (!state.user) {
    navigate('/ingresar?siguiente=/perfil', { replace: true });
    return null;
  }
  setTitle('Mi cuenta');
  const message = h('p', { class: 'form-error', role: 'alert', hidden: true });

  async function changePassword(event) {
    event.preventDefault();
    const form = event.target;
    const data = new FormData(form);
    message.hidden = true;
    try {
      await api('POST', '/api/me/password', { current: data.get('current'), new: data.get('new') });
      form.reset();
      toast('Contraseña actualizada.');
    } catch (failure) {
      message.textContent = failure.message;
      message.hidden = false;
    }
  }

  return layout('perfil',
    h('main', { class: 'page' },
      h('h1', { class: 'page-title' }, 'Mi cuenta'),
      h('div', { class: 'profile-grid' },
        h('section', { class: 'panel', 'aria-labelledby': 'cuenta' },
          h('div', { class: 'panel-head' }, h('h2', { id: 'cuenta' }, 'Cuenta')),
          h('div', { class: 'panel-body stack' },
            h('dl', { class: 'keyval' },
              h('dt', {}, 'Nombre'), h('dd', {}, state.user.name),
              h('dt', {}, 'Correo'), h('dd', {}, state.user.email),
              h('dt', {}, 'Rol'), h('dd', {}, state.user.role === 'admin' ? 'Administrador' : 'Consulta'),
            ),
            state.user.role === 'admin' && h('div', {}, h('a', { class: 'btn', href: '/admin' }, 'Volver al administrador')),
          ),
        ),
        h('section', { class: 'panel', 'aria-labelledby': 'clave' },
          h('div', { class: 'panel-head' }, h('h2', { id: 'clave' }, 'Cambiar la contraseña')),
          h('form', { class: 'panel-body stack', onSubmit: changePassword },
            h('div', { class: 'field' }, h('label', { for: 'current' }, 'Contraseña actual'), h('input', { class: 'input', id: 'current', name: 'current', type: 'password', autocomplete: 'current-password', required: true })),
            h('div', { class: 'field' }, h('label', { for: 'new' }, 'Contraseña nueva'), h('input', { class: 'input', id: 'new', name: 'new', type: 'password', autocomplete: 'new-password', minlength: 10, required: true }), h('span', { class: 'field-hint' }, 'Mínimo 10 caracteres.')),
            message,
            h('div', {}, h('button', { class: 'btn btn-primary', type: 'submit' }, 'Guardar la contraseña')),
          ),
        ),
      ),
    ),
  );
}
