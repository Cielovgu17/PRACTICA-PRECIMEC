// Información general de la técnica.
import { h, toast } from '../core/dom.js';
import { api } from '../core/api.js';
import { assetField, loadAssets, selectedAsset } from './assetField.js';
import { adminView } from './shell.js';

export function generalView() {
  return adminView('/admin/general', 'Información general', async ({ doc, refresh }) => {
    const { technique } = doc;
    const assets = await loadAssets();
    const name = h('input', { class: 'input', id: 'tech-name', value: technique.name, required: true, maxlength: 200 });
    const platform = h('input', { class: 'input', id: 'platform', value: technique.platform_name, required: true, maxlength: 200 });
    const company = h('input', { class: 'input', id: 'company', value: technique.company, required: true, maxlength: 200 });
    const intro = h('textarea', { class: 'textarea', id: 'intro', rows: 5 }, technique.intro);
    const system = h('textarea', { class: 'textarea', id: 'system', rows: 5 }, technique.system_info);
    const sample = h('input', { type: 'checkbox', checked: technique.is_sample });
    const cover = assetField({ id: 'cover', label: 'Imagen de portada', kind: 'image', assets, value: technique.cover_asset_id });
    const model = assetField({ id: 'cover-model', label: 'Modelo 3D de portada', kind: 'model', assets, value: technique.model_asset_id });

    return h('div', {},
      h('div', { class: 'admin-title-row' },
        h('div', {},
          h('h1', { class: 'page-title' }, 'Información general'),
          h('p', { class: 'page-sub' }, 'Si eliges un modelo 3D de portada, se muestra en lugar de la imagen.'),
        ),
      ),
      h('form', {
        class: 'panel',
        onSubmit: async (event) => {
          event.preventDefault();
          try {
            await api('PUT', '/api/admin/technique', {
              name: name.value,
              platform_name: platform.value,
              company: company.value,
              intro: intro.value,
              system_info: system.value,
              is_sample: sample.checked,
              cover_asset_id: selectedAsset(cover),
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
            h('div', { class: 'field' }, h('label', { for: 'tech-name' }, 'Nombre de la técnica'), name),
            h('div', { class: 'field' }, h('label', { for: 'platform' }, 'Nombre de la plataforma'), platform),
            h('div', { class: 'field' }, h('label', { for: 'company' }, 'Empresa'), company),
            h('div', {}),
            h('div', { class: 'field editor-wide' }, h('label', { for: 'intro' }, 'Descripción introductoria'), intro),
            h('div', { class: 'field editor-wide' }, h('label', { for: 'system' }, 'Información general del sistema de osteosíntesis'), system),
            cover,
            model,
          ),
          h('div', { class: 'editor-footer' },
            h('label', { class: 'check' }, sample, h('span', {}, 'Mostrar la etiqueta «Por validar»')),
            h('button', { class: 'btn btn-primary', type: 'submit' }, 'Guardar'),
          ),
        ),
      ),
    );
  });
}
