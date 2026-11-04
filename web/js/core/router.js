// Navegación sin recargar la página.
const routes = [];
let cleanups = [];
let renderToken = 0;
let notFoundView;
let target;

export function addRoute(path, view) {
  const pattern = new RegExp(`^${path.replace(/:\w+/g, '(\\d+)')}/?$`);
  routes.push({ pattern, view });
}

export function setNotFound(view) {
  notFoundView = view;
}

// Las vistas registran aquí lo que deben liberar al salir (por ejemplo, el visor 3D).
export function onLeave(fn) {
  cleanups.push(fn);
}

export function navigate(path, { replace = false } = {}) {
  history[replace ? 'replaceState' : 'pushState']({}, '', path);
  return render();
}

export async function render() {
  const token = ++renderToken;
  cleanups.forEach((fn) => fn());
  cleanups = [];
  const path = location.pathname;
  let view = notFoundView;
  let params = [];
  for (const route of routes) {
    const match = path.match(route.pattern);
    if (match) {
      view = route.view;
      params = match.slice(1).map(Number);
      break;
    }
  }
  const node = await view(...params);
  if (token !== renderToken || !node) return;
  target.replaceChildren(...[node].flat());
  window.scrollTo(0, 0);
}

export function startRouter(root) {
  target = root;
  window.addEventListener('popstate', render);
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || link.target === '_blank') return;
    const href = link.getAttribute('href');
    if (!href.startsWith('/') || href.startsWith('/archivos/')) return;
    event.preventDefault();
    navigate(href);
  });
  return render();
}
