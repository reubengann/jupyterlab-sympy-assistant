import { Dialog, showDialog } from '@jupyterlab/apputils';
import { Widget } from '@lumino/widgets';
import { IEquationInput, IEquationRecord } from '../types';

function wireTextareaEnterBehavior(textarea: HTMLTextAreaElement): void {
  const swallowEnter = (event: KeyboardEvent) => {
    if (event.key !== 'Enter') {
      return;
    }
    event.stopPropagation();
  };

  textarea.addEventListener('keyup', swallowEnter);
  textarea.addEventListener('keypress', swallowEnter);
  textarea.addEventListener('keydown', event => {
    if (event.key !== 'Enter') {
      return;
    }
    event.stopPropagation();
    if (textarea.name !== 'sympy') {
      return;
    }

    // Force newline insertion in case dialog-level handlers block default behavior.
    event.preventDefault();
    const start = textarea.selectionStart ?? textarea.value.length;
    const end = textarea.selectionEnd ?? textarea.value.length;
    textarea.setRangeText('\n', start, end, 'end');
  });
}

function isTextAreaInside(root: HTMLElement, target: EventTarget | null): target is HTMLTextAreaElement {
  return target instanceof HTMLTextAreaElement && root.contains(target);
}

class EquationFormWidget extends Widget {
  private readonly documentKeyHandler: (event: KeyboardEvent) => void;

  constructor(initial?: Partial<IEquationInput>) {
    super();
    this.addClass('jp-SympyEquationModal');
    this.node.setAttribute('data-lm-suppress-shortcuts', 'true');

    const tags = (initial?.tags ?? []).join(', ');
    this.node.innerHTML = `
      <div class="jp-SympyEquationModal-row">
        <label>Name</label>
        <input name="name" type="text" value="${escapeHtml(initial?.name ?? '')}" />
      </div>
      <div class="jp-SympyEquationModal-row">
        <label>SymPy</label>
        <textarea name="sympy" rows="6">${escapeHtml(initial?.sympy ?? '')}</textarea>
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
    this.markInputsAsShortcutSafe();
    this.allowTextareaNewlines();
    this.documentKeyHandler = event => {
      if (event.key !== 'Enter') {
        return;
      }
      if (!isTextAreaInside(this.node, event.target)) {
        return;
      }
      event.stopPropagation();
      event.stopImmediatePropagation();
      if (event.target.name !== 'sympy') {
        return;
      }
      event.preventDefault();
      const textarea = event.target;
      const start = textarea.selectionStart ?? textarea.value.length;
      const end = textarea.selectionEnd ?? textarea.value.length;
      textarea.setRangeText('\n', start, end, 'end');
    };
    document.addEventListener('keydown', this.documentKeyHandler, true);
  }

  dispose(): void {
    document.removeEventListener('keydown', this.documentKeyHandler, true);
    super.dispose();
  }

  private markInputsAsShortcutSafe(): void {
    const controls = this.node.querySelectorAll('input, textarea');
    controls.forEach(control => {
      control.setAttribute('data-lm-suppress-shortcuts', 'true');
    });
  }

  private allowTextareaNewlines(): void {
    const textareas = this.node.querySelectorAll('textarea');
    textareas.forEach(textarea => wireTextareaEnterBehavior(textarea));
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
  private readonly documentKeyHandler: (event: KeyboardEvent) => void;

  constructor(initialLatex = '') {
    super();
    this.addClass('jp-SympyEquationModal');
    this.node.setAttribute('data-lm-suppress-shortcuts', 'true');
    this.node.innerHTML = `
      <div class="jp-SympyEquationModal-row">
        <label>LaTeX</label>
        <textarea name="latex">${escapeHtml(initialLatex)}</textarea>
      </div>
    `;
    this.markInputsAsShortcutSafe();
    this.allowTextareaNewlines();
    this.documentKeyHandler = event => {
      if (event.key !== 'Enter') {
        return;
      }
      if (!isTextAreaInside(this.node, event.target)) {
        return;
      }
      event.stopPropagation();
      event.stopImmediatePropagation();
    };
    document.addEventListener('keydown', this.documentKeyHandler, true);
  }

  dispose(): void {
    document.removeEventListener('keydown', this.documentKeyHandler, true);
    super.dispose();
  }

  private markInputsAsShortcutSafe(): void {
    const controls = this.node.querySelectorAll('input, textarea');
    controls.forEach(control => {
      control.setAttribute('data-lm-suppress-shortcuts', 'true');
    });
  }

  private allowTextareaNewlines(): void {
    const textareas = this.node.querySelectorAll('textarea');
    textareas.forEach(textarea => wireTextareaEnterBehavior(textarea));
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
