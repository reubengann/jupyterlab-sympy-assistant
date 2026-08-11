export interface IEquationRecord {
  id: string;
  name: string;
  sympy: string;
  latex: string;
  description: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface IEquationInput {
  name: string;
  sympy: string;
  latex?: string;
  description?: string;
  tags?: string[];
}

export interface IEquationLibrary {
  schema_version: number;
  equations: IEquationRecord[];
}

export interface IEquationImportResult {
  imported: number;
  added: number;
  updated: number;
}

export interface ILatexConversion {
  sympy: string;
  symbols: string[];
  symbols_line: string;
  code: string;
}
