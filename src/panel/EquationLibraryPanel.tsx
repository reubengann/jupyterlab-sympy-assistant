import React, { useEffect, useMemo, useRef, useState } from 'react';
import katex from 'katex';
import { showErrorMessage } from '@jupyterlab/apputils';
import {
  deleteIcon,
  editIcon,
  LabIcon,
  ReactWidget,
  runIcon
} from '@jupyterlab/ui-components';
import { convertLatexToBundle } from '../latexConversion';
import { EquationLibraryApi } from '../request';
import { IEquationRecord } from '../types';
import { showEquationModal, showLatexInputModal } from './EquationModal';
import functionSvg from '../../style/icons/function.svg';
import addBoxSvg from '../../style/icons/addbox.svg';

const sympyLibraryIcon = new LabIcon({
  name: 'jupyterlab-sympy-assistant:function',
  svgstr: functionSvg
});

const addFromLatexIcon = new LabIcon({
  name: 'jupyterlab-sympy-assistant:addbox',
  svgstr: addBoxSvg
});

interface IEquationLibraryPanelOptions {
  api: EquationLibraryApi;
  onInsertSympy: (sympyText: string, latexText: string) => void;
}

interface IEquationViewProps extends IEquationLibraryPanelOptions {}

function toPythonIdentifier(name: string): string {
  const normalized = name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '');
  if (!normalized) {
    return 'equation';
  }
  if (/^[0-9]/.test(normalized)) {
    return `eq_${normalized}`;
  }
  return normalized;
}

function buildInsertionSnippet(equation: IEquationRecord): string {
  const lines = equation.sympy
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => line.replace(/^Eq\(/, 'spp.Eq('));

  if (lines.length === 0) {
    return equation.sympy;
  }

  // If user already authored explicit assignments, preserve as-is.
  if (lines.some(line => /^[A-Za-z_][A-Za-z0-9_]*\s*=/.test(line))) {
    return lines.join('\n');
  }

  const eqIndex = lines.findIndex(line => /^spp\.Eq\(/.test(line));
  if (eqIndex === -1) {
    return lines.join('\n');
  }

  const varName = toPythonIdentifier(equation.name);
  const prelude = lines.slice(0, eqIndex);
  const eqLine = lines[eqIndex];
  const suffix = lines.slice(eqIndex + 1);

  return [...prelude, `${varName} = ${eqLine}`, ...suffix, varName].join('\n');
}

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
      <div className="jp-SympyEquationCard-actions">
        <button
          className="jp-SympyEquationCard-iconButton"
          onClick={() => props.onInsert(props.equation)}
          title="Insert into active cell"
          aria-label="Insert equation"
        >
          {LabIcon.resolveReact({ icon: runIcon, tag: 'span' })}
        </button>
        <button
          className="jp-SympyEquationCard-iconButton"
          onClick={() => props.onEdit(props.equation)}
          title="Edit equation"
          aria-label="Edit equation"
        >
          {LabIcon.resolveReact({ icon: editIcon, tag: 'span' })}
        </button>
        <button
          className="jp-SympyEquationCard-iconButton"
          onClick={() => props.onDelete(props.equation)}
          title="Delete equation"
          aria-label="Delete equation"
        >
          {LabIcon.resolveReact({ icon: deleteIcon, tag: 'span' })}
        </button>
      </div>
      <div className="jp-SympyEquationCard-body">
        <div className="jp-SympyEquationCard-header">
          <strong>{props.equation.name}</strong>
        </div>
        {latexMarkup ? (
          <div
            className="jp-SympyEquationCard-rendered"
            dangerouslySetInnerHTML={{ __html: latexMarkup }}
          />
        ) : (
          <pre className="jp-SympyEquationCard-fallback">
            {props.equation.sympy}
          </pre>
        )}
        {props.equation.description && (
          <p className="jp-SympyEquationCard-description">
            {props.equation.description}
          </p>
        )}
      </div>
    </div>
  );
}

