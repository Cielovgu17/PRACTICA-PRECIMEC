// Construcción del DOM sin plantillas de texto: el contenido siempre entra como texto, nunca como HTML.
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'value') el.value = value;
    else if (key === 'checked' || key === 'disabled' || key === 'selected') el[key] = value;
    else el.setAttribute(key, value === true ? '' : value);
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === undefined || child === null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function replace(el, ...children) {
  el.replaceChildren();
  append(el, children);
}

let toastTimer;
export function toast(message, isError = false) {
  const el = document.getElementById('toast');
  // Los errores se anuncian de inmediato; los avisos normales, cuando el lector termina de hablar.
  el.setAttribute('role', isError ? 'alert' : 'status');
  el.textContent = message;
  el.classList.toggle('is-error', isError);
  el.classList.add('is-visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('is-visible'), isError ? 5000 : 2600);
}

export function confirmDialog({ title, message, confirm = 'Confirmar', danger = false }) {
  return new Promise((resolve) => {
    const dialog = h('dialog', { class: 'dialog' },
      h('h2', {}, title),
      h('p', {}, message),
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn', type: 'button', onClick: () => dialog.close('no') }, 'Cancelar'),
        h('button', { class: `btn ${danger ? 'btn-danger' : 'btn-primary'}`, type: 'button', onClick: () => dialog.close('si') }, confirm),
      ),
    );
    dialog.addEventListener('close', () => {
      dialog.remove();
      resolve(dialog.returnValue === 'si');
    });
    document.body.append(dialog);
    dialog.showModal();
  });
}

export function formatBytes(size) {
  if (size >= 1024 ** 2) return `${(size / 1024 ** 2).toLocaleString('es-CO', { maximumFractionDigits: 1 })} MB`;
  return `${Math.max(1, Math.round(size / 1024)).toLocaleString('es-CO')} KB`;
}

export function formatDate(utc) {
  if (!utc) return '—';
  return new Date(`${utc.replace(' ', 'T')}Z`).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
}
