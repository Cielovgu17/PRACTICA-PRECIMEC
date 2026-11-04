// Iconos de contorno, una sola familia. Son textos fijos de este archivo, nunca contenido del usuario.
const paths = {
  play: '<path d="M7 5l12 7-12 7z"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  restart: '<path d="M4 12a8 8 0 1 0 2.5-5.8L4 8.5"/><path d="M4 4v4.5h4.5"/>',
  back: '<path d="M11 6l-6 6 6 6M19 6l-6 6 6 6"/>',
  forward: '<path d="M13 6l6 6-6 6M5 6l6 6-6 6"/>',
  zoomIn: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.5-4.5M11 8.5v5M8.5 11h5"/>',
  zoomOut: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.5-4.5M8.5 11h5"/>',
  layers: '<path d="M12 4l8 4.5-8 4.5-8-4.5z"/><path d="M4 12.5l8 4.5 8-4.5M4 16.5l8 4.5 8-4.5"/>',
  cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  left: '<path d="M15 6l-6 6 6 6"/>',
  right: '<path d="M9 6l6 6-6 6"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6.5 7l1 13h9l1-13M10 11v5M14 11v5"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5c1.2-3.8 4-5.5 7.5-5.5s6.3 1.7 7.5 5.5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.9-3.4 3.3-5 6.5-5s5.6 1.6 6.5 5"/><path d="M15.5 4.8a3.5 3.5 0 0 1 0 6.4M18 15.4c1.8.7 3 2.2 3.5 4.6"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  file: '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
  tool: '<path d="M14.5 6.5a4 4 0 0 1 5-1.5l-3 3 1.5 1.5 3-3a4 4 0 0 1-5.5 5L8 18.500a2.100 2.100 0 0 1-3-3l7-6.500a4 4 0 0 1 2.500-2.500z"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.600 5.600l2.100 2.100M16.300 16.300l2.100 2.100M18.400 5.600l-2.100 2.100M7.700 16.300l-2.100 2.100"/>',
  check: '<path d="M5 12.500l4.500 4.500L19 7.500"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.200-2.4 3.700M12 17.200h.01"/>',
  // Ratón con la parte que se usa resaltada (rueda, botón izquierdo o derecho).
  mouseWheel: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M6 10h12M12 3v7"/><rect x="10.8" y="5" width="2.4" height="3.6" rx="1.2" fill="#f56f0d" stroke="#f56f0d"/>',
  mouseLeft: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M6 10h12M12 3v7"/><path d="M12 3.6a5.4 5.4 0 0 0-5.4 5.4v.4h5.4z" fill="#f56f0d" stroke="none"/>',
  mouseRight: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M6 10h12M12 3v7"/><path d="M12 3.6a5.4 5.4 0 0 1 5.4 5.4v.4H12z" fill="#f56f0d" stroke="none"/>',
  touchOne: '<path d="M9 11V5.5a1.500 1.500 0 0 1 3 0V11l3.300.8a2 2 0 0 1 1.500 2.300L16 19H9.500l-3-4.300a1.400 1.400 0 0 1 2-1.900L9 13.500"/>',
  touchTwo: '<path d="M7.5 10V5.300a1.300 1.300 0 0 1 2.600 0V10M10.100 9V4.300a1.300 1.300 0 0 1 2.600 0V10l2.800.7a1.800 1.800 0 0 1 1.300 2L16.300 18H9.500l-2.700-3.800a1.300 1.300 0 0 1 1.800-1.800l.9.700"/>',
};

export function icon(name) {
  const span = document.createElement('span');
  span.setAttribute('aria-hidden', 'true');
  span.style.display = 'contents';
  span.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
  return span;
}

function svgNode(markup) {
  const span = document.createElement('span');
  span.setAttribute('aria-hidden', 'true');
  span.style.display = 'contents';
  span.innerHTML = markup;
  return span;
}

// Retícula del logotipo PRECIMEC, ampliada como fondo del visor mientras no hay modelo.
export function reticle(className = '', { dot = false } = {}) {
  return svgNode(`<svg class="${className}" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid slice" fill="none" stroke="currentColor">
    <path d="M0 250H180M620 250H800M400 0V30M400 470V500" stroke-width="3"/>
    <path d="M400 30A220 220 0 0 1 620 250A220 220 0 0 1 400 470A220 220 0 0 1 180 250" stroke-width="20"/>
    <path d="M400 85A165 165 0 0 1 565 250A165 165 0 0 1 400 415" stroke-width="9"/>
    <path d="M235 250A165 165 0 0 1 335 98" stroke-width="9"/>
    ${dot ? '<circle cx="400" cy="250" r="16" fill="#f56f0d" stroke="none"/>' : ''}
  </svg>`);
}

// Marcas de estado de un paso: por hacer, actual (retícula con punto naranja) y hecho.
export function stepMark(status) {
  const inner = {
    pending: '<circle cx="9" cy="9" r="6.500" stroke="currentColor" stroke-width="1.500" fill="none"/>',
    current: '<circle cx="9" cy="9" r="6.500" stroke="currentColor" stroke-width="1.500" fill="none"/><path d="M9 0v3.500M9 14.500V18M0 9h3.500M14.500 9H18" stroke="currentColor" stroke-width="1.500"/><circle cx="9" cy="9" r="2.600" fill="#f56f0d"/>',
    done: '<circle cx="9" cy="9" r="7.500" fill="currentColor"/><path d="M5.500 9.200l2.400 2.400 4.600-5" stroke="#fff" stroke-width="1.600" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  }[status];
  const wrap = document.createElement('span');
  wrap.className = `mark mark-${status}`;
  wrap.setAttribute('aria-hidden', 'true');
  wrap.innerHTML = `<svg viewBox="0 0 18 18">${inner}</svg>`;
  return wrap;
}
