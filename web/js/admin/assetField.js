// Selector de archivo reutilizable: elegir uno ya cargado o subir uno nuevo.
import { h, replace, toast } from '../core/dom.js';
import { api, uploadFile } from '../core/api.js';
import { icon } from '../components/icons.js';

const ACCEPT = {
  model: '.stl,.glb,.gltf',
  image: '.png,.jpg,.jpeg,.webp',
  any: '.png,.jpg,.jpeg,.webp,.pdf,.mp4,.webm',
};

export async function loadAssets() {
  return (await api('GET', '/api/admin/assets')).assets;
}

export function assetField({ id, label, kind, assets, value = null, emptyLabel = 'Ninguno', onChange }) {
  const matches = (asset) => (kind === 'any' ? asset.kind !== 'model' : asset.kind === kind);
  const select = h('select', { class: 'select', id, onChange: () => onChange?.(select.value ? Number(select.value) : null) });

  function paintOptions(selected) {
    replace(select,
      h('option', { value: '' }, emptyLabel),
      assets.filter(matches).map((asset) => h('option', { value: asset.id, selected: asset.id === selected }, asset.filename)),
    );
    select.value = selected ?? '';
  }
  paintOptions(value);

  const state = h('span', { class: 'upload-state', role: 'status' });
  const picker = h('input', {
    type: 'file',
    accept: ACCEPT[kind],
    hidden: true,
    onChange: async () => {
      const file = picker.files[0];
      if (!file) return;
      try {
        state.textContent = 'Cargando: 0 %';
        const asset = await uploadFile(file, { onProgress: (percent) => { state.textContent = `Cargando: ${percent} %`; } });
        if (!assets.some((item) => item.id === asset.id)) assets.unshift(asset);
        paintOptions(asset.id);
        state.textContent = asset.reused ? 'Este archivo ya existía; se reutilizó.' : 'Archivo cargado.';
        onChange?.(asset.id);
      } catch (error) {
        state.textContent = '';
        toast(error.message, true);
      }
      picker.value = '';
    },
  });

  return h('div', { class: 'field' },
    h('label', { for: id }, label),
    h('div', { class: 'asset-field' },
      select,
      h('button', { class: 'btn', type: 'button', onClick: () => picker.click() }, icon('upload'), 'Subir'),
      picker,
    ),
    state,
  );
}

export function selectedAsset(field) {
  const value = field.querySelector('select').value;
  return value ? Number(value) : null;
}
