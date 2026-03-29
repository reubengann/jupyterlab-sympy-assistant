from __future__ import annotations

import re
from typing import Any, List, cast

from sympy import Basic, Mul, Pow, Symbol
from sympy.core.function import AppliedUndef


def _parse_part(part: str):
    try:
        from sympy.parsing.latex import parse_latex
    except ImportError as err:  # pragma: no cover - import path environment-specific
        raise RuntimeError("LaTeX parsing requires sympy in the active environment.") from err

    # Prefer the Lark backend because it avoids the fragile antlr4 runtime pin.
    # If Lark yields a non-SymPy parse artifact (e.g. an ambiguity tree),
    # fall back to the default backend.
    parse_latex_any = cast(Any, parse_latex)
    try:
        parsed = parse_latex_any(part, backend="lark")
        if isinstance(parsed, (Basic, tuple)):
            return parsed
    except Exception:
        pass
    return parse_latex_any(part)


def convert_latex_to_bundle(latex: str) -> dict[str, Any]:
    raw = (latex or "").strip()
    if not raw:
        raise ValueError("Field 'latex' is required.")
    # Handle common copy/paste form where slashes are double-escaped.
    raw = raw.replace("\\\\", "\\")
    # Common thermo shorthand: d'Q, d'W -> dQ, dW.
    raw = re.sub(r"\bd'\s*([A-Za-z][A-Za-z0-9_]*)", r"d\1", raw)
    # Keep text subscripts as atomic names by converting them to one-token commands:
    # T_\text{boil} -> T_{\boil}. SymPy then parses this as T_{boil}.
    def rewrite_text_subscript(match: re.Match[str]) -> str:
        label = match.group(1).strip()
        command = re.sub(r"[^A-Za-z]", "", label)
        if not command:
            command = "text"
        return f"_{{\\{command}}}"

    raw = re.sub(r"_\\text\s*\{([^{}]+)\}", rewrite_text_subscript, raw)

    parts = [part.strip() for part in raw.split("=") if part.strip()]
    parsed_exprs: List[Any] = [_parse_part(part) for part in parts]

    def collapse_differential_tuples(expr: Any) -> Any:
        # parse_latex may read a standalone token like "dU" as tuple (d, U).
        # For thermodynamics notation, treat this as a single symbol dU.
        if (
            isinstance(expr, tuple)
            and len(expr) == 2
            and all(getattr(item, "is_Symbol", False) for item in expr)
            and str(expr[0]) == "d"
        ):
            return Symbol(f"d{expr[1]}")
        return expr

    def collapse_implicit_symbol_calls(expr: Any) -> Any:
        # parse_latex may read "f (x)" as an undefined function call f(x).
        # For equation-entry use cases we prefer implicit multiplication.
        if not isinstance(expr, Basic):
            return expr

        def parse_callable_name(node: Any) -> str:
            if not isinstance(node, AppliedUndef) or len(node.args) != 1:
                return ""
            func_name = getattr(node.func, "__name__", "")
            if not func_name:
                return ""
            return str(func_name)

        def rewrite_pow_call(node: Any) -> Any:
            if not isinstance(node, Pow):
                return node
            base, exponent = node.args
            func_name = parse_callable_name(base)
            if not func_name:
                return node
            argument = cast(Any, base.args[0])
            return cast(Any, Symbol(func_name) * (argument**exponent))

        def rewrite_call(node: Any) -> Any:
            func_name = parse_callable_name(node)
            if not func_name:
                return node
            argument = cast(Any, node.args[0])
            return cast(Any, Symbol(func_name) * argument)

        expr = expr.replace(lambda node: isinstance(node, Pow), rewrite_pow_call)
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
            if len(wrapper_symbols) != 1:
                return node

            wrapper = wrapper_symbols[0]
            wrapped: Any | None = None
            nested_mul_arg: Any | None = None

            direct_wrapped_symbols = [
                arg
                for arg in symbol_args
                if str(arg) not in wrappers and arg is not wrapper
            ]
            if len(direct_wrapped_symbols) == 1:
                wrapped = direct_wrapped_symbols[0]
            elif len(direct_wrapped_symbols) == 0:
                for arg in node.args:
                    if not isinstance(arg, Mul):
                        continue
                    nested_symbols = [
                        item
                        for item in arg.args
                        if getattr(item, "is_Symbol", False) and str(item) not in wrappers
                    ]
                    if len(nested_symbols) == 1:
                        wrapped = nested_symbols[0]
                        nested_mul_arg = arg
                        break

            if wrapped is None:
                return node

            merged = Symbol(f"{wrapper}{wrapped}")
            kept_args: list[Any] = []
            for arg in node.args:
                if arg == wrapper:
                    continue
                if nested_mul_arg is not None and arg == nested_mul_arg:
                    remaining_nested_args = [
                        item for item in nested_mul_arg.args if item != wrapped
                    ]
                    kept_args.extend(remaining_nested_args)
                    continue
                if nested_mul_arg is None and arg == wrapped:
                    continue
                kept_args.append(arg)
            return Mul(merged, *kept_args)

        return expr.replace(lambda node: isinstance(node, Mul), merge_mul)

    parsed_exprs = [collapse_differential_tuples(expr) for expr in parsed_exprs]
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
        subscript_match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)_([A-Za-z][A-Za-z0-9]*)", name)
        if subscript_match:
            base, subscript = subscript_match.groups()
            if subscript.isalpha() and len(subscript) > 1:
                return f"{base}_\\text{{{subscript}}}"
        return name

    def extract_declared_symbols(expr: Any) -> set[Symbol]:
        if isinstance(expr, Basic):
            return {symbol for symbol in expr.atoms(Symbol)}
        return set()

    # Normalize symbol names so generated Python assignments are valid.
    rename_map: dict[Any, Any] = {}
    used_names: set[str] = set()
    for expr in parsed_exprs:
        for symbol in sorted(extract_declared_symbols(expr), key=lambda item: str(item)):
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
            for symbol in extract_declared_symbols(expr)
        }
    )
    symbol_literal_names = [to_latex_symbol_name(name) for name in symbol_names]
    symbols_literal = " ".join(symbol_literal_names)
    escaped_symbols_literal = symbols_literal.replace("\\", "\\\\")
    symbols_literal_text = f"'{escaped_symbols_literal}'"
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
