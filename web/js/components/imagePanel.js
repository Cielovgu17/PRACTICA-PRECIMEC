// Panel de imágenes: ocupa el lugar del visor 3D en los pasos que se explican con ilustraciones.
import { h, replace } from '../core/dom.js';

// images: [{ title, asset: { url, filename } }]
export function createImagePanel({ images }) {
  const stage = h('div', { class: 'viewer-canvas' });

  function show(image) {
    replace(stage, h('a', {
      class: 'viewer-image',
      href: image.asset.url,
      target: '_blank',
      rel: 'noopener',
      title: 'Ver la imagen en grande',
      'aria-label': `${image.title}. Abrir la imagen en grande en otra pestaña`,
    },
      h('img', { src: image.asset.url, alt: '' }),
    ));
  }

  const thumbs = images.length > 1 ? h('div', { class: 'viewer-sources', role: 'group', 'aria-label': 'Imágenes de este paso' },
    images.map((image, index) => h('button', {
      class: 'viewer-source',
      type: 'button',
      'aria-pressed': index === 0 ? 'true' : 'false',
      onClick: (event) => {
        thumbs.querySelectorAll('.viewer-source').forEach((el) => el.setAttribute('aria-pressed', 'false'));
        event.currentTarget.setAttribute('aria-pressed', 'true');
        show(image);
      },
    }, image.title)),
  ) : null;

  show(images[0]);
  const root = h('div', { class: 'viewer', role: 'region', 'aria-label': 'Ilustración del paso' }, thumbs, stage);
  // Las mismas funciones del visor 3D, para que la pantalla los trate por igual.
  root.setNote = () => {};
  root.highlight = () => {};
  root.relabel = () => {};
  root.destroy = () => {};
  return root;
}
