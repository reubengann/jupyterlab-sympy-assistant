import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ToolbarButton, showErrorMessage } from '@jupyterlab/apputils';
import { INotebookTracker } from '@jupyterlab/notebook';
import { EquationLibraryPanel } from './panel/EquationLibraryPanel';
import { EquationLibraryApi } from './request';

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

    const insertIntoActiveCell = (sympyText: string) => {
      const notebookPanel = notebooks.currentWidget;
      if (!notebookPanel) {
        void showErrorMessage('No notebook is active', 'Open a notebook to insert SymPy code.');
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

      const replaceSelection = cell.editor.replaceSelection;
      if (typeof replaceSelection === 'function') {
        replaceSelection.call(cell.editor, sympyText);
        return;
      }

      const current = cell.model.sharedModel.getSource();
      cell.model.sharedModel.setSource(current + sympyText);
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
        label: 'SymPy Library',
        onClick: () => {
          void app.commands.execute(commandId);
        },
        tooltip: 'Open SymPy equation library sidebar'
      });

      notebookPanel.toolbar.insertAfter('cellType', 'sympyLibrary', toolbarButton);
      notebookPanel.disposed.connect(() => toolbarButton.dispose());
    });
  }
};

export default plugin;