function EquationLibraryView({ api, onInsertSympy }: IEquationViewProps) {
  const [equations, setEquations] = useState<IEquationRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const listRef = useRef<HTMLDivElement | null>(null);
  const pendingScrollTopRef = useRef<number | null>(null);

  const refresh = async ({
    showLoading = true,
    preserveScroll = false
  }: {
    showLoading?: boolean;
    preserveScroll?: boolean;
  } = {}) => {
    if (preserveScroll && listRef.current) {
      pendingScrollTopRef.current = listRef.current.scrollTop;
    }
    if (showLoading) {
      setLoading(true);
    }
    try {
      setEquations(await api.list());
    } catch (error) {
      await showErrorMessage('Failed to load equations', String(error));
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void refresh({ showLoading: true });
  }, []);

  useEffect(() => {
    if (pendingScrollTopRef.current === null || !listRef.current) {
      return;
    }
    listRef.current.scrollTop = pendingScrollTopRef.current;
    pendingScrollTopRef.current = null;
  }, [equations]);

  const editEquation = async (equation: IEquationRecord) => {
    const draft = await showEquationModal(equation);
    if (!draft) {
      return;
    }
    try {
      await api.update(equation.id, draft);
      await refresh({ showLoading: false, preserveScroll: true });
    } catch (error) {
      await showErrorMessage('Failed to update equation', String(error));
    }
  };

  const deleteEquation = async (equation: IEquationRecord) => {
    try {
      await api.remove(equation.id);
      await refresh({ showLoading: false, preserveScroll: true });
    } catch (error) {
      await showErrorMessage('Failed to delete equation', String(error));
    }
  };

  const insertEquation = (equation: IEquationRecord) => {
    onInsertSympy(buildInsertionSnippet(equation), equation.latex ?? '');
  };

  const insertFromLatex = async () => {
    const latex = await showLatexInputModal();
    if (!latex) {
      return;
    }
    try {
      const converted = convertLatexToBundle(latex);
      const draft = await showEquationModal({
        id: '',
        name: '',
        sympy: converted.code,
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
      await refresh({ showLoading: false, preserveScroll: true });
    } catch (error) {
      await showErrorMessage('Failed to convert LaTeX', String(error));
    }
  };

  const convertLatexToCell = async () => {
    const latex = await showLatexInputModal();
    if (!latex) {
      return;
    }
    try {
      const converted = convertLatexToBundle(latex);
      onInsertSympy(converted.code, latex);
    } catch (error) {
      await showErrorMessage('Failed to convert LaTeX', String(error));
    }
  };

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredEquations = useMemo(() => {
    if (!normalizedQuery) {
      return equations;
    }
    return equations.filter(equation => {
      const haystack = [
        equation.name,
        equation.description ?? '',
        equation.latex ?? '',
        equation.sympy
      ]
        .join('\n')
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [equations, normalizedQuery]);

  return (
    <div className="jp-SympyEquationPanel">
      <div className="jp-SympyEquationPanel-header">
        <h3>Library</h3>
        <div className="jp-SympyEquationPanel-headerButtons">
          <button
            className="jp-SympyEquationCard-iconButton"
            onClick={() => void insertFromLatex()}
            title="Add from LaTeX"
            aria-label="Add from LaTeX"
          >
            {LabIcon.resolveReact({ icon: addFromLatexIcon, tag: 'span' })}
          </button>
          <button
            className="jp-SympyEquationCard-iconButton"
            onClick={() => void convertLatexToCell()}
            title="Convert LaTeX and insert into active cell"
            aria-label="Convert LaTeX and insert"
          >
            {LabIcon.resolveReact({ icon: sympyLibraryIcon, tag: 'span' })}
          </button>
        </div>
      </div>
      <div className="jp-SympyEquationPanel-searchRow">
        <input
          className="jp-SympyEquationPanel-searchInput"
          type="search"
          value={searchQuery}
          onChange={event => setSearchQuery(event.target.value)}
          placeholder="Search name, description, LaTeX, SymPy"
          aria-label="Search equations"
        />
        {searchQuery ? (
          <button
            className="jp-SympyEquationPanel-searchClear"
            type="button"
            onClick={() => setSearchQuery('')}
            title="Clear search"
            aria-label="Clear search"
          >
            x
          </button>
        ) : null}
      </div>
      {loading ? (
        <p>Loading...</p>
      ) : equations.length === 0 ? (
        <p>No saved equations yet.</p>
      ) : filteredEquations.length === 0 ? (
        <p>No equations match your search.</p>
      ) : (
        <div className="jp-SympyEquationPanel-list" ref={listRef}>
          {filteredEquations.map(equation => (
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
    this.title.label = '';
    this.title.caption = 'Library';
    this.title.icon = sympyLibraryIcon;
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
