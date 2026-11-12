// El instructivo en una sola pantalla: pasos a la izquierda y, al elegir uno, su animación a la derecha.
// En modo edición es la misma pantalla, con formularios en lugar de los textos.
import { h, replace, toast } from '../core/dom.js';
import { assetOf, findPage, isComplete, loadContent, pages, progress, resumePage, setCurrent, setDone, state } from '../core/store.js';
import { icon, stepMark } from '../components/icons.js';
import { layout, setTitle } from '../components/shell.js';
import { createImagePanel } from '../components/imagePanel.js';
import { createViewer } from '../components/viewer.js';
import { notFoundView } from './notFound.js';
import { createEditing } from './stepEditing.js';

function animationsOf(step) {
  return step.animations
    .map((animation) => ({
      key: `a${animation.id}:${animation.asset_id}`,
      animationId: animation.id,
      title: animation.title,
      asset: assetOf(animation.asset_id),
      settings: { ...(animation.settings || {}) },
    }))
    .filter((source) => source.asset);
}

function imagesOf(step) {
  return step.media
    .map((item) => ({ key: `i${item.id}:${item.asset_id}`, title: item.caption || assetOf(item.asset_id)?.filename, asset: assetOf(item.asset_id) }))
    .filter((image) => image.asset?.kind === 'image');
}

// Qué se ve a la derecha: solo lo que corresponde al paso elegido. Ya no se muestra el modelo general
// (clavo con la hoja) en etapas o subpasos que no tienen animación propia: confundía con otro paso.
function sourcesFor({ step, parent }) {
  // Una etapa con subpasos no muestra nada propio (ni imagen ni animación) hasta que se elige un subpaso.
  if (!parent && step.children.length) {
    return {
      sources: [],
      empty: { title: 'Elige un subpaso', text: 'Abre uno de los subpasos de la lista para ver su animación o su imagen.' },
    };
  }
  const own = animationsOf(step);
  if (own.length) return { sources: own, note: '' };
  const ownImages = imagesOf(step);
  if (ownImages.length) return { images: ownImages, sources: [], note: '' };
  // Un subpaso sin animación propia sigue mostrando la de su etapa, si la etapa tiene una.
  const inherited = parent ? animationsOf(parent) : [];
  if (inherited.length) return { sources: inherited, note: '' };
  return { sources: [] };
}

function labelOf(raw) {
  return state.doc.piece_names?.[raw] || raw;
}

