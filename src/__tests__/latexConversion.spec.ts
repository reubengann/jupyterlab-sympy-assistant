import { convertLatexToBundle } from '../latexConversion';

beforeAll(() => {
  if (!globalThis.structuredClone) {
    globalThis.structuredClone = <T>(value: T): T =>
      JSON.parse(JSON.stringify(value)) as T;
  }
});

describe('convertLatexToBundle', () => {
  it('converts LaTeX through the PDP AST and emits the existing bundle shape', () => {
    const bundle = convertLatexToBundle(String.raw`a + b = c`);

    expect(bundle).toEqual({
      sympy: 'spp.Eq(spp.Add(a, b), c)',
      symbols: ['a', 'b', 'c'],
      symbols_line: 'a, b, c = spp.symbols("a b c")',
      code: 'a, b, c = spp.symbols("a b c")\n' + 'spp.Eq(spp.Add(a, b), c)'
    });
  });

  it('preserves chained equalities as adjacent equation lines', () => {
    const bundle = convertLatexToBundle(
      String.raw`\rho = \frac{m}{V} = \frac{1}{v}`
    );

    expect(bundle.symbols).toEqual(['V', 'm', 'rho', 'v']);
    expect(bundle.symbols_line).toContain(
      String.raw`rho = spp.Symbol("\\rho")`
    );
    expect(bundle.sympy.split('\n')).toHaveLength(2);
    expect(bundle.sympy).not.toContain('spp.Symbol(');
    expect(bundle.sympy).toContain('spp.Eq(rho,');
  });

  it('creates safe aliases while preserving the original SymPy symbol names', () => {
    const bundle = convertLatexToBundle(
      String.raw`\Delta Q = n c_v \Delta T + \frac{n c_v T_0}{2}`
    );

    expect(bundle.symbols).toEqual(['T_0', 'c_v', 'dQ', 'dT', 'n']);
    expect(bundle.symbols_line).toContain(
      String.raw`dQ = spp.Symbol("\\Delta Q")`
    );
    expect(bundle.symbols_line).toContain(
      String.raw`dT = spp.Symbol("\\Delta T")`
    );
    expect(bundle.sympy).toContain('spp.Eq(dQ,');
  });

  it('rejects empty input before invoking the parser', () => {
    expect(() => convertLatexToBundle('   ')).toThrow(
      'LaTeX input is required.'
    );
  });

  it.each([
    [
      'ordinary differentials',
      String.raw`dU = dQ - dW`,
      ['dQ', 'dU', 'dW'],
      'spp.Eq(dU, spp.Add(dQ, spp.Mul(spp.Integer(-1), dW)))'
    ],
    [
      'standalone text',
      String.raw`x = \text{const}`,
      ['const', 'x'],
      'spp.Eq(x, const)'
    ]
  ])('converts assistant semantics for %s', (_name, latex, symbols, sympy) => {
    expect(convertLatexToBundle(latex)).toMatchObject({ symbols, sympy });
  });

  it('emits matterlib constrained partial calls from the PDP AST', () => {
    const bundle = convertLatexToBundle(
      String.raw`\left(\frac{\partial h}{\partial T}\right)_P`
    );

    expect(bundle.symbols).toEqual(['P', 'T', 'h']);
    expect(bundle.sympy).toBe('spp.partial(h, T, hold=P)');
  });

  it('reports expression kinds that have no SymPy policy', () => {
    expect(() =>
      convertLatexToBundle(String.raw`\vec{v} \cdot \vec{w}`)
    ).toThrow('inner_product');
  });
});
