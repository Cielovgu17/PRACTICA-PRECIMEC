// Visor: estado vacío, controles, ayuda para mover el modelo y nombres de las piezas.
// El motor 3D solo se descarga si hay un modelo.
import { h, replace } from '../core/dom.js';
import { onLeave } from '../core/router.js';
import { icon, reticle } from './icons.js';

const SPEEDS = [0.25, 0.5, 1, 1.5, 2];

function button(name, label, onClick) {
  return h('button', { class: 'viewer-btn', type: 'button', 'aria-label': label, title: label, onClick }, icon(name));
}

function speedText(value) {
  return `${String(value).replace('.', ',')}×`;
}

// Cómo mover el modelo, siempre a la vista bajo el modelo: a quien no usa programas 3D se le olvida.
// Los botones de vista y zoom hacen lo mismo sin arrastrar, para teclado y para quien no usa ratón.
function controlsHint() {
  const touch = window.matchMedia('(pointer: coarse)').matches;
  const items = touch
    ? [['touchOne', 'Girar', 'un dedo'], ['touchTwo', 'Acercar y mover', 'dos dedos']]
    : [['mouseLeft', 'Girar', 'clic izquierdo y arrastrar'], ['mouseWheel', 'Acercar', 'rueda del ratón'], ['mouseRight', 'Mover', 'clic derecho y arrastrar']];
  return h('div', { class: 'viewer-hint', role: 'note', 'aria-label': 'Cómo mover el modelo' },
    h('ul', {}, items.map(([name, action, how]) => h('li', {},
      icon(name),
      h('span', {}, h('strong', {}, action), ` ${how}`),
    ))),
  );
}

