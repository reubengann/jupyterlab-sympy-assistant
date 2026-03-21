import pytest

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
