// Pasos y subpasos: crear, renombrar, ordenar, mover y eliminar.
import { h, confirmDialog } from '../core/dom.js';
import { api } from '../core/api.js';
import { icon } from '../components/icons.js';
import { adminView, guarded } from './shell.js';

function iconButton(name, label, onClick, disabled = false, danger = false) {
  return h('button', { class: `btn btn-text btn-icon${danger ? ' btn-danger' : ''}`, type: 'button', title: label, 'aria-label': label, disabled, onClick }, icon(name));
}

export function structureView() {
  return adminView('/admin', 'Pasos y subpasos', ({ doc, refresh }) => {
    const act = (fn, success) => guarded(async () => { await fn(); await refresh(); }, success);

    const move = (id, direction) => act(() => api('POST', `/api/admin/steps/${id}/move`, { direction }));
    const remove = (step, kind) => async () => {
      const ok = await confirmDialog({
        title: `Eliminar ${kind}`,
        message: step.children?.length
          ? `Se eliminará «${step.title}» con sus ${step.children.length} subpasos y su contenido.`
          : `Se eliminará «${step.title}» y su contenido.`,
        confirm: 'Eliminar',
        danger: true,
      });
      if (ok) await act(() => api('DELETE', `/api/admin/steps/${step.id}`), 'Eliminado del borrador.')();
    };

    function addForm({ parentId, placeholder, buttonLabel, className }) {
      const input = h('input', { class: 'input', type: 'text', placeholder, 'aria-label': placeholder, required: true, maxlength: 200 });
      return h('form', {
        class: className,
        onSubmit: async (event) => {
          event.preventDefault();
          await act(() => api('POST', '/api/admin/steps', { parent_id: parentId, title: input.value }), 'Agregado al borrador.')();
        },
      }, input, h('button', { class: 'btn', type: 'submit' }, icon('plus'), buttonLabel));
    }

    function parentSelect(child, currentParent) {
      return h('select', {
        class: 'select',
        style: 'min-height:32px;width:auto;max-width:170px;padding:2px 6px;font-size:13px',
        'aria-label': `Mover «${child.title}» a otro paso`,
        title: 'Mover a otro paso',
        onChange: (event) => {
          act(() => api('POST', `/api/admin/steps/${child.id}/move`, { parent_id: Number(event.target.value) }), 'Subpaso movido.')();
        },
      }, doc.steps.map((step, i) => h('option', { value: step.id, selected: step.id === currentParent.id }, `Paso ${i + 1}`)));
    }

    return h('div', {},
      h('div', { class: 'admin-title-row' },
        h('div', {},
          h('h1', { class: 'page-title' }, 'Pasos y subpasos'),
          h('p', { class: 'page-sub' }, `${doc.steps.length} pasos y ${doc.steps.reduce((sum, step) => sum + step.children.length, 0)} subpasos en el borrador.`),
        ),
      ),
      doc.steps.length === 0 && h('p', { class: 'empty-note' }, 'Aún no hay pasos. Agrega el primero.'),
      doc.steps.map((step, i) => h('section', { class: 'panel structure-step' },
        h('div', { class: 'structure-row' },
          h('span', { class: 'structure-number' }, i + 1),
          h('a', { class: 'structure-title', href: `/admin/paso/${step.id}` }, step.title),
          h('div', { class: 'structure-actions' },
            iconButton('up', `Subir «${step.title}»`, move(step.id, 'up'), i === 0),
            iconButton('down', `Bajar «${step.title}»`, move(step.id, 'down'), i === doc.steps.length - 1),
            h('a', { class: 'btn btn-text btn-icon', href: `/admin/paso/${step.id}`, title: `Editar «${step.title}»`, 'aria-label': `Editar «${step.title}»` }, icon('edit')),
            iconButton('trash', `Eliminar «${step.title}»`, remove(step, 'el paso'), false, true),
          ),
        ),
        h('div', { class: 'structure-subs' },
          step.children.map((child, j) => h('div', { class: 'structure-row' },
            h('span', { class: 'structure-number' }, `${i + 1}.${j + 1}`),
            h('a', { class: 'structure-title', href: `/admin/paso/${child.id}` }, child.title),
            h('div', { class: 'structure-actions' },
              parentSelect(child, step),
              iconButton('up', `Subir «${child.title}»`, move(child.id, 'up'), j === 0),
              iconButton('down', `Bajar «${child.title}»`, move(child.id, 'down'), j === step.children.length - 1),
              h('a', { class: 'btn btn-text btn-icon', href: `/admin/paso/${child.id}`, title: `Editar «${child.title}»`, 'aria-label': `Editar «${child.title}»` }, icon('edit')),
              iconButton('trash', `Eliminar «${child.title}»`, remove(child, 'el subpaso'), false, true),
            ),
          )),
        ),
        addForm({ parentId: step.id, placeholder: `Nuevo subpaso en el paso ${i + 1}`, buttonLabel: 'Subpaso', className: 'structure-add' }),
      )),
      addForm({ parentId: null, placeholder: 'Título del nuevo paso', buttonLabel: 'Agregar paso', className: 'add-row' }),
    );
  });
}
