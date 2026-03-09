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
