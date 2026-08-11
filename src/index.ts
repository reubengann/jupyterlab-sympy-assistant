import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import {
  Dialog,
  ICommandPalette,
  showDialog,
  showErrorMessage
} from '@jupyterlab/apputils';
import { INotebookTracker } from '@jupyterlab/notebook';
import { EquationLibraryPanel } from './panel/EquationLibraryPanel';
import { EquationLibraryApi } from './request';
import { IEquationLibrary } from './types';

export const EQUATION_FORGE_WIDGET_ID = 'jupyterlab-equation-forge:main';
export const ADD_EQUATION_FORGE_ENTRY_COMMAND =
  'jupyterlab-equation-forge:add-equation-entry';

function downloadJson(filename: string, value: unknown): void {
  const blob = new Blob([JSON.stringify(value, null, 2)], {
    type: 'application/json'
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function selectJsonFile(): Promise<File | null> {
  return new Promise(resolve => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';
    input.addEventListener(
      'change',
      () => {
        resolve(input.files?.[0] ?? null);
      },
      { once: true }
    );
    input.addEventListener('cancel', () => resolve(null), { once: true });
    input.click();
  });
}

/**
 * Initialization data for the jupyterlab-sympy-assistant extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'jupyterlab-sympy-assistant:plugin',
  description: 'SymPy helper sidebar for JupyterLab notebooks.',
  autoStart: true,
  requires: [INotebookTracker, ICommandPalette],
  activate: (
    app: JupyterFrontEnd,
    notebooks: INotebookTracker,
    palette: ICommandPalette
  ) => {
    const openCommandId = 'jupyterlab-sympy-assistant:open-library';
    const exportCommandId = 'jupyterlab-sympy-assistant:export-library';
    const importCommandId = 'jupyterlab-sympy-assistant:import-library';
    const api = new EquationLibraryApi(app.serviceManager.serverSettings);
    const asMarkdownLatex = (latexText: string): string => {
      const trimmed = latexText.trim();
      if (!trimmed) {
        return '';
      }
      if (/^\${1,2}[\s\S]*\${1,2}$/.test(trimmed)) {
        return trimmed;
      }
      return `$$\n${trimmed}\n$$`;
    };

    const insertIntoActiveCell = (sympyText: string, latexText: string) => {
      if (app.shell.currentWidget?.id === EQUATION_FORGE_WIDGET_ID) {
        const latex = latexText.trim();
        if (!latex) {
          void showErrorMessage(
            'No LaTeX is available',
            'This library equation has no LaTeX to add to Equation Forge.'
          );
          return;
        }
        if (!app.commands.hasCommand(ADD_EQUATION_FORGE_ENTRY_COMMAND)) {
          void showErrorMessage(
            'Equation Forge integration is unavailable',
            'Rebuild or update the Equation Forge extension to enable library insertion.'
          );
          return;
        }
        void app.commands.execute(ADD_EQUATION_FORGE_ENTRY_COMMAND, { latex });
        return;
      }

      const notebookPanel = notebooks.currentWidget;
      if (!notebookPanel) {
        void showErrorMessage(
          'No notebook is active',
          'Open a notebook to insert SymPy code.'
        );
        return;
      }

      const cell = notebookPanel.content.activeCell;
      if (!cell?.editor) {
        void showErrorMessage(
          'No editable cell is active',
          'Select a notebook cell before inserting SymPy code.'
        );
        return;
      }

      const textToInsert =
        cell.model.type === 'markdown'
          ? asMarkdownLatex(latexText) || sympyText
          : sympyText;

      const replaceSelection = cell.editor.replaceSelection;
      if (typeof replaceSelection === 'function') {
        replaceSelection.call(cell.editor, textToInsert);
        return;
      }

      const current = cell.model.sharedModel.getSource();
      cell.model.sharedModel.setSource(current + textToInsert);
    };

    const panel = new EquationLibraryPanel({
      api,
      onInsertSympy: insertIntoActiveCell
    });
    app.shell.add(panel, 'left', { rank: 700 });

    app.commands.addCommand(openCommandId, {
      label: 'Open SymPy Equation Library',
      execute: () => {
        app.shell.activateById(panel.id);
      }
    });

    app.commands.addCommand(exportCommandId, {
      label: 'Export Equation Library',
      execute: async () => {
        try {
          const library = await api.exportLibrary();
          downloadJson('equation-library.json', library);
        } catch (error) {
          await showErrorMessage(
            'Failed to export equation library',
            String(error)
          );
        }
      }
    });

    app.commands.addCommand(importCommandId, {
      label: 'Import Equation Library',
      execute: async () => {
        const file = await selectJsonFile();
        if (!file) {
          return;
        }
        try {
          const library = JSON.parse(await file.text()) as IEquationLibrary;
          const result = await api.importLibrary(library);
          panel.reload();
          await showDialog({
            title: 'Equation library imported',
            body: `Imported ${result.imported} equations (${result.added} added, ${result.updated} updated).`,
            buttons: [Dialog.okButton()]
          });
        } catch (error) {
          await showErrorMessage(
            'Failed to import equation library',
            String(error)
          );
        }
      }
    });

    const category = 'SymPy Assistant';
    palette.addItem({ command: exportCommandId, category });
    palette.addItem({ command: importCommandId, category });
  }
};

export default plugin;
