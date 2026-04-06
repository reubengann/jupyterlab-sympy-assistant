import sys
from types import SimpleNamespace

import pytest
from sympy import Function, Integral, Symbol

from jupyterlab_sympy_assistant import latex_parser


def test_convert_latex_requires_content():
    with pytest.raises(ValueError):
        latex_parser.convert_latex_to_sympy("   ")


def test_convert_latex_chain(monkeypatch):
    monkeypatch.setattr(latex_parser, "_parse_part", lambda part: f"parsed({part})")
    value = latex_parser.convert_latex_to_sympy(r"\rho = \frac{m}{V} = \frac{1}{v}")
    assert value == "spp.Eq(parsed(\\rho), parsed(\\frac{m}{V}))\nspp.Eq(parsed(\\frac{m}{V}), parsed(\\frac{1}{v}))"


def test_convert_latex_bundle_includes_symbols():
    bundle = latex_parser.convert_latex_to_bundle(r"\rho = \frac{m}{V} = \frac{1}{v}")
    assert bundle["symbols"] == ["V", "m", "rho", "v"]
    assert bundle["symbols_line"] == "V, m, rho, v = spp.symbols('V m rho v')"
    assert bundle["code"].startswith("V, m, rho, v = spp.symbols('V m rho v')\nspp.Eq(")


def test_convert_latex_normalizes_subscript_symbols():
    bundle = latex_parser.convert_latex_to_bundle(r"\theta = \theta_3 \frac{X}{X_3}")
    assert bundle["symbols"] == ["X", "X_3", "theta", "theta_3"]
    assert bundle["symbols_line"] == "X, X_3, theta, theta_3 = spp.symbols('X X_3 theta theta_3')"
    assert "spp.Eq(theta, X*theta_3/X_3)" == bundle["sympy"]


def test_convert_latex_normalizes_mathscr_and_subscripts(monkeypatch):
    lhs = Symbol("L")
    rhs = Symbol("L_{0}") * (
        1
        + Symbol("mathscr") * Symbol("F") / (Symbol("Y") * Symbol("A"))
        + Function("alpha")(Symbol("T") - Symbol("T_{0}"))
    )
    parsed = iter([lhs, rhs])
    monkeypatch.setattr(latex_parser, "_parse_part", lambda part: next(parsed))

    bundle = latex_parser.convert_latex_to_bundle(
        r"L = L_0 \left[1 + \frac{\mathscr{F}}{Y A} + \alpha (T - T_0)\right]"
    )
    assert bundle["symbols"] == ["A", "L", "L_0", "T", "T_0", "Y", "alpha", "mathscrF"]
    assert (
        bundle["symbols_line"]
        == "A, L, L_0, T, T_0, Y, alpha, mathscrF = spp.symbols('A L L_0 T T_0 Y alpha \\\\mathscr{F}')"
    )
    assert bundle["sympy"].startswith("spp.Eq(L, L_0*(")
    assert "mathscrF/(A*Y)" in bundle["sympy"]
    assert "alpha*(T - T_0)" in bundle["sympy"]
    assert "T_0" in bundle["sympy"]


def test_convert_latex_rewrites_implicit_symbol_call(monkeypatch):
    lhs = Symbol("L")
    rhs = Function("f")(Symbol("a") - Symbol("b"))  # emulate parse_latex output for "f (a - b)"
    parsed = iter([lhs, rhs])
    monkeypatch.setattr(latex_parser, "_parse_part", lambda part: next(parsed))

    bundle = latex_parser.convert_latex_to_bundle(r"L = f (a - b)")
    assert bundle["symbols"] == ["L", "a", "b", "f"]
    assert bundle["symbols_line"] == "L, a, b, f = spp.symbols('L a b f')"
    assert bundle["sympy"] == "spp.Eq(L, f*(a - b))"


def test_convert_latex_rewrites_powered_implicit_symbol_call(monkeypatch):
    lhs = Symbol("c_v")
    rhs = Function("A")(Symbol("T") / Symbol("theta")) ** 3
    parsed = iter([lhs, rhs])
    monkeypatch.setattr(latex_parser, "_parse_part", lambda part: next(parsed))

    bundle = latex_parser.convert_latex_to_bundle(r"c_v = A \left(\frac{T}{\theta}\right)^3")
    assert bundle["symbols"] == ["A", "T", "c_v", "theta"]
    assert bundle["symbols_line"] == "A, T, c_v, theta = spp.symbols('A T c_v theta')"
    assert bundle["sympy"] == "spp.Eq(c_v, A*T**3/theta**3)"


