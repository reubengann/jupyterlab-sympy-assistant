import { Dialog, showDialog } from '@jupyterlab/apputils';
import { Widget } from '@lumino/widgets';
import { IEquationInput, IEquationRecord } from '../types';

class EquationFormWidget extends Widget {
  constructor(initial?: Partial<IEquationInput>) {
    super();
    this.addClass('jp-SympyEquationModal');

    const tags = (initial?.tags ?? []).join(', ');
    this.node.innerHTML = `
      <div class="jp-SympyEquationModal-row">
        <label>Name</label>
        <input name="name" type="text" value="${escapeHtml(initial?.name ?? '')}" />
      </div>
      <div class="jp-SympyEquationModal-row">
        <label>SymPy</label>
        <textarea name="sympy">${escapeHtml(initial?.sympy ?? '')}</textarea>
      </div>
      <div class="jp-SympyEquationModal-row">
        <label>LaTeX (optional)</label>
        <textarea name="latex">${escapeHtml(initial?.latex ?? '')}</textarea>
      </div>
      <div class="jp-SympyEquationModal-row">
        <label>Description (optional)</label>
        <textarea name="description">${escapeHtml(initial?.description ?? '')}</textarea>
      </div>
      <div class="jp-SympyEquationModal-row">
        <label>Tags (comma-separated)</label>
        <input name="tags" type="text" value="${escapeHtml(tags)}" />
      </div>
    `;
  }

  getValue(): IEquationInput {
    const get = (selector: string): string => {
      const element = this.node.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement | null;
      return (element?.value ?? '').trim();
    };
    const tags = get('input[name="tags"]')
      .split(',')
      .map(part => part.trim())
      .filter(Boolean);

    return {
      name: get('input[name="name"]'),
      sympy: get('textarea[name="sympy"]'),
      latex: get('textarea[name="latex"]'),
      description: get('textarea[name="description"]'),
      tags
    };
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export async function showEquationModal(
  initial?: IEquationRecord
): Promise<IEquationInput | null> {
  const form = new EquationFormWidget(initial);
  const result = await showDialog({
    title: initial ? 'Edit Equation' : 'Add Equation',
    body: form,
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'Save' })]
  });

  if (!result.button.accept) {
    return null;
  }

  return form.getValue();
}

class LatexInputWidget extends Widget {
  constructor(initialLatex = '') {
    super();
    this.addClass('jp-SympyEquationModal');
    this.node.innerHTML = `
      <div class="jp-SympyEquationModal-row">
        <label>LaTeX</label>
        <textarea name="latex">${escapeHtml(initialLatex)}</textarea>
      </div>
    `;
  }

  getLatex(): string {
    const textarea = this.node.querySelector(
      'textarea[name="latex"]'
    ) as HTMLTextAreaElement | null;
    return (textarea?.value ?? '').trim();
  }
}

export async function showLatexInputModal(initialLatex = ''): Promise<string | null> {
  const form = new LatexInputWidget(initialLatex);
  const result = await showDialog({
    title: 'Insert from LaTeX',
    body: form,
    buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'Convert & Insert' })]
  });

  if (!result.button.accept) {
    return null;
  }

  return form.getLatex();
}
