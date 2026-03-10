from __future__ import annotations

import re
from typing import Any, List


def _parse_part(part: str):
    try:
        from sympy.parsing.latex import parse_latex
    except ImportError as err:  # pragma: no cover - import path environment-specific
        raise RuntimeError("LaTeX parsing requires sympy in the active environment.") from err

    # Prefer the Lark backend because it avoids the fragile antlr4 runtime pin.
    try:
        return parse_latex(part, backend="lark")
    except Exception:
        return parse_latex(part)


def convert_latex_to_bundle(latex: str) -> dict[str, Any]:
    raw = (latex or "").strip()
    if not raw:
        raise ValueError("Field 'latex' is required.")
    # Handle common copy/paste form where slashes are double-escaped.
    raw = raw.replace("\\\\", "\\")

    parts = [part.strip() for part in raw.split("=") if part.strip()]
    parsed_exprs: List[Any] = [_parse_part(part) for part in parts]

    if len(parsed_exprs) == 1:
        expressions = [parsed_exprs[0]]
    else:
        # Preserve chained equalities as adjacent Eq(...) statements.
        expressions = [
            f"sp.Eq({parsed_exprs[index]}, {parsed_exprs[index + 1]})"
            for index in range(len(parsed_exprs) - 1)
        ]

    def normalize_eq(text: str) -> str:
        return re.sub(r"(?<!sp\.)Eq\(", "sp.Eq(", text)

    sympy_text = "\n".join(normalize_eq(str(expr)) for expr in expressions)

    symbol_names = sorted(
        {
            str(symbol)
            for expr in parsed_exprs
            for symbol in getattr(expr, "free_symbols", set())
        }
    )
    symbols_line = (
        f"{', '.join(symbol_names)} = sp.symbols('{ ' '.join(symbol_names)}')"
        if symbol_names
        else ""
    )
    code = f"{symbols_line}\n{sympy_text}" if symbols_line else sympy_text

    return {
        "sympy": sympy_text,
        "symbols": symbol_names,
        "symbols_line": symbols_line,
        "code": code,
    }


def convert_latex_to_sympy(latex: str) -> str:
    return str(convert_latex_to_bundle(latex)["sympy"])
