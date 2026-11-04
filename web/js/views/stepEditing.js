// Modo edición del instructivo: los formularios que aparecen sobre la misma pantalla de pasos.
import { h, confirmDialog, replace, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { assetOf, state } from '../core/store.js';
import { icon } from '../components/icons.js';
import { assetField, loadAssets } from '../admin/assetField.js';

// Un solo texto por paso, escrito para el instrumentador, más sus recomendaciones.
const TEXT_FIELDS = [
  ['description', 'Descripción'],
  ['recommendations', 'Recomendaciones para el instrumentador'],
];

function seconds(value) {
  return `${Number(value).toFixed(1).replace('.', ',')} s`;
}

function fileTitle(filename) {
  return filename.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim();
}

function iconButton(name, label, onClick, disabled = false, danger = false) {
  return h('button', { class: `btn btn-icon${danger ? ' btn-danger' : ''}`, type: 'button', title: label, 'aria-label': label, disabled, onClick }, icon(name));
}

// refresh(id): vuelve a cargar el borrador y selecciona ese paso.
// getViewer(): el visor actual, para resaltar y renombrar piezas.
export async function createEditing({ refresh, getViewer }) {
  const assets = await loadAssets();
  const open = new Set();
  const statusText = h('span', { class: 'edit-status', role: 'status' });
  const publishButton = h('button', { class: 'btn btn-primary', type: 'button', onClick: publish }, 'Publicar');
  const piecesHolder = h('div', {});
  let pieces = [];

  async function updateStatus(saved = false) {
    const { status } = await api('GET', '/api/admin/draft');
    publishButton.disabled = !status.has_changes;
    statusText.textContent = status.has_changes
      ? `${saved ? 'Guardado. ' : ''}Falta publicar para que los demás lo vean.`
      : 'Todo está publicado.';
  }

  // Corre un cambio y avisa si el servidor lo rechaza. Devuelve true si se guardó.
  async function save(action) {
    try {
      await action();
      await updateStatus(true);
      return true;
    } catch (error) {
      toast(error.message, true);
      return false;
    }
  }

  async function publish() {
    const ok = await confirmDialog({
      title: 'Publicar los cambios',
      message: 'Todas las personas que consultan el instructivo verán esta versión.',
      confirm: 'Publicar',
    });
    if (!ok) return;
    if (await save(() => api('POST', '/api/admin/publish'))) toast('Cambios publicados.');
  }

  function bar() {
    return h('div', { class: 'edit-bar' },
      h('strong', {}, 'Modo edición'),
      statusText,
      h('div', { class: 'edit-bar-actions' },
        publishButton,
        h('a', { class: 'btn', href: '/admin' }, 'Más opciones'),
        h('a', {
          class: 'btn',
          href: '/',
          onClick: () => { if (!publishButton.disabled) toast('Tus cambios quedaron guardados, sin publicar.'); },
        }, 'Salir'),
      ),
    );
  }

  // Un campo de texto que se guarda solo al salir de él.
  function textInput(id, label, value, onSave, { multiline = false, required = false } = {}) {
    const input = multiline
      ? h('textarea', { class: 'textarea', id, rows: 3 }, value)
      : h('input', { class: 'input', id, value, required, maxlength: 200 });
    let lastSaved = value;
    input.addEventListener('change', async () => {
      const ok = await save(() => onSave(input.value));
      if (ok) lastSaved = input.value;
      else input.value = lastSaved;
    });
    return h('div', { class: 'field' }, h('label', { for: id }, label), input);
  }

  function techniqueForm() {
    const { technique } = state.doc;
    const update = (field) => async (value) => {
      // El borrador se recarga tras otros cambios: siempre se parte del más reciente.
      await api('PUT', '/api/admin/technique', { ...state.doc.technique, [field]: value });
      state.doc.technique[field] = value;
    };
    return section('tecnica', 'Nombre e introducción del instructivo',
      textInput('tech-name', 'Nombre de la técnica', technique.name, async (value) => {
        await update('name')(value);
        const heading = document.getElementById('titulo-tecnica');
        if (heading) heading.textContent = `Técnica quirúrgica: ${value}`;
      }, { required: true }),
      textInput('tech-intro', 'Texto de introducción', technique.intro, update('intro'), { multiline: true }),
    );
  }

  function section(id, title, ...content) {
    return h('details', {
      class: 'edit-section',
      open: open.has(id),
      onToggle: (event) => {
        if (event.target.open) open.add(id);
        else open.delete(id);
      },
    }, h('summary', {}, title), h('div', { class: 'edit-section-body' }, content));
  }

  function moveButtons(step, siblings, path, label) {
    const index = siblings.findIndex((item) => item.id === step.id);
    const move = (direction) => async () => {
      if (await save(() => api('POST', `${path}/move`, { direction }))) await refresh(step.id);
    };
    return [
      iconButton('up', `Subir ${label}`, move('up'), index === 0),
      iconButton('down', `Bajar ${label}`, move('down'), index === siblings.length - 1),
    ];
  }

  function animationsSection(step) {
    const pathOf = (animation) => `/api/admin/animations/${animation.id}`;
    const put = (animation, changes) => api('PUT', pathOf(animation), {
      asset_id: animation.asset_id,
      title: animation.title,
      description: animation.description,
      ...changes,
    });
    const rows = step.animations.map((animation) => {
      const picker = assetField({
        id: `anim-file-${animation.id}`,
        label: 'Archivo',
        kind: 'model',
        assets,
        value: animation.asset_id,
        emptyLabel: 'Elige un archivo',
        onChange: async (assetId) => {
          if (assetId && await save(() => put(animation, { asset_id: assetId }))) await refresh(step.id);
        },
      });
      return h('li', { class: 'edit-animation' },
        textInput(`anim-title-${animation.id}`, 'Nombre de la animación', animation.title, async (value) => {
          await put(animation, { title: value });
          animation.title = value;
        }, { required: true }),
        picker,
        h('div', { class: 'edit-row-actions' },
          moveButtonsFor(animation, step),
          iconButton('trash', `Quitar ${animation.title}`, async () => {
            if (await save(() => api('DELETE', pathOf(animation)))) await refresh(step.id);
          }, false, true),
        ),
      );
    });
    const adder = assetField({
      id: `anim-add-${step.id}`,
      label: 'Agregar una animación o modelo',
      kind: 'model',
      assets,
      emptyLabel: 'Elige un archivo ya cargado, o súbelo',
      onChange: async (assetId) => {
        if (!assetId) return;
        const asset = assets.find((item) => item.id === assetId);
        const payload = { asset_id: assetId, title: fileTitle(asset.filename) };
        if (await save(() => api('POST', `/api/admin/steps/${step.id}/animations`, payload))) await refresh(step.id);
      },
    });
    return section(`anim-${step.id}`, `Animación de este paso (${step.animations.length})`,
      rows.length > 0 && h('ul', { class: 'edit-list' }, rows),
      rows.length === 0 && h('p', { class: 'field-hint' }, 'Este paso no tiene animación propia; por eso se ve el modelo general.'),
      adder,
    );
  }

  function imagesSection(step) {
    const images = step.media
      .map((item) => ({ item, asset: assetOf(item.asset_id) }))
      .filter(({ asset }) => asset?.kind === 'image');
    const adder = assetField({
      id: `image-add-${step.id}`,
      label: 'Agregar una imagen',
      kind: 'image',
      assets,
      emptyLabel: 'Elige una imagen ya cargada, o súbela',
      onChange: async (assetId) => {
        if (!assetId) return;
        const asset = assets.find((item) => item.id === assetId);
        const payload = { asset_id: assetId, caption: fileTitle(asset.filename) };
        if (await save(() => api('POST', `/api/admin/steps/${step.id}/media`, payload))) await refresh(step.id);
      },
    });
    return section(`images-${step.id}`, `Imágenes de este paso (${images.length})`,
      h('p', { class: 'field-hint' }, 'Se ven a la derecha cuando el paso no tiene animación propia.'),
      images.length > 0 && h('ul', { class: 'edit-list' }, images.map(({ item, asset }) => h('li', { class: 'edit-image' },
        h('img', { src: asset.url, alt: '' }),
        h('div', { class: 'field' }, h('span', { class: 'field-hint' }, item.caption || asset.filename)),
        iconButton('trash', `Quitar ${item.caption || asset.filename}`, async () => {
          if (await save(() => api('DELETE', `/api/admin/media/${item.id}`))) await refresh(step.id);
        }, false, true),
      ))),
      adder,
    );
  }

  function moveButtonsFor(animation, step) {
    if (step.animations.length < 2) return [];
    const index = step.animations.findIndex((item) => item.id === animation.id);
    const move = (direction) => async () => {
      if (await save(() => api('POST', `/api/admin/animations/${animation.id}/move`, { direction }))) await refresh(step.id);
    };
    return [
      iconButton('up', `Subir ${animation.title}`, move('up'), index === 0),
      iconButton('down', `Bajar ${animation.title}`, move('down'), index === step.animations.length - 1),
    ];
  }

  function instrumentsSection(step) {
    const newName = h('input', { class: 'input', id: `inst-new-${step.id}`, maxlength: 200, placeholder: 'Nombre del instrumento' });
    const rows = state.doc.instruments.map((item) => {
      const name = h('input', { class: 'input', value: item.name, maxlength: 200, 'aria-label': `Nombre de ${item.name}` });
      name.addEventListener('change', async () => {
        const ok = await save(() => api('PUT', `/api/admin/instruments/${item.id}`, { ...item, name: name.value }));
        if (ok) item.name = name.value;
        else name.value = item.name;
      });
      return h('li', { class: 'edit-instrument' },
        h('input', {
          type: 'checkbox',
          checked: step.instrument_ids.includes(item.id),
          title: 'Se usa en este paso',
          'aria-label': `${item.name} se usa en este paso`,
          onChange: async (event) => {
            const ids = event.target.checked
              ? [...step.instrument_ids, item.id]
              : step.instrument_ids.filter((id) => id !== item.id);
            const ok = await save(() => api('PUT', `/api/admin/steps/${step.id}/instruments`, { ids }));
            if (ok) step.instrument_ids = ids;
            else event.target.checked = !event.target.checked;
          },
        }),
        name,
      );
    });
    return section(`inst-${step.id}`, `Instrumental de este paso (${step.instrument_ids.length})`,
      h('p', { class: 'field-hint' }, 'Marca los que se usan en este paso. Para renombrar uno, escribe sobre su nombre.'),
      h('ul', { class: 'edit-list' }, rows),
      h('form', {
        class: 'edit-add',
        onSubmit: async (event) => {
          event.preventDefault();
          const ok = await save(async () => {
            const { id } = await api('POST', '/api/admin/instruments', { name: newName.value });
            await api('PUT', `/api/admin/steps/${step.id}/instruments`, { ids: [...step.instrument_ids, id] });
          });
          if (ok) await refresh(step.id);
        },
      }, newName, h('button', { class: 'btn', type: 'submit' }, icon('plus'), 'Agregar')),
    );
  }

  // La animación que está en el visor y lo que el visor sabe de ella (escenas, duración, piezas ocultas).
  let scene = { source: null, info: null };

  function setScene(source, info) {
    scene = { source, info };
    paintPieces();
  }

  async function saveSettings(changes) {
    const { source, info } = scene;
    const settings = { clip: info.clip, start: info.start, end: info.end, hidden: info.hidden, ...changes };
    const ok = await save(() => api('PUT', `/api/admin/animations/${source.animationId}/settings`, settings));
    if (!ok) return;
    source.settings = settings;
    // El borrador en memoria queda igual que el guardado, para que no se pierda al cambiar de paso.
    state.doc.steps.flatMap((item) => [item, ...item.children])
      .flatMap((item) => item.animations)
      .filter((animation) => animation.id === source.animationId)
      .forEach((animation) => { animation.settings = settings; });
    getViewer()?.configure(settings);
  }

  function sceneControls() {
    const { source, info } = scene;
    if (!source?.animationId || !info) {
      return h('p', { class: 'field-hint' }, 'El recorte y las piezas ocultas se ajustan cuando el paso tiene su propia animación.');
    }
    const timeField = (key, label) => {
      const input = h('input', { class: 'input', type: 'number', min: 0, max: info.duration, step: 0.1, value: info[key].toFixed(1), id: `anim-${key}` });
      input.addEventListener('change', () => saveSettings({ [key]: Math.min(Math.max(Number(input.value) || 0, 0), info.duration) }));
      return h('div', { class: 'field' },
        h('label', { for: `anim-${key}` }, label),
        h('div', { class: 'edit-time' },
          input,
          h('button', {
            class: 'btn',
            type: 'button',
            title: 'Usar el momento en que está la animación',
            'aria-label': `Usar el momento actual de la animación como ${key === 'start' ? 'inicio' : 'final'}`,
            onClick: () => saveSettings({ [key]: Math.round(getViewer().currentTime() * 10) / 10 }),
          }, 'Momento actual'),
        ),
      );
    };
    return h('div', { class: 'edit-scene' },
      info.clips.length > 1 && h('div', { class: 'field' },
        h('label', { for: 'anim-clip' }, 'Escena del archivo'),
        h('select', {
          class: 'select',
          id: 'anim-clip',
          onChange: (event) => saveSettings({ clip: event.target.value, start: null, end: null }),
        }, info.clips.map((name) => h('option', { value: name, selected: name === info.clip }, name.replace(/_/g, ' ')))),
        h('span', { class: 'field-hint' }, 'Este archivo trae varias escenas. Elige la que corresponde a este paso.'),
      ),
      info.duration > 0 && h('div', { class: 'edit-grid-2' }, timeField('start', 'Empieza en (segundos)'), timeField('end', 'Termina en (segundos)')),
      info.duration > 0 && h('p', { class: 'field-hint' }, `Duración total de la escena: ${seconds(info.duration)}. Solo se reproduce el tramo elegido, una vez.`),
    );
  }

  function paintPieces() {
    const names = state.doc.piece_names || {};
    const controls = sceneControls();
    if (!pieces.length) {
      replace(piecesHolder, controls, h('p', { class: 'field-hint' }, 'Aquí aparecen las piezas cuando el modelo termina de cargar.'));
      return;
    }
    const canHide = Boolean(scene.source?.animationId && scene.info);
    const hidden = new Set(scene.info?.hidden || []);
    replace(piecesHolder,
      controls,
      h('p', { class: 'field-hint' }, canHide
        ? 'Desmarca una pieza para ocultarla en esta animación. El nombre es el que sale al pasar el cursor.'
        : 'Es el nombre que sale al pasar el cursor. Si haces clic en una pieza del modelo, te lleva a su casilla.'),
      h('ul', { class: 'edit-list' }, pieces.map((raw) => {
        const input = h('input', {
          class: 'input',
          value: names[raw] || raw,
          maxlength: 200,
          'data-piece': raw,
          'aria-label': `Nombre de la pieza ${raw}`,
          onFocus: () => getViewer()?.highlight(raw),
          onBlur: () => getViewer()?.highlight(null),
          onPointerenter: () => getViewer()?.highlight(raw),
          onPointerleave: () => { if (document.activeElement !== input) getViewer()?.highlight(null); },
        });
        input.addEventListener('change', async () => {
          const label = input.value.trim();
          const ok = await save(() => api('PUT', '/api/admin/piece-names', { raw, label }));
          if (!ok) return;
          state.doc.piece_names = { ...(state.doc.piece_names || {}) };
          if (label && label !== raw) state.doc.piece_names[raw] = label;
          else delete state.doc.piece_names[raw];
          input.value = state.doc.piece_names[raw] || raw;
          getViewer()?.relabel();
        });
        if (!canHide) return h('li', {}, input);
        return h('li', { class: 'edit-instrument' },
          h('input', {
            type: 'checkbox',
            checked: !hidden.has(raw),
            title: 'Se ve en esta animación',
            'aria-label': `${names[raw] || raw} se ve en esta animación`,
            onChange: (event) => {
              const next = new Set(hidden);
              if (event.target.checked) next.delete(raw);
              else next.add(raw);
              saveSettings({ hidden: [...next] });
            },
          }),
          input,
        );
      })),
    );
  }

  function setPieces(names) {
    pieces = names;
    paintPieces();
  }

  function focusPiece(raw) {
    const details = piecesHolder.closest('details');
    if (details) details.open = true;
    const input = [...piecesHolder.querySelectorAll('input')].find((el) => el.dataset.piece === raw);
    input?.focus();
    input?.select();
    input?.scrollIntoView({ block: 'nearest' });
  }

  function stepForm(page) {
    const { step, parent } = page;
    const siblings = parent ? parent.children : state.doc.steps;
    const kind = parent ? 'el subpaso' : 'el paso';
    const payload = (changes) => ({
      title: step.title,
      objective: step.objective,
      description: step.description,
      procedure: step.procedure,
      observations: step.observations,
      recommendations: step.recommendations,
      is_sample: step.is_sample,
      ...changes,
    });
    const update = (field) => async (value) => {
      await api('PUT', `/api/admin/steps/${step.id}`, payload({ [field]: value }));
      step[field] = value;
    };
    const newSub = h('input', { class: 'input', id: `sub-new-${step.id}`, maxlength: 200, placeholder: 'Título del subpaso' });

    return h('div', { class: 'step-detail step-editor' },
      h('div', { class: 'edit-row-actions' },
        moveButtons(step, siblings, `/api/admin/steps/${step.id}`, kind),
        iconButton('trash', `Eliminar ${kind}`, async () => {
          const ok = await confirmDialog({
            title: `Eliminar ${kind}`,
            message: step.children.length
              ? `Se eliminará «${step.title}» junto con sus subpasos (${step.children.length}).`
              : `Se eliminará «${step.title}».`,
            confirm: 'Eliminar',
            danger: true,
          });
          if (!ok) return;
          const index = siblings.findIndex((item) => item.id === step.id);
          const neighbor = siblings[index + 1] || siblings[index - 1] || parent;
          if (await save(() => api('DELETE', `/api/admin/steps/${step.id}`))) await refresh(neighbor?.id ?? null);
        }, false, true),
      ),
      textInput(`title-${step.id}`, parent ? 'Nombre del subpaso' : 'Nombre del paso', step.title, async (value) => {
        await update('title')(value);
        await refresh(step.id);
      }, { required: true }),
      TEXT_FIELDS.map(([field, label]) => textInput(`${field}-${step.id}`, label, step[field], update(field), { multiline: true })),
      imagesSection(step),
      animationsSection(step),
      section('piezas', 'Ajustes de la animación y piezas', piecesHolder),
      instrumentsSection(step),
      !parent && h('form', {
        class: 'edit-add',
        onSubmit: async (event) => {
          event.preventDefault();
          let created;
          const ok = await save(async () => {
            created = await api('POST', '/api/admin/steps', { parent_id: step.id, title: newSub.value });
          });
          if (ok) await refresh(created.id);
        },
      }, newSub, h('button', { class: 'btn', type: 'submit' }, icon('plus'), 'Subpaso')),
    );
  }

  function addStepForm() {
    const input = h('input', { class: 'input', maxlength: 200, placeholder: 'Título del paso nuevo', 'aria-label': 'Título del paso nuevo' });
    return h('form', {
      class: 'edit-add',
      onSubmit: async (event) => {
        event.preventDefault();
        let created;
        const ok = await save(async () => {
          created = await api('POST', '/api/admin/steps', { parent_id: null, title: input.value });
        });
        if (ok) await refresh(created.id);
      },
    }, input, h('button', { class: 'btn', type: 'submit' }, icon('plus'), 'Agregar paso'));
  }

  await updateStatus();
  paintPieces();
  return { bar, techniqueForm, stepForm, addStepForm, setPieces, setScene, paintPieces, focusPiece };
}