// sources: [{ key, title, asset: { url, filename }, settings }]
export function createViewer({
  sources = [],
  note = '',
  autoplay = false,
  labelOf = (name) => name,
  onPieces,
  onPieceClick,
  onScene,
  emptyTitle = 'Visualización 3D próximamente',
  emptyText = 'Aquí se mostrarán los modelos y las animaciones de este paso.',
} = {}) {
  let engine = null;
  let raf = 0;
  let loadToken = 0;
  let speedIndex = SPEEDS.indexOf(1);
  let pinned = null;
  let current = null;
  let shownPlaying = null;

  const canvas = h('div', { class: 'viewer-canvas' });
  const noteEl = h('span', { class: 'viewer-tag', hidden: !note }, note);
  // El nombre que sigue al cursor es una ayuda visual: no se anuncia en cada movimiento del ratón.
  const tip = h('div', { class: 'viewer-tip', 'aria-hidden': 'true', hidden: true });
  const legend = h('ul', { class: 'viewer-legend', 'aria-label': 'Piezas del modelo', hidden: true });
  const hint = controlsHint();
  hint.hidden = true;

  const play = button('play', 'Reproducir', () => { engine?.setPlaying(!engine.playing); sync(); });
  const restart = button('restart', 'Volver al inicio', () => { engine?.restart(); sync(); });
  // El nombre accesible incluye lo que se ve escrito en el botón (1×, 2×…).
  const speed = h('button', { class: 'viewer-btn', type: 'button', 'aria-label': 'Velocidad 1×', title: 'Cambiar la velocidad', onClick: cycleSpeed }, '1×');
  const time = h('input', { class: 'viewer-time', type: 'range', min: 0, max: 1000, value: 0, 'aria-label': 'Posición de la animación', onInput: (e) => engine?.seekRatio(e.target.value / 1000) });
  const animationGroup = h('div', { class: 'viewer-group viewer-animation', hidden: true }, play, restart, speed, time);
  // Cámara automática: se acerca sola a lo que se mueve. Al mover la cámara a mano se apaga; este botón la enciende.
  const follow = h('button', {
    class: 'viewer-btn viewer-follow',
    type: 'button',
    'aria-pressed': 'true',
    title: 'La cámara se acerca sola a lo que se está moviendo',
    hidden: true,
    onClick: () => { if (engine) engine.setAutoCamera(!engine.autoCamera); },
  }, 'Cámara automática');
  const showFollow = (on) => follow.setAttribute('aria-pressed', on ? 'true' : 'false');
  const viewGroup = h('div', { class: 'viewer-group' },
    follow,
    ['Anterior', 'Posterior', 'Superior'].map((label, i) => h('button', {
      class: 'viewer-btn',
      type: 'button',
      title: `Vista ${label.toLowerCase()} del fémur`,
      onClick: () => engine?.view(['anterior', 'posterior', 'superior'][i]),
    }, label)),
    button('zoomOut', 'Alejar', () => engine?.zoom(1.25)),
    button('zoomIn', 'Acercar', () => engine?.zoom(0.8)),
  );
  const bar = h('div', { class: 'viewer-bar', role: 'toolbar', 'aria-label': 'Controles del visor', hidden: true }, animationGroup, viewGroup);

  const sourceBar = sources.length > 1 ? h('div', { class: 'viewer-sources', role: 'group', 'aria-label': 'Animaciones de este paso' },
    sources.map((source, index) => h('button', {
      class: 'viewer-source',
      type: 'button',
      'aria-pressed': index === 0 ? 'true' : 'false',
      onClick: (event) => {
        sourceBar.querySelectorAll('.viewer-source').forEach((el) => el.setAttribute('aria-pressed', 'false'));
        event.currentTarget.setAttribute('aria-pressed', 'true');
        load(source);
      },
    }, source.title)),
  ) : null;

  const root = h('div', { class: 'viewer', role: 'region', 'aria-label': 'Visor 3D' }, sourceBar, canvas, hint, bar);

  function showEmpty() {
    replace(canvas,
      h('div', { class: 'viewer-empty', role: 'status' },
        reticle('viewer-reticle'),
        h('div', { class: 'viewer-empty-copy' }, h('i', { class: 'viewer-dot' }), h('strong', {}, emptyTitle), h('span', {}, emptyText)),
      ),
    );
  }

  function status(text) {
    let el = canvas.querySelector('.viewer-status');
    if (!text) { el?.remove(); return; }
    if (!el) { el = h('div', { class: 'viewer-status', role: 'status' }); canvas.append(el); }
    el.textContent = text;
  }

  function cycleSpeed() {
    speedIndex = (speedIndex + 1) % SPEEDS.length;
    const value = SPEEDS[speedIndex];
    engine?.setSpeed(value);
    speed.textContent = speedText(value);
    speed.setAttribute('aria-label', `Velocidad ${speedText(value)}`);
  }

  // El ícono del botón se cambia solo cuando cambia el estado. Si se reemplazara en cada cuadro, el clic
  // podía caer sobre un ícono que ya no existía y a veces la pausa no respondía.
  function sync() {
    if (!engine) return;
    if (shownPlaying !== engine.playing) {
      shownPlaying = engine.playing;
      const label = shownPlaying ? 'Pausar' : 'Reproducir';
      replace(play, icon(shownPlaying ? 'pause' : 'play'));
      play.setAttribute('aria-label', label);
      play.title = label;
    }
    if (document.activeElement !== time) time.value = Math.round(engine.ratio() * 1000);
    const info = engine.info();
    const value = `${(info.time - info.start).toFixed(1).replace('.', ',')} de ${(info.end - info.start).toFixed(1).replace('.', ',')} segundos`;
    if (time.getAttribute('aria-valuetext') !== value) time.setAttribute('aria-valuetext', value);
  }

  // Nombre de la pieza: sigue al cursor, y al hacer clic o tocarla queda fijo.
  function showTip(name, x, y) {
    if (!name) { tip.hidden = true; return; }
    tip.textContent = labelOf(name);
    tip.hidden = false;
    const box = canvas.getBoundingClientRect();
    const width = tip.offsetWidth;
    tip.style.left = `${Math.min(Math.max(x - box.left + 14, 8), box.width - width - 8)}px`;
    tip.style.top = `${Math.max(y - box.top - 38, 8)}px`;
  }

  function paintLegend() {
    legend.querySelectorAll('button').forEach((el) => el.setAttribute('aria-pressed', String(el.dataset.piece === pinned)));
  }

  function setPinned(name, x, y) {
    pinned = name;
    engine?.highlight(name);
    if (name) showTip(name, x, y);
    else tip.hidden = true;
    paintLegend();
  }

  function buildLegend() {
    const pieces = engine.pieces().filter((name) => !engine.hidden?.has(name));
    // Con muchas piezas la lista taparía el modelo; los nombres siguen saliendo con el cursor.
    legend.hidden = pieces.length === 0 || pieces.length > 4;
    replace(legend, pieces.map((name) => h('li', {},
      h('button', {
        type: 'button',
        'data-piece': name,
        'aria-pressed': 'false',
        onPointerenter: () => { if (!pinned) engine?.highlight(name); },
        onPointerleave: () => { if (!pinned) engine?.highlight(null); },
        onFocus: () => { if (!pinned) engine?.highlight(name); },
        onBlur: () => { if (!pinned) engine?.highlight(null); },
        onClick: () => {
          pinned = pinned === name ? null : name;
          engine?.highlight(pinned);
          tip.hidden = true;
          paintLegend();
        },
      }, labelOf(name)),
    )));
    paintLegend();
  }

  function dispose() {
    cancelAnimationFrame(raf);
    raf = 0;
    engine?.dispose();
    engine = null;
    pinned = null;
    shownPlaying = null;
  }

  function report() {
    onPieces?.(engine.pieces());
    onScene?.(current, engine.info());
  }

  async function load(source) {
    const token = ++loadToken;
    current = source;
    dispose();
    bar.hidden = true;
    hint.hidden = true;
    legend.hidden = true;
    tip.hidden = true;
    replace(canvas, noteEl, legend, tip);
    status('Cargando el visor…');
    try {
      const { Engine3D } = await import('./viewer3d.js');
      if (token !== loadToken) return;
      engine = new Engine3D(canvas);
      engine.onEnd = sync;
      engine.onAutoChange = showFollow;
      // Para lectores de pantalla el lienzo es una imagen con nombre; las vistas se cambian con los botones.
      const drawing = canvas.querySelector('canvas');
      drawing.setAttribute('role', 'img');
      drawing.setAttribute('aria-label', `Modelo 3D: ${source.title}. Usa los botones Anterior, Posterior, Superior, Alejar y Acercar para cambiar la vista.`);
      await engine.load(source, (percent) => {
        if (token === loadToken) status(percent === null ? 'Cargando el modelo…' : `Cargando el modelo: ${percent} %`);
      });
      if (token !== loadToken) { dispose(); return; }
      status('');
      buildLegend();
      report();
      engine.enablePicking({
        onHover: (name, x, y) => {
          if (pinned) return;
          engine.highlight(name);
          showTip(name, x, y);
        },
        onSelect: (name, x, y) => {
          setPinned(name === pinned ? null : name, x, y);
          if (name) onPieceClick?.(name);
        },
      });
      const animated = engine.hasAnimation();
      bar.hidden = false;
      hint.hidden = false;
      animationGroup.hidden = !animated;
      follow.hidden = !engine.focus;
      showFollow(engine.autoCamera);
      if (animated) {
        const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (autoplay && !calm) engine.setPlaying(true);
        const tick = () => {
          raf = requestAnimationFrame(tick);
          sync();
        };
        tick();
      }
    } catch (error) {
      if (token !== loadToken) return;
      console.error(error);
      dispose();
      status(error.message === 'webgl'
        ? 'Este dispositivo no permite mostrar gráficos 3D.'
        : 'No se pudo abrir este modelo. Revisa que el archivo no esté dañado.');
    }
  }

  root.setNote = (text) => {
    noteEl.textContent = text;
    noteEl.hidden = !text;
  };
  root.highlight = (name) => {
    if (!pinned) engine?.highlight(name);
  };
  root.relabel = () => {
    if (engine) buildLegend();
    if (pinned && !tip.hidden) tip.textContent = labelOf(pinned);
  };
  // Aplica en vivo los ajustes que se cambian en el modo edición (escena, tramo, piezas ocultas).
  root.configure = (settings) => {
    if (!engine || !current) return;
    current.settings = settings;
    engine.configure(settings);
    animationGroup.hidden = !engine.hasAnimation();
    buildLegend();
    report();
  };
  root.currentTime = () => engine?.info().time ?? 0;
  root.engine = () => engine;                                      // para revisar el visor desde la consola
  root.destroy = () => {
    loadToken += 1;
    dispose();
  };

  if (sources.length) load(sources[0]);
  else showEmpty();

  onLeave(root.destroy);
  return root;
}
