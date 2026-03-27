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
