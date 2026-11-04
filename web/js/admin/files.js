// Modelos 3D y demás archivos: cargar, reemplazar y eliminar.
import { h, confirmDialog, formatBytes, replace, toast } from '../core/dom.js';
import { api, uploadFile } from '../core/api.js';
import { icon } from '../components/icons.js';
import { loadAssets } from './assetField.js';
import { adminView, guarded } from './shell.js';

const KINDS = { model: 'Modelo 3D', image: 'Imagen', document: 'Documento', video: 'Video' };
const ACCEPT = '.stl,.glb,.gltf,.png,.jpg,.jpeg,.webp,.pdf,.mp4,.webm';

export function filesView() {
  return adminView('/admin/archivos', 'Modelos y archivos', async ({ refresh }) => {
    const assets = await loadAssets();
    const progressEl = h('p', { class: 'upload-state', role: 'status' });

    async function uploadAll(files) {
      let index = 0;
      for (const file of files) {
        index += 1;
        const prefix = files.length > 1 ? `Archivo ${index} de ${files.length}. ` : '';
        try {
          progressEl.textContent = `${prefix}Cargando ${file.name}: 0 %`;
          const result = await uploadFile(file, { onProgress: (percent) => { progressEl.textContent = `${prefix}Cargando ${file.name}: ${percent} %`; } });
          if (result.reused) toast(`«${file.name}» ya existía como «${result.filename}»; no se duplicó.`);
        } catch (error) {
          toast(`${file.name}: ${error.message}`, true);
        }
      }
      await refresh();
    }

    const picker = h('input', { type: 'file', multiple: true, accept: ACCEPT, hidden: true, onChange: () => uploadAll([...picker.files]) });
    const zone = h('div', {
      class: 'dropzone',
      onDragover: (event) => { event.preventDefault(); zone.classList.add('is-over'); },
      onDragleave: () => zone.classList.remove('is-over'),
      onDrop: (event) => {
        event.preventDefault();
        zone.classList.remove('is-over');
        uploadAll([...event.dataTransfer.files]);
      },
    },
      h('div', {},
        h('p', {}, 'Arrastra aquí los archivos: STL, GLB, GLTF, PNG, JPG, WEBP, PDF, MP4 o WEBM, hasta 400 MB cada uno.'),
        progressEl,
      ),
      h('button', { class: 'btn', type: 'button', onClick: () => picker.click() }, icon('upload'), 'Elegir archivos'),
      picker,
    );

    function replacer(asset) {
      const input = h('input', {
        type: 'file',
        hidden: true,
        accept: ACCEPT,
        onChange: guarded(async () => {
          progressEl.textContent = `Reemplazando ${asset.filename}…`;
          await uploadFile(input.files[0], { replaceId: asset.id, onProgress: (percent) => { progressEl.textContent = `Reemplazando ${asset.filename}: ${percent} %`; } });
          await refresh();
        }, 'Reemplazado en el borrador. Publica para que se vea.'),
      });
      return h('span', {}, input, h('button', { class: 'btn', type: 'button', onClick: () => input.click() }, 'Reemplazar'));
    }

    async function remove(asset) {
      const ok = await confirmDialog({ title: 'Eliminar el archivo', message: `Se eliminará «${asset.filename}» de forma definitiva.`, confirm: 'Eliminar', danger: true });
      if (ok) await guarded(async () => { await api('DELETE', `/api/admin/assets/${asset.id}`); await refresh(); }, 'Archivo eliminado.')();
    }

    const table = h('div', { class: 'panel', style: 'margin-top:var(--gap)' });
    if (assets.length) {
      replace(table, h('div', { class: 'table-wrap' }, h('table', { class: 'table' },
        h('thead', {}, h('tr', {},
          h('th', {}, 'Archivo'),
          h('th', { class: 'is-hide-phone' }, 'Tipo'),
          h('th', { class: 'num is-hide-phone' }, 'Tamaño'),
          h('th', { class: 'num' }, 'Usos'),
          h('th', {}, h('span', { class: 'sr-only' }, 'Acciones')),
        )),
        h('tbody', {}, assets.map((asset) => h('tr', {},
          h('td', { class: 'is-name' }, h('a', { href: asset.url, target: '_blank', rel: 'noopener', style: 'text-decoration:none' }, asset.filename)),
          h('td', { class: 'is-hide-phone' }, KINDS[asset.kind]),
          h('td', { class: 'num is-hide-phone' }, formatBytes(asset.size)),
          h('td', { class: 'num' }, asset.uses),
          h('td', { class: 'is-actions' }, replacer(asset), ' ', h('button', { class: 'btn btn-danger', type: 'button', onClick: () => remove(asset) }, 'Eliminar')),
        ))),
      )));
    } else {
      replace(table, h('p', { class: 'empty-note', style: 'margin:16px' }, 'Aún no hay archivos cargados.'));
    }

    return h('div', {},
      h('div', { class: 'admin-title-row' },
        h('div', {},
          h('h1', { class: 'page-title' }, 'Modelos y archivos'),
          h('p', { class: 'page-sub' }, 'Cada archivo se guarda una sola vez y se puede usar en muchos pasos. Al reemplazar uno, todos sus usos cambian en el borrador.'),
        ),
      ),
      zone,
      table,
    );
  });
}