def test_convert_latex_collapses_differential_tokens():
    bundle = latex_parser.convert_latex_to_bundle("dU = dQ - dW")
    assert bundle["symbols"] == ["dQ", "dU", "dW"]
    assert bundle["symbols_line"] == "dQ, dU, dW = spp.symbols('dQ dU dW')"
    assert bundle["sympy"] == "spp.Eq(dU, dQ - dW)"


def test_convert_latex_normalizes_apostrophe_differentials():
    bundle = latex_parser.convert_latex_to_bundle("dU = d'Q - d'W")
    assert bundle["symbols"] == ["dQ", "dU", "dW"]
    assert bundle["symbols_line"] == "dQ, dU, dW = spp.symbols('dQ dU dW')"
    assert bundle["sympy"] == "spp.Eq(dU, dQ - dW)"


def test_convert_latex_declares_integral_bound_variable(monkeypatch):
    lhs = Symbol("Q")
    rhs = Symbol("n") * Integral(Symbol("c"), (Symbol("T"), Symbol("T_1"), Symbol("T_2")))
    parsed = iter([lhs, rhs])
    monkeypatch.setattr(latex_parser, "_parse_part", lambda part: next(parsed))

    bundle = latex_parser.convert_latex_to_bundle(r"Q = n \int_{T_1}^{T_2} c \, dT")
    assert bundle["symbols"] == ["Q", "T", "T_1", "T_2", "c", "n"]
    assert (
        bundle["symbols_line"]
        == "Q, T, T_1, T_2, c, n = spp.symbols('Q T T_1 T_2 c n')"
    )
    assert bundle["sympy"] == "spp.Eq(Q, n*Integral(c, (T, T_1, T_2)))"


def test_convert_latex_prefers_fallback_when_lark_returns_non_sympy(monkeypatch):
    calls = {"lark": 0, "default": 0}

    def fake_parse_latex(part: str, backend: str | None = None):
        if backend == "lark":
            calls["lark"] += 1
            return "Tree('_ambig', [...])"
        calls["default"] += 1
        return Symbol("A")

    monkeypatch.setitem(
        sys.modules,
        "sympy.parsing.latex",
        SimpleNamespace(parse_latex=fake_parse_latex),
    )
    result = latex_parser._parse_part(r"A \left(\frac{T}{theta}\right)^3")
    assert result == Symbol("A")
    assert calls == {"lark": 1, "default": 1}


def test_convert_latex_formula_fallbacks_after_lark_ambiguity(monkeypatch):
    calls = {"lark": 0, "default": 0}
    expected_expr = Symbol("A") * (Symbol("T") / Symbol("theta")) ** 3

    def fake_parse_latex(part: str, backend: str | None = None):
        if backend == "lark":
            calls["lark"] += 1
            if r"A \left(\frac{T}{\theta}\right)^3" in part:
                return "Tree('_ambig', [...])"
            return Symbol("c_v")
        calls["default"] += 1
        if r"A \left(\frac{T}{\theta}\right)^3" in part:
            return expected_expr
        return Symbol("c_v")

    monkeypatch.setitem(
        sys.modules,
        "sympy.parsing.latex",
        SimpleNamespace(parse_latex=fake_parse_latex),
    )

    bundle = latex_parser.convert_latex_to_bundle(r"c_v = A \left(\frac{T}{\theta}\right)^3")
    assert calls == {"lark": 2, "default": 1}
    assert bundle["symbols"] == ["A", "T", "c_v", "theta"]
    assert bundle["sympy"] == "spp.Eq(c_v, A*T**3/theta**3)"


def test_convert_latex_preserves_text_subscripts_and_mathscr_symbols():
    bundle = latex_parser.convert_latex_to_bundle(
        r"m c_P (T_\text{boil} - T_\text{melt}) = \mathscr{P} (t_4 - t_3)"
    )
    assert bundle["symbols"] == ["T_boil", "T_melt", "c_P", "m", "mathscrP", "t_3", "t_4"]
    assert (
        bundle["symbols_line"]
        == "T_boil, T_melt, c_P, m, mathscrP, t_3, t_4 = spp.symbols('T_\\\\text{boil} T_\\\\text{melt} c_P m \\\\mathscr{P} t_3 t_4')"
    )
    assert bundle["sympy"] == "spp.Eq(c_P*m*(T_boil - T_melt), mathscrP*(-t_3 + t_4))"


def test_convert_latex_keeps_plain_letter_subscripts_non_text():
    bundle = latex_parser.convert_latex_to_bundle(r"q_{acb} - w_{acb} = q_{ab} - w_{ab}")
    assert bundle["symbols"] == ["q_ab", "q_acb", "w_ab", "w_acb"]
    assert (
        bundle["symbols_line"]
        == "q_ab, q_acb, w_ab, w_acb = spp.symbols('q_ab q_acb w_ab w_acb')"
    )
    assert bundle["sympy"] == "spp.Eq(q_acb - w_acb, q_ab - w_ab)"


