import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ToolbarButton, showErrorMessage } from '@jupyterlab/apputils';
import { INotebookTracker } from '@jupyterlab/notebook';
import { runIcon } from '@jupyterlab/ui-components';
import { EquationLibraryPanel } from './panel/EquationLibraryPanel';
import { EquationLibraryApi } from './request';

export const EQUATION_FORGE_WIDGET_ID = 'jupyterlab-equation-forge:main';
export const ADD_EQUATION_FORGE_ENTRY_COMMAND =
  'jupyterlab-equation-forge:add-equation-entry';

/**
 * Initialization data for the jupyterlab-sympy-assistant extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'jupyterlab-sympy-assistant:plugin',
  description: 'SymPy helper sidebar for JupyterLab notebooks.',
  autoStart: true,
  requires: [INotebookTracker],
  activate: (app: JupyterFrontEnd, notebooks: INotebookTracker) => {
    const commandId = 'jupyterlab-sympy-assistant:open-library';
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

    app.commands.addCommand(commandId, {
      label: 'Open SymPy Equation Library',
      execute: () => {
        if (!panel.isAttached) {
          app.shell.add(panel, 'left', { rank: 700 });
        }
        app.shell.activateById(panel.id);
      }
    });

    notebooks.widgetAdded.connect((_, notebookPanel) => {
      const toolbarButton = new ToolbarButton({
        icon: runIcon,
        onClick: () => {
          void app.commands.execute(commandId);
        },
        tooltip: 'Open equation library sidebar'
      });

      notebookPanel.toolbar.insertAfter(
        'cellType',
        'sympyLibrary',
        toolbarButton
      );
      notebookPanel.disposed.connect(() => toolbarButton.dispose());
    });
  }
};

export default plugin;
