// Edición de un paso: contenido, instrumental, animaciones y material complementario.
import { h, confirmDialog, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { icon } from '../components/icons.js';
import { notFoundView } from '../views/notFound.js';
import { assetField, loadAssets, selectedAsset } from './assetField.js';
import { adminView, guarded } from './shell.js';

const TEXT_FIELDS = [
  ['description', 'Descripción', true],
  ['recommendations', 'Recomendaciones para el instrumentador', true],
];

function findStep(doc, id) {
  for (const [i, step] of doc.steps.entries()) {
    if (step.id === id) return { step, label: `Paso ${i + 1}` };
    const j = step.children.findIndex((child) => child.id === id);
    if (j >= 0) return { step: step.children[j], label: `Subpaso ${i + 1}.${j + 1}` };
  }
  return null;
}

export async function stepEditorView(stepId) {
  let missing = false;
  const view = await adminView('/admin', 'Editar paso', async ({ doc, refresh }) => {
    const found = findStep(doc, stepId);
    if (!found) {
      missing = true;
      return h('div', {});
    }
    const { step, label } = found;
    const assets = await loadAssets();
    const assetName = (id) => assets.find((asset) => asset.id === id)?.filename || 'Archivo no disponible';
    const run = (fn, success) => guarded(async () => { await fn(); await refresh(); }, success);

    // --- Contenido ---
    const inputs = {};
    const title = h('input', { class: 'input', id: 'title', value: step.title, required: true, maxlength: 200 });
    const contentForm = h('form', {
      class: 'panel',
      onSubmit: async (event) => {
        event.preventDefault();
        // Los campos que ya no se editan quedan vacíos: su texto se unió en la descripción.
        const payload = { title: title.value, is_sample: false, objective: '', procedure: '', observations: '' };
        for (const [field] of TEXT_FIELDS) payload[field] = inputs[field].value;
        try {
          await api('PUT', `/api/admin/steps/${stepId}`, payload);
          toast('Guardado en el borrador.');
          await refresh();
        } catch (error) {
          toast(error.message, true);
        }
      },
    },
      h('div', { class: 'panel-head' }, h('h2', {}, 'Contenido')),
      h('div', { class: 'panel-body' },
        h('div', { class: 'editor-grid' },
          h('div', { class: 'field editor-wide' }, h('label', { for: 'title' }, 'Nombre del paso'), title),
          TEXT_FIELDS.map(([field, fieldLabel, wide]) => {
            inputs[field] = h('textarea', { class: 'textarea', id: field, rows: wide ? 6 : 4 }, step[field]);
            return h('div', { class: `field${wide ? ' editor-wide' : ''}` }, h('label', { for: field }, fieldLabel), inputs[field]);
          }),
        ),
        h('div', { class: 'editor-footer' },
          h('button', { class: 'btn btn-primary', type: 'submit' }, 'Guardar el contenido'),
        ),
      ),
    );

    // --- Animaciones ---
    const newAnimAsset = assetField({ id: 'anim-asset', label: 'Modelo 3D o animación', kind: 'model', assets, emptyLabel: 'Selecciona un archivo' });
    const newAnimTitle = h('input', { class: 'input', id: 'anim-title', maxlength: 200, required: true });
    const newAnimDesc = h('input', { class: 'input', id: 'anim-desc' });
    const animationsPanel = h('section', { class: 'panel' },
      h('div', { class: 'panel-head' }, h('h2', {}, 'Modelos y animaciones del visor')),
      h('div', { class: 'panel-body' },
        step.animations.length === 0
          ? h('p', { class: 'empty-note' }, 'Sin modelos. El visor mostrará «Visualización 3D próximamente».')
          : h('ul', { class: 'rows' }, step.animations.map((animation, index) => h('li', {},
              h('div', { class: 'rows-main' }, h('strong', {}, animation.title), h('span', {}, [assetName(animation.asset_id), animation.description].filter(Boolean).join(' · '))),
              h('div', { class: 'rows-actions' },
                h('button', { class: 'btn btn-text btn-icon', type: 'button', title: 'Subir', 'aria-label': `Subir ${animation.title}`, disabled: index === 0, onClick: run(() => api('POST', `/api/admin/animations/${animation.id}/move`, { direction: 'up' })) }, icon('up')),
                h('button', { class: 'btn btn-text btn-icon', type: 'button', title: 'Bajar', 'aria-label': `Bajar ${animation.title}`, disabled: index === step.animations.length - 1, onClick: run(() => api('POST', `/api/admin/animations/${animation.id}/move`, { direction: 'down' })) }, icon('down')),
                h('button', {
                  class: 'btn btn-text btn-icon', type: 'button', title: 'Editar', 'aria-label': `Editar ${animation.title}`,
                  onClick: () => {
                    newAnimTitle.value = animation.title;
                    newAnimDesc.value = animation.description;
                    newAnimAsset.querySelector('select').value = animation.asset_id;
                    animationForm.dataset.editing = animation.id;
                    animationSubmit.textContent = 'Guardar los cambios';
                    newAnimTitle.focus();
                  },
                }, icon('edit')),
                h('button', { class: 'btn btn-text btn-icon btn-danger', type: 'button', title: 'Quitar', 'aria-label': `Quitar ${animation.title}`, onClick: run(() => api('DELETE', `/api/admin/animations/${animation.id}`), 'Quitado del paso.') }, icon('trash')),
              ),
            ))),
      ),
    );
    const animationSubmit = h('button', { class: 'btn', type: 'submit' }, icon('plus'), 'Agregar al visor');
    const animationForm = h('form', {
      class: 'inline-form',
      style: 'margin:0 var(--card-pad) var(--card-pad)',
      onSubmit: async (event) => {
        event.preventDefault();
        const payload = { asset_id: selectedAsset(newAnimAsset), title: newAnimTitle.value, description: newAnimDesc.value };
        const editing = animationForm.dataset.editing;
        await run(() => (editing
          ? api('PUT', `/api/admin/animations/${editing}`, payload)
          : api('POST', `/api/admin/steps/${stepId}/animations`, payload)), 'Guardado en el borrador.')();
      },
    },
      h('div', { class: 'is-wide' }, newAnimAsset),
      h('div', { class: 'field' }, h('label', { for: 'anim-title' }, 'Título'), newAnimTitle),
      h('div', { class: 'field' }, h('label', { for: 'anim-desc' }, 'Descripción'), newAnimDesc),
      h('div', { class: 'inline-actions' }, animationSubmit),
    );
    animationsPanel.append(animationForm);

    // --- Instrumental ---
    const assigned = new Set(step.instrument_ids);
    const instrumentsPanel = h('section', { class: 'panel' },
      h('div', { class: 'panel-head' },
        h('h2', {}, 'Instrumental utilizado'),
        h('a', { class: 'panel-link', href: '/admin/instrumental' }, 'Gestionar el instrumental'),
      ),
      h('div', { class: 'panel-body' },
        doc.instruments.length === 0
          ? h('p', { class: 'empty-note' }, 'Aún no hay instrumentos registrados.')
          : h('div', { class: 'checklist' }, doc.instruments.map((item) => h('label', { class: 'check' },
              h('input', {
                type: 'checkbox',
                checked: assigned.has(item.id),
                onChange: guarded(async (event) => {
                  if (event.target.checked) assigned.add(item.id);
                  else assigned.delete(item.id);
                  await api('PUT', `/api/admin/steps/${stepId}/instruments`, { ids: [...assigned] });
                  await refresh();
                }, 'Instrumental actualizado.'),
              }),
              h('span', {}, item.name),
            ))),
      ),
    );

    // --- Material complementario ---
    const mediaAsset = assetField({ id: 'media-asset', label: 'Imagen, documento o video', kind: 'any', assets, emptyLabel: 'Selecciona un archivo' });
    const mediaCaption = h('input', { class: 'input', id: 'media-caption' });
    const mediaPanel = h('section', { class: 'panel' },
      h('div', { class: 'panel-head' }, h('h2', {}, 'Imágenes, documentos y material audiovisual')),
      h('div', { class: 'panel-body' },
        step.media.length === 0
          ? h('p', { class: 'empty-note' }, 'Sin material complementario.')
          : h('ul', { class: 'rows' }, step.media.map((item) => h('li', {},
              h('div', { class: 'rows-main' }, h('strong', {}, item.caption || assetName(item.asset_id)), h('span', {}, assetName(item.asset_id))),
              h('div', { class: 'rows-actions' },
                h('button', { class: 'btn btn-text btn-icon btn-danger', type: 'button', title: 'Quitar', 'aria-label': `Quitar ${assetName(item.asset_id)}`, onClick: run(() => api('DELETE', `/api/admin/media/${item.id}`), 'Quitado del paso.') }, icon('trash')),
              ),
            ))),
        h('form', {
          class: 'inline-form',
          onSubmit: async (event) => {
            event.preventDefault();
            await run(() => api('POST', `/api/admin/steps/${stepId}/media`, { asset_id: selectedAsset(mediaAsset), caption: mediaCaption.value }), 'Agregado al borrador.')();
          },
        },
          h('div', { class: 'is-wide' }, mediaAsset),
          h('div', { class: 'field is-wide' }, h('label', { for: 'media-caption' }, 'Texto que lo acompaña'), mediaCaption),
          h('div', { class: 'inline-actions' }, h('button', { class: 'btn', type: 'submit' }, icon('plus'), 'Agregar')),
        ),
      ),
    );

    return h('div', { class: 'editor-stack' },
      h('div', { class: 'admin-title-row', style: 'margin-bottom:0' },
        h('div', {},
          h('a', { class: 'back-link', href: '/admin' }, 'Volver a pasos y subpasos'),
          h('h1', { class: 'page-title', style: 'margin-top:8px' }, `${label}: ${step.title}`),
        ),
        h('button', {
          class: 'btn btn-danger',
          type: 'button',
          onClick: async () => {
            const ok = await confirmDialog({ title: 'Eliminar', message: `Se eliminará «${step.title}» y su contenido del borrador.`, confirm: 'Eliminar', danger: true });
            if (!ok) return;
            await guarded(async () => {
              await api('DELETE', `/api/admin/steps/${stepId}`);
              const { navigate } = await import('../core/router.js');
              navigate('/admin');
            }, 'Eliminado del borrador.')();
          },
        }, icon('trash'), 'Eliminar'),
      ),
      contentForm,
      animationsPanel,
      instrumentsPanel,
      mediaPanel,
    );
  });
  return missing ? notFoundView() : view;
}