def test_convert_latex_handles_mathscr_with_text_subscript_in_integral():
    bundle = latex_parser.convert_latex_to_bundle(
        r"W = \int_{x_0}^{0.9 x_0} \left[\frac{n R T}{x} + \mathscr{F}_\text{fric.}\right] \, dx"
    )
    assert bundle["symbols"] == ["R", "T", "W", "mathscrF_fric", "n", "x", "x_0"]
    assert (
        bundle["symbols_line"]
        == "R, T, W, mathscrF_fric, n, x, x_0 = spp.symbols('R T W \\\\mathscr{F}_\\\\text{fric} n x x_0')"
    )
    assert bundle["sympy"] == "spp.Eq(W, Integral(R*T*n/x + mathscrF_fric, (x, x_0, 0.9*x_0)))"


def test_convert_latex_preserves_mathscr_numeric_subscripts_in_kinetic_term():
    bundle = latex_parser.convert_latex_to_bundle(
        r"\Delta h = - w_\text{sh} - \frac12 (\mathscr{V}_2^2 - \mathscr{V}_1^2)"
    )
    assert bundle["symbols"] == ["Delta", "h", "mathscrV_1", "mathscrV_2", "w_sh"]
    assert (
        bundle["symbols_line"]
        == "Delta, h, mathscrV_1, mathscrV_2, w_sh = spp.symbols('Delta h \\\\mathscr{V}_{1} \\\\mathscr{V}_{2} w_\\\\text{sh}')"
    )
    assert bundle["sympy"] == "spp.Eq(Delta*h, mathscrV_1**2/2 - mathscrV_2**2/2 - w_sh)"


def test_convert_latex_preserves_constrained_partials_in_products():
    bundle = latex_parser.convert_latex_to_bundle(
        r"c_P = c_v + \left[\left(\dfrac{\partial u}{\partial v}\right)_T  + P \right] \left(\dfrac{\partial v}{\partial T}\right)_P"
    )
    assert bundle["symbols"] == ["P", "T", "c_P", "c_v", "u", "v"]
    assert (
        bundle["symbols_line"]
        == "P, T, c_P, c_v, u, v = spp.symbols('P T c_P c_v u v')"
    )
    assert bundle["sympy"] == "spp.Eq(c_P, c_v + spp.partial(v, T, hold=P)*(P + spp.partial(u, v, hold=T)))"


def test_convert_latex_preserves_braced_constrained_partial():
    bundle = latex_parser.convert_latex_to_bundle(
        r"c_{P} = \left(\frac{\partial{h}}{\partial{T}}\right)_{P}"
    )
    assert bundle["symbols"] == ["P", "T", "c_P", "h"]
    assert bundle["symbols_line"] == "P, T, c_P, h = spp.symbols('P T c_P h')"
    assert bundle["sympy"] == "spp.Eq(c_P, spp.partial(h, T, hold=P))"


def test_convert_latex_normalizes_braced_roman_differentials_in_integrals():
    bundle = latex_parser.convert_latex_to_bundle(
        r"-\int_{T_{1}}^{T_{2}} \,\mathrm{d}{T} = \int_{V}^{2 V} \frac{a}{c_{v} v^{2}} \,\mathrm{d}{v}"
    )
    assert bundle["symbols"] == ["T", "T_1", "T_2", "V", "a", "c_v", "v"]
    assert bundle["symbols_line"] == "T, T_1, T_2, V, a, c_v, v = spp.symbols('T T_1 T_2 V a c_v v')"
    assert (
        bundle["sympy"]
        == "spp.Eq(-Integral(1, (T, T_1, T_2)), Integral(a/(c_v*v**2), (v, V, 2*V)))"
    )


def test_convert_latex_declares_delta_symbols_as_atomic():
    bundle = latex_parser.convert_latex_to_bundle(
        r"\Delta Q = n c_v \Delta T + \frac{n c_v T_0}{2}"
    )
    assert bundle["symbols"] == ["T_0", "c_v", "dQ", "dT", "n"]
    assert (
        bundle["symbols_line"]
        == "dQ = spp.Symbol('\\\\Delta Q')\n"
        "dT = spp.Symbol('\\\\Delta T')\n"
        "T_0, c_v, n = spp.symbols('T_0 c_v n')"
    )
    assert bundle["sympy"] == "spp.Eq(dQ, T_0*c_v*n/2 + c_v*dT*n)"
