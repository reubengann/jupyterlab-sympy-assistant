import type { Expr } from '@physics-derivation-pad/core/ast';
import { parseLatexToExpr } from '@physics-derivation-pad/core/latex';
import { tryExprToSympy } from '@physics-derivation-pad/core/sympy';

import type { ILatexConversion } from './types';

const PYTHON_KEYWORDS = new Set([
  'False',
  'None',
  'True',
  'and',
  'as',
  'assert',
  'async',
  'await',
  'break',
  'class',
  'continue',
  'def',
  'del',
  'elif',
  'else',
  'except',
  'finally',
  'for',
  'from',
  'global',
  'if',
  'import',
  'in',
  'is',
  'lambda',
  'nonlocal',
  'not',
  'or',
  'pass',
  'raise',
  'return',
  'try',
  'while',
  'with',
  'yield'
]);

const SYMBOL_CALL_PATTERN = /spp\.Symbol\(("(?:\\.|[^"\\])*")\)/g;

interface ISymbolBinding {
  identifier: string;
  sourceName: string;
}

export function convertLatexToBundle(latex: string): ILatexConversion {
  if (!latex.trim()) {
    throw new Error('LaTeX input is required.');
  }

  const expr = parseLatexToExpr(normalizeAssistantLatex(latex), {
    onError: 'throw'
  });
  const renderedLines = renderSympyLines(expr);
  const rendered = renderedLines.join('\n');
  const bindings = buildSymbolBindings(extractRenderedSymbolNames(rendered));
  const identifierBySourceName = new Map(
    bindings.map(binding => [binding.sourceName, binding.identifier])
  );
  const sympy = rendered.replace(
    SYMBOL_CALL_PATTERN,
    (_match, quotedName: string) => {
      const sourceName = JSON.parse(quotedName) as string;
      return identifierBySourceName.get(sourceName) ?? _match;
    }
  );
  const symbols = bindings.map(binding => binding.identifier).sort();
  const symbolsLine = renderSymbolDeclarations(bindings);

  return {
    sympy,
    symbols,
    symbols_line: symbolsLine,
    code: [symbolsLine, sympy].filter(Boolean).join('\n')
  };
}

function renderSympyLines(expr: Expr): string[] {
  if (expr.kind === 'equation' && expr.sides.length > 2) {
    return expr.sides.slice(1).map((side, index) =>
      renderExpr({
        kind: 'equation',
        sides: [expr.sides[index], side]
      })
    );
  }
  return [renderExpr(expr)];
}

function renderExpr(expr: Expr): string {
  const result = tryExprToSympy(expr, {
    namespace: 'spp',
    constrainedPartialFunction: 'partial'
  });
  if (result.ok) {
    return result.code;
  }

  const details = result.issues
    .map(issue => `${issue.exprKind}: ${issue.reason}`)
    .join(', ');
  throw new Error(`PDP cannot convert this LaTeX to SymPy (${details}).`);
}

function extractRenderedSymbolNames(code: string): string[] {
  const names = new Set<string>();
  const pattern = new RegExp(SYMBOL_CALL_PATTERN.source, 'g');
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(code)) !== null) {
    names.add(JSON.parse(match[1]) as string);
  }
  return [...names].sort();
}

function buildSymbolBindings(sourceNames: string[]): ISymbolBinding[] {
  const identifiers = new Set<string>();
  return sourceNames.map(sourceName => {
    const baseIdentifier = toPythonIdentifier(sourceName);
    let identifier = baseIdentifier;
    let suffix = 2;
    while (identifiers.has(identifier)) {
      identifier = `${baseIdentifier}_${suffix}`;
      suffix += 1;
    }
    identifiers.add(identifier);
    return { identifier, sourceName };
  });
}

function toPythonIdentifier(sourceName: string): string {
  let identifier = sourceName
    .replace(/^\\Delta\s*/, 'd')
    .replace(/\\mathscr\{([^{}]+)\}/g, 'mathscr$1')
    .replace(/\\mathcal\{([^{}]+)\}/g, 'mathcal$1')
    .replace(/\\mathbb\{([^{}]+)\}/g, 'mathbb$1')
    .replace(/_\{?\\text\{([^{}]+)\}\}?/g, '_$1')
    .replace(/\\([A-Za-z]+)/g, '$1')
    .replace(/[{}]/g, '')
    .replace(/'+/g, match => `_prime${match.length > 1 ? match.length : ''}`)
    .replace(/[^A-Za-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '');

  if (!identifier) {
    identifier = 'symbol';
  }
  if (/^[0-9]/.test(identifier)) {
    identifier = `symbol_${identifier}`;
  }
  if (PYTHON_KEYWORDS.has(identifier)) {
    identifier = `${identifier}_symbol`;
  }
  return identifier;
}

function normalizeAssistantLatex(latex: string): string {
  return latex.replace(
    /\\(?:d?frac)\{\\mathrm\{d\}\{([^{}]+)\}\}\{\\mathrm\{d\}\{([^{}]+)\}\}/g,
    String.raw`\text{d$1_d$2}`
  );
}

function renderSymbolDeclarations(bindings: ISymbolBinding[]): string {
  const directBindings = bindings.filter(
    binding => binding.identifier === binding.sourceName
  );
  const aliasedBindings = bindings.filter(
    binding => binding.identifier !== binding.sourceName
  );
  const lines = aliasedBindings.map(
    binding =>
      `${binding.identifier} = spp.Symbol(${JSON.stringify(binding.sourceName)})`
  );

  if (directBindings.length > 0) {
    const identifiers = directBindings.map(binding => binding.identifier);
    lines.push(
      `${identifiers.join(', ')} = spp.symbols(${JSON.stringify(
        identifiers.join(' ')
      )})`
    );
  }
  return lines.join('\n');
}