export async function instructivoView(stepId) {
  const { technique } = state.doc;
  let current = stepId ? findPage(stepId) : resumePage();
  if (stepId && !current) return notFoundView();
  setTitle('');

  const base = state.editing ? '/editar/paso/' : '/paso/';
  let sequence = pages();
  // Etapas abiertas a mano y etapas que la persona cerró aunque tengan el paso actual.
  const expanded = new Set();
  const collapsed = new Set();
  const percentText = h('strong', {});
  const percentFill = h('div', { class: 'progress-fill' });
  const percentTrack = h('div', { class: 'progress-track', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-label': 'Avance del instructivo' }, percentFill);
  const list = h('ol', { class: 'steps', 'aria-labelledby': 'lista-etapas' });
  const viewerHolder = h('div', { class: 'guide-viewer' });
  const prevButton = h('button', { class: 'btn', type: 'button', onClick: () => move(-1) }, icon('left'), 'Paso anterior');
  const nextLabel = h('span', {});
  const nextButton = h('button', { class: 'btn btn-primary', type: 'button', onClick: () => move(1) }, nextLabel, icon('right'));
  let activeViewer = null;
  let activeKey = null;

  const editing = state.editing ? await createEditing({
    refresh: async (id) => {
      await loadContent();
      sequence = pages();
      current = (id && findPage(id)) || sequence[0] || null;
      if (current) history.replaceState({}, '', `${base}${current.step.id}`);
      render();
    },
    getViewer: () => activeViewer,
  }) : null;

  function paintProgress() {
    const { percent } = progress();
    percentText.textContent = `${percent} %`;
    percentFill.style.width = `${percent}%`;
    percentTrack.setAttribute('aria-valuenow', percent);
  }

  function field(title, text) {
    if (!text) return null;
    return h('div', { class: 'step-field' }, h('h3', {}, title), h('p', {}, text));
  }

  function stepDetail(page) {
    if (editing) return editing.stepForm(page);
    const { step, isLeaf } = page;
    const instruments = step.instrument_ids
      .map((id) => state.doc.instruments.find((item) => item.id === id))
      .filter(Boolean);
    // Las imágenes se ven a la derecha; aquí solo se listan si el paso muestra una animación en su lugar.
    const media = step.media
      .map((item) => ({ ...item, asset: assetOf(item.asset_id) }))
      .filter((item) => item.asset && (item.asset.kind !== 'image' || animationsOf(step).length));
    const done = state.done.has(step.id);
    return h('div', { class: 'step-detail' },
      field('Descripción', step.description),
      instruments.length > 0 && h('div', { class: 'step-field' },
        h('h3', {}, 'Instrumental'),
        h('ul', { class: 'chips' }, instruments.map((item) => h('li', { class: 'chip' }, item.name))),
      ),
      step.recommendations && h('div', { class: 'step-note' }, h('h3', {}, 'Recomendaciones para el instrumentador'), h('p', {}, step.recommendations)),
      media.length > 0 && h('div', { class: 'step-field' },
        h('h3', {}, 'Material de apoyo'),
        h('ul', { class: 'step-media' }, media.map((item) => h('li', {},
          h('a', { href: item.asset.url, target: '_blank', rel: 'noopener' }, icon('file'), item.caption || item.asset.filename),
        ))),
      ),
      isLeaf && h('button', {
        class: 'btn step-done',
        type: 'button',
        // El botón siempre dice «Completado»; el estado lo muestran el visto y aria-pressed.
        'aria-pressed': done ? 'true' : 'false',
        onClick: () => {
          setDone(step.id, !state.done.has(step.id));
          render();
        },
      }, done && icon('check'), 'Completado'),
    );
  }

  function markFor(step) {
    if (current?.step.id === step.id) return stepMark('current');
    return stepMark(isComplete(step) ? 'done' : 'pending');
  }

  function holdsCurrent(step) {
    return current?.step.id === step.id || step.children.some((child) => child.id === current?.step.id);
  }

  function isOpen(step) {
    return (holdsCurrent(step) || expanded.has(step.id)) && !collapsed.has(step.id);
  }

  // Tocar una etapa abierta la cierra; tocarla cerrada la abre y la muestra.
  function toggleStage(page) {
    const { step } = page;
    if (isOpen(step)) {
      collapsed.add(step.id);
      expanded.delete(step.id);
      render();
      return;
    }
    collapsed.delete(step.id);
    expanded.add(step.id);
    if (holdsCurrent(step)) render();
    else select(page);
  }

  function stepButton(page, isChild) {
    const { step, number } = page;
    const selected = current?.step.id === step.id;
    const open = !isChild && isOpen(step);
    // El estado (completado, actual) se dice en palabras: el círculo solo lo muestra con su forma.
    const status = selected ? ', paso actual' : isComplete(step) ? ', completado' : '';
    return h('button', {
      class: `step-head${isChild ? ' is-child' : ''}`,
      type: 'button',
      'aria-current': selected ? 'step' : null,
      'aria-expanded': isChild || !step.children.length ? null : String(open),
      'aria-controls': isChild || !step.children.length ? null : `subpasos-${step.id}`,
      onClick: () => (isChild ? select(page) : toggleStage(page)),
    },
      markFor(step),
      h('span', { class: 'step-number' }, number),
      h('span', { class: 'step-title' }, step.title, status && h('span', { class: 'sr-only' }, status)),
      !isChild && h('span', { class: `step-chevron${open ? ' is-open' : ''}`, 'aria-hidden': 'true' }, icon('chevron')),
    );
  }

  function paintList() {
    const pageOf = new Map(sequence.map((page) => [page.step.id, page]));
    replace(list, state.doc.steps.map((step) => {
      const page = pageOf.get(step.id);
      const open = isOpen(step);
      return h('li', { class: `step-card${open && holdsCurrent(step) ? ' is-open' : ''}` },
        stepButton(page, false),
        open && current?.step.id === step.id && stepDetail(page),
        open && step.children.length > 0 && h('ol', { class: 'step-subs', id: `subpasos-${step.id}`, 'aria-label': `Subpasos de ${step.title}` }, step.children.map((child) => {
          const childPage = pageOf.get(child.id);
          return h('li', { class: current?.step.id === child.id ? 'is-selected' : '' },
            stepButton(childPage, true),
            current?.step.id === child.id && stepDetail(childPage),
          );
        })),
      );
    }));
    editing?.paintPieces();
  }

  function paintViewer() {
    const { sources, images, note = '', empty } = current ? sourcesFor(current) : { sources: [] };
    const key = (images || sources).map((source) => source.key).join('|') || `vacio:${empty?.title || ''}`;
    if (key === activeKey) {
      activeViewer?.setNote(note);
      return;
    }
    activeViewer?.destroy();
    activeKey = key;
    editing?.setPieces([]);
    editing?.setScene(null, null);
    activeViewer = images ? createImagePanel({ images }) : createViewer({
      sources,
      note,
      autoplay: true,
      labelOf,
      onPieces: editing ? editing.setPieces : undefined,
      onPieceClick: editing ? editing.focusPiece : undefined,
      onScene: editing ? editing.setScene : undefined,
      ...(empty ? { emptyTitle: empty.title, emptyText: empty.text } : {}),
    });
    replace(viewerHolder, activeViewer);
  }

  function paintPager() {
    const index = sequence.findIndex((page) => page.step.id === current?.step.id);
    prevButton.disabled = index <= 0;
    nextLabel.textContent = index === sequence.length - 1 ? 'Finalizar' : 'Paso siguiente';
    nextButton.disabled = !current;
  }

  function render() {
    paintList();
    paintViewer();
    paintPager();
    paintProgress();
  }

  function select(page) {
    current = page;
    collapsed.delete((page.parent || page.step).id);
    setCurrent(page.step.id);
    history.replaceState({}, '', `${base}${page.step.id}`);
    render();
    const selected = list.querySelector('[aria-current="step"]');
    selected?.scrollIntoView({ block: 'nearest' });
    // En teléfono la animación queda arriba: se lleva a la vista al elegir un paso.
    if (!editing && window.matchMedia('(max-width: 899px)').matches) viewerHolder.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  function move(direction) {
    const index = sequence.findIndex((page) => page.step.id === current.step.id);
    if (direction > 0 && current.isLeaf && !editing) setDone(current.step.id, true);
    const target = sequence[index + direction];
    if (target) select(target);
    else {
      render();
      toast('Llegaste al final del instructivo.');
    }
  }

  if (current) setCurrent(current.step.id);
  render();

  const scroller = h('div', { class: 'guide-scroll' },
    editing
      ? editing.techniqueForm()
      : technique.intro && h('p', { class: 'guide-intro' }, technique.intro),
    // Encabezado para lectores de pantalla: ordena la página (título, etapas, detalle).
    h('h2', { class: 'sr-only', id: 'lista-etapas' }, 'Etapas de la técnica'),
    list,
    editing?.addStepForm(),
  );

  const content = layout('instructivo',
    editing?.bar(),
    h('main', { class: 'guide' },
      h('section', { class: 'guide-steps', 'aria-labelledby': 'lista-etapas' },
        !editing && h('div', { class: 'guide-head' },
          h('div', { class: 'guide-progress' }, h('span', {}, percentText, ' de avance'), percentTrack),
        ),
        state.doc.steps.length || editing ? scroller : h('p', { class: 'empty-note' }, 'Aún no hay pasos publicados.'),
        h('div', { class: 'guide-pager' }, prevButton, nextButton),
      ),
      viewerHolder,
    ),
  );
  document.getElementById('app').classList.add('is-learning');
  return content;
}
