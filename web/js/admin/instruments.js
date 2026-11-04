// Gestión del instrumental. Un mismo instrumento se puede asociar a varios pasos.
import { h, confirmDialog, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { navigate } from '../core/router.js';
import { icon } from '../components/icons.js';
import { notFoundView } from '../views/notFound.js';
import { assetField, loadAssets, selectedAsset } from './assetField.js';
import { adminView, guarded } from './shell.js';

function countSteps(doc, id) {
  let total = 0;
  for (const step of doc.steps) {
    if (step.instrument_ids.includes(id)) total += 1;
    for (const child of step.children) if (child.instrument_ids.includes(id)) total += 1;
  }
  return total;
}

export function adminInstrumentsView() {
  return adminView('/admin/instrumental', 'Instrumental', ({ doc, refresh }) => {
    const name = h('input', { class: 'input', 'aria-label': 'Nombre del nuevo instrumento', placeholder: 'Nombre del nuevo instrumento', required: true, maxlength: 200 });
    return h('div', {},
      h('div', { class: 'admin-title-row' },
        h('div', {},
          h('h1', { class: 'page-title' }, 'Instrumental'),
          h('p', { class: 'page-sub' }, `${doc.instruments.length} instrumentos en el borrador. Se asocian a los pasos desde la edición de cada paso.`),
        ),
      ),
      h('section', { class: 'panel' },
        h('div', { class: 'table-wrap' },
          h('table', { class: 'table' },
            h('thead', {}, h('tr', {},
              h('th', {}, 'Instrumento'),
              h('th', { class: 'is-hide-phone' }, 'Modelo 3D'),
              h('th', { class: 'num' }, 'Pasos'),
              h('th', {}, 'Estado'),
              h('th', {}, h('span', { class: 'sr-only' }, 'Acciones')),
            )),
            h('tbody', {}, doc.instruments.map((item) => h('tr', {},
              h('td', { class: 'is-name' }, h('a', { href: `/admin/instrumental/${item.id}`, style: 'text-decoration:none' }, item.name)),
              h('td', { class: 'is-hide-phone' }, item.model_asset_id ? 'Asignado' : '—'),
              h('td', { class: 'num' }, countSteps(doc, item.id)),
              h('td', {}, h('span', { class: `pill ${item.is_verified ? 'pill-ok' : 'pill-sample'}` }, item.is_verified ? 'Verificado' : 'Por verificar')),
              h('td', { class: 'is-actions' }, h('a', { class: 'btn', href: `/admin/instrumental/${item.id}` }, 'Editar')),
            ))),
          ),
        ),
      ),
      h('form', {
        class: 'add-row',
        onSubmit: guarded(async (event) => {
          event.preventDefault();
          const { id } = await api('POST', '/api/admin/instruments', { name: name.value });
          navigate(`/admin/instrumental/${id}`);
        }, 'Instrumento agregado.'),
      }, name, h('button', { class: 'btn', type: 'submit' }, icon('plus'), 'Agregar')),
    );
  });
}

export async function instrumentEditorView(id) {
  let missing = false;
  const view = await adminView('/admin/instrumental', 'Editar instrumento', async ({ doc, refresh }) => {
    const item = doc.instruments.find((row) => row.id === id);
    if (!item) {
      missing = true;
      return h('div', {});
    }
    const assets = await loadAssets();
    const name = h('input', { class: 'input', id: 'name', value: item.name, required: true, maxlength: 200 });
    const description = h('textarea', { class: 'textarea', id: 'description' }, item.description);
    const fn = h('textarea', { class: 'textarea', id: 'function' }, item.function);
    const verified = h('input', { type: 'checkbox', checked: item.is_verified });
    const image = assetField({ id: 'image', label: 'Imagen o render', kind: 'image', assets, value: item.image_asset_id });
    const model = assetField({ id: 'model', label: 'Modelo 3D', kind: 'model', assets, value: item.model_asset_id });

    return h('div', { class: 'editor-stack' },
      h('div', { class: 'admin-title-row', style: 'margin-bottom:0' },
        h('div', {},
          h('a', { class: 'back-link', href: '/admin/instrumental' }, 'Volver al instrumental'),
          h('h1', { class: 'page-title', style: 'margin-top:8px' }, item.name),
        ),
        h('button', {
          class: 'btn btn-danger',
          type: 'button',
          onClick: async () => {
            const uses = countSteps(doc, id);
            const ok = await confirmDialog({
              title: 'Eliminar el instrumento',
              message: uses ? `«${item.name}» se quitará de ${uses} paso(s).` : `Se eliminará «${item.name}» del borrador.`,
              confirm: 'Eliminar',
              danger: true,
            });
            if (ok) {
              await guarded(async () => {
                await api('DELETE', `/api/admin/instruments/${id}`);
                navigate('/admin/instrumental');
              }, 'Instrumento eliminado.')();
            }
          },
        }, icon('trash'), 'Eliminar'),
      ),
      h('form', {
        class: 'panel',
        onSubmit: async (event) => {
          event.preventDefault();
          try {
            await api('PUT', `/api/admin/instruments/${id}`, {
              name: name.value,
              description: description.value,
              function: fn.value,
              is_verified: verified.checked,
              image_asset_id: selectedAsset(image),
              model_asset_id: selectedAsset(model),
            });
            toast('Guardado en el borrador.');
            await refresh();
          } catch (error) {
            toast(error.message, true);
          }
        },
      },
        h('div', { class: 'panel-body', style: 'padding-top:var(--card-pad)' },
          h('div', { class: 'editor-grid' },
            h('div', { class: 'field editor-wide' }, h('label', { for: 'name' }, 'Nombre'), name),
            h('div', { class: 'field' }, h('label', { for: 'description' }, 'Descripción breve'), description),
            h('div', { class: 'field' }, h('label', { for: 'function' }, 'Función dentro de la técnica'), fn),
            image,
            model,
          ),
          h('div', { class: 'editor-footer' },
            h('label', { class: 'check' }, verified, h('span', {}, 'Información verificada por PRECIMEC')),
            h('button', { class: 'btn btn-primary', type: 'submit' }, 'Guardar el instrumento'),
          ),
        ),
      ),
    );
  });
  return missing ? notFoundView() : view;
}
