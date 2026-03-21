from __future__ import annotations

import re
from typing import Any, List

from sympy import Basic, Mul, Symbol
from sympy.core.function import AppliedUndef


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

    def collapse_implicit_symbol_calls(expr: Any) -> Any:
        # parse_latex may read "f (x)" as an undefined function call f(x).
        # For equation-entry use cases we prefer implicit multiplication.
        if not isinstance(expr, Basic):
            return expr

        def rewrite_call(node: Any) -> Any:
            if not isinstance(node, AppliedUndef) or len(node.args) != 1:
                return node
            func_name = getattr(node.func, "__name__", "")
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", func_name):
                return node
            return Symbol(func_name) * node.args[0]

        return expr.replace(lambda node: isinstance(node, AppliedUndef), rewrite_call)

    def collapse_wrapper_symbol_products(expr: Any) -> Any:
        wrappers = {
            "mathscr",
            "mathcal",
            "mathbf",
            "mathrm",
            "mathit",
            "mathsf",
            "mathtt",
            "boldsymbol",
        }
        if not isinstance(expr, Basic):
            return expr

        def merge_mul(node: Any) -> Any:
            if not isinstance(node, Mul):
                return node
            symbol_args = [arg for arg in node.args if getattr(arg, "is_Symbol", False)]
            wrapper_symbols = [arg for arg in symbol_args if str(arg) in wrappers]
            wrapped_symbols = [arg for arg in symbol_args if str(arg) not in wrappers]
            if len(wrapper_symbols) != 1 or len(wrapped_symbols) != 1:
                return node

            wrapper = wrapper_symbols[0]
            wrapped = wrapped_symbols[0]
            merged = Symbol(f"{wrapper}{wrapped}")
            kept_args = [arg for arg in node.args if arg not in {wrapper, wrapped}]
            return Mul(merged, *kept_args)

        return expr.replace(lambda node: isinstance(node, Mul), merge_mul)

    parsed_exprs = [collapse_implicit_symbol_calls(expr) for expr in parsed_exprs]
    parsed_exprs = [collapse_wrapper_symbol_products(expr) for expr in parsed_exprs]

    def normalize_eq(text: str) -> str:
        return re.sub(r"(?<!spp\.)(?<!sp\.)Eq\(", "spp.Eq(", text)

    latex_wrapper_commands = (
        "mathscr",
        "mathcal",
        "mathbf",
        "mathrm",
        "mathit",
        "mathsf",
        "mathtt",
        "boldsymbol",
    )

    def normalize_symbol_name(name: str) -> str:
        # Flatten LaTeX command wrappers, e.g. \mathscr{F} -> mathscrF.
        normalized = name.strip()
        normalized = normalized.replace("\\left", "").replace("\\right", "")
        normalized = re.sub(
            r"\\([A-Za-z]+)\s*\{([^{}]+)\}",
            lambda match: f"{match.group(1)}{match.group(2)}",
            normalized,
        )
        normalized = re.sub(r"\\([A-Za-z]+)", r"\1", normalized)
        normalized = normalized.replace("{", "").replace("}", "")
        # Convert latex-style subscripts: X_{3} -> X_3
        normalized = re.sub(r"_\{([^}]+)\}", r"_\1", normalized)
        # Replace remaining non-identifier chars with underscores.
        normalized = re.sub(r"[^0-9A-Za-z_]", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if not normalized:
            normalized = "sym"
        if normalized[0].isdigit():
            normalized = f"sym_{normalized}"
        return normalized

    def to_latex_symbol_name(name: str) -> str:
        for command in latex_wrapper_commands:
            if not name.startswith(command):
                continue
            wrapped = name[len(command) :]
            if not wrapped:
                continue
            if re.fullmatch(r"[A-Za-z0-9_]+", wrapped):
                return f"\\{command}{{{wrapped}}}"
        return name

    # Normalize free symbol names so generated Python assignments are valid.
    rename_map: dict[Any, Any] = {}
    used_names: set[str] = set()
    for expr in parsed_exprs:
        for symbol in sorted(getattr(expr, "free_symbols", set()), key=lambda item: str(item)):
            if symbol in rename_map:
                continue
            base_name = normalize_symbol_name(str(symbol))
            candidate = base_name
            suffix = 2
            while candidate in used_names:
                candidate = f"{base_name}_{suffix}"
                suffix += 1
            used_names.add(candidate)
            rename_map[symbol] = Symbol(candidate)

    if rename_map:
        parsed_exprs = [
            expr.xreplace(rename_map) if hasattr(expr, "xreplace") else expr for expr in parsed_exprs
        ]

    if len(parsed_exprs) == 1:
        expressions = [parsed_exprs[0]]
    else:
        # Preserve chained equalities as adjacent Eq(...) statements.
        expressions = [
            f"spp.Eq({parsed_exprs[index]}, {parsed_exprs[index + 1]})"
            for index in range(len(parsed_exprs) - 1)
        ]

    sympy_text = "\n".join(normalize_eq(str(expr)) for expr in expressions)

    symbol_names = sorted(
        {
            str(symbol)
            for expr in parsed_exprs
            for symbol in getattr(expr, "free_symbols", set())
        }
    )
    symbol_literal_names = [to_latex_symbol_name(name) for name in symbol_names]
    symbols_literal = " ".join(symbol_literal_names)
    symbols_literal_text = f"'{symbols_literal.replace('\\', '\\\\')}'"
    symbols_line = (
        f"{', '.join(symbol_names)} = spp.symbols({symbols_literal_text})"
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
