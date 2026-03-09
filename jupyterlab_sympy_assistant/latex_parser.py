from __future__ import annotations

from typing import List


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


def convert_latex_to_sympy(latex: str) -> str:
    raw = (latex or "").strip()
    if not raw:
        raise ValueError("Field 'latex' is required.")
    # Handle common copy/paste form where slashes are double-escaped.
    raw = raw.replace("\\\\", "\\")

    parts = [part.strip() for part in raw.split("=") if part.strip()]
    parsed: List[str] = [str(_parse_part(part)) for part in parts]

    if len(parsed) == 1:
        return parsed[0]

    # Preserve chained equalities as adjacent Eq(...) statements.
    return "\n".join(
        f"Eq({parsed[index]}, {parsed[index + 1]})"
        for index in range(len(parsed) - 1)
    )
