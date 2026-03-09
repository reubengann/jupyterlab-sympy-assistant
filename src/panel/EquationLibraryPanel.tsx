import React, { useEffect, useMemo, useState } from 'react';
import katex from 'katex';
import { showErrorMessage } from '@jupyterlab/apputils';
import { ReactWidget } from '@jupyterlab/ui-components';
import { EquationLibraryApi } from '../request';
import { IEquationRecord } from '../types';
import { showEquationModal, showLatexInputModal } from './EquationModal';

interface IEquationLibraryPanelOptions {
  api: EquationLibraryApi;
  onInsertSympy: (sympyText: string) => void;
}

interface IEquationViewProps extends IEquationLibraryPanelOptions {}

function EquationCard(props: {
  equation: IEquationRecord;
  onEdit: (equation: IEquationRecord) => void;
  onDelete: (equation: IEquationRecord) => void;
  onInsert: (equation: IEquationRecord) => void;
}) {
  const latexMarkup = useMemo(() => {
    if (!props.equation.latex) {
      return '';
    }
    try {
      return katex.renderToString(props.equation.latex, {
        displayMode: true,
        throwOnError: false
      });
    } catch {
      return '';
    }
  }, [props.equation.latex]);

  return (
    <div className="jp-SympyEquationCard">
      <div className="jp-SympyEquationCard-header">
        <strong>{props.equation.name}</strong>
      </div>
      {latexMarkup ? (
        <div
          className="jp-SympyEquationCard-rendered"
          dangerouslySetInnerHTML={{ __html: latexMarkup }}
        />
      ) : (
        <pre className="jp-SympyEquationCard-fallback">{props.equation.sympy}</pre>
      )}
      <code className="jp-SympyEquationCard-sympy">{props.equation.sympy}</code>
      {props.equation.description && (
        <p className="jp-SympyEquationCard-description">{props.equation.description}</p>
      )}
      <div className="jp-SympyEquationCard-actions">
        <button onClick={() => props.onInsert(props.equation)}>Insert</button>
        <button onClick={() => props.onEdit(props.equation)}>Edit</button>
        <button onClick={() => props.onDelete(props.equation)}>Delete</button>
      </div>
    </div>
  );
}

function EquationLibraryView({ api, onInsertSympy }: IEquationViewProps) {
  const [equations, setEquations] = useState<IEquationRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const refresh = async () => {
    setLoading(true);
    try {
      setEquations(await api.list());
    } catch (error) {
      await showErrorMessage('Failed to load equations', String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const createEquation = async () => {
    const draft = await showEquationModal();
    if (!draft) {
      return;
    }
    try {
      await api.create(draft);
      await refresh();
    } catch (error) {
      await showErrorMessage('Failed to create equation', String(error));
    }
  };

  const editEquation = async (equation: IEquationRecord) => {
    const draft = await showEquationModal(equation);
    if (!draft) {
      return;
    }
    try {
      await api.update(equation.id, draft);
      await refresh();
    } catch (error) {
      await showErrorMessage('Failed to update equation', String(error));
    }
  };

  const deleteEquation = async (equation: IEquationRecord) => {
    try {
      await api.remove(equation.id);
      await refresh();
    } catch (error) {
      await showErrorMessage('Failed to delete equation', String(error));
    }
  };

  const insertEquation = (equation: IEquationRecord) => {
    onInsertSympy(equation.sympy);
  };

  const insertFromLatex = async () => {
    const latex = await showLatexInputModal();
    if (!latex) {
      return;
    }
    try {
      const sympy = await api.convertLatex(latex);
      const draft = await showEquationModal({
        id: '',
        name: '',
        sympy,
        latex,
        description: '',
        tags: [],
        created_at: '',
        updated_at: ''
      });
      if (!draft) {
        return;
      }
      await api.create(draft);
      await refresh();
    } catch (error) {
      await showErrorMessage('Failed to convert LaTeX', String(error));
    }
  };

  return (
    <div className="jp-SympyEquationPanel">
      <div className="jp-SympyEquationPanel-header">
        <h3>SymPy Equation Library</h3>
        <div className="jp-SympyEquationPanel-headerButtons">
          <button onClick={() => void insertFromLatex()}>Add from LaTeX</button>
          <button onClick={() => void createEquation()}>Add Equation</button>
        </div>
      </div>
      {loading ? (
        <p>Loading...</p>
      ) : equations.length === 0 ? (
        <p>No saved equations yet.</p>
      ) : (
        <div className="jp-SympyEquationPanel-list">
          {equations.map(equation => (
            <EquationCard
              key={equation.id}
              equation={equation}
              onEdit={eq => void editEquation(eq)}
              onDelete={eq => void deleteEquation(eq)}
              onInsert={insertEquation}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export class EquationLibraryPanel extends ReactWidget {
  constructor(private options: IEquationLibraryPanelOptions) {
    super();
    this.id = 'jupyterlab-sympy-assistant:library-panel';
    this.title.label = 'SymPy Library';
    this.title.closable = false;
    this.addClass('jp-SympyEquationSidebar');
  }

  render(): JSX.Element {
    return (
      <EquationLibraryView
        api={this.options.api}
        onInsertSympy={this.options.onInsertSympy}
      />
    );
  }
}
