from __future__ import annotations

import re
from typing import Any, List, cast

from sympy import Basic, Mul, Pow, Symbol, Tuple
from sympy.core.function import AppliedUndef


def _parse_part(part: str):
    try:
        from sympy.parsing.latex import parse_latex
    except ImportError as err:  # pragma: no cover - import path environment-specific
        raise RuntimeError("LaTeX parsing requires sympy in the active environment.") from err

    # Prefer the Lark backend because it avoids the fragile antlr4 runtime pin.
    # For wrapped symbols with explicit subscripts (e.g. \mathscr{V}_2),
    # Lark can silently drop terms, so force the default backend.
    if re.search(
        r"\\(?:mathscr|mathcal|mathbf|mathrm|mathit|mathsf|mathtt|boldsymbol)\s*\{[^{}]+\}\s*_",
        part,
    ):
        return cast(Any, parse_latex)(part)
    if re.search(r"\bZ_\{\d{6,}\}", part):
        return cast(Any, parse_latex)(part)

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
    raw = re.sub(r"^\s*\$\$(.*)\$\$\s*$", r"\1", raw, flags=re.DOTALL).strip()
    # Handle common copy/paste form where slashes are double-escaped.
    raw = raw.replace("\\\\", "\\")
    # Common thermo shorthand: d'Q, d'W -> dQ, dW.
    raw = re.sub(r"\bd'\s*([A-Za-z][A-Za-z0-9_]*)", r"d\1", raw)
    # Also support LaTeX differential prime notation with braces:
    # \mathrm{d}'{q_r} -> dq_r
    raw = re.sub(
        r"\\mathrm\s*\{\s*d\s*\}\s*'\s*(?:\{\s*([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?)\s*\}|([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?))",
        lambda match: f"d{match.group(1) or match.group(2)}",
        raw,
    )
    # Normalize differential notation that SymPy misparses:
    # \mathrm{d}{T} -> dT
    # \mathrm{d}{T_{s}} -> dT_{s}
    raw = re.sub(
        r"\\mathrm\s*\{\s*d\s*\}\s*\{\s*([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?)\s*\}",
        r"d\1",
        raw,
    )

    def sanitize_text_label(label: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]", "", label.strip())
        return cleaned or "text"

    def sanitize_symbol_label(label: str) -> str:
        normalized = label.strip()
        normalized = normalized.replace("\\left", "").replace("\\right", "")
        normalized = re.sub(r"_\{([^{}]+)\}", r"_\1", normalized)
        normalized = re.sub(r"[^0-9A-Za-z_]", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if not normalized:
            normalized = "sym"
        if normalized[0].isdigit():
            normalized = f"sym_{normalized}"
        return normalized

    ordinary_derivative_placeholders: dict[str, str] = {}
    ordinary_derivative_index = 0

    def rewrite_ordinary_derivative(match: re.Match[str]) -> str:
        nonlocal ordinary_derivative_index
        dependent = sanitize_symbol_label(
            match.group("dep") or match.group("dep_braced") or match.group("dep_bare") or ""
        )
        wrt = sanitize_symbol_label(
            match.group("wrt") or match.group("wrt_braced") or match.group("wrt_bare") or ""
        )
        placeholder_id = 950000 + ordinary_derivative_index
        placeholder = f"Z_{{{placeholder_id}}}"
        ordinary_derivative_index += 1
        ordinary_derivative_placeholders[placeholder] = f"d{dependent}_d{wrt}"
        return placeholder

    # Treat ordinary differential quotients as atomic symbols for equation entry:
    # \frac{\mathrm{d}{P}}{\mathrm{d}{T}} -> dP_dT
    raw = re.sub(
        r"\\(?:d?frac)\s*\{\s*(?:\\mathrm\s*\{\s*d\s*\}\s*\{\s*(?P<dep>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?)\s*\}|d\s*\{\s*(?P<dep_braced>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?)\s*\}|d\s*(?P<dep_bare>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?))\s*\}\s*\{\s*(?:\\mathrm\s*\{\s*d\s*\}\s*\{\s*(?P<wrt>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?)\s*\}|d\s*\{\s*(?P<wrt_braced>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?)\s*\}|d\s*(?P<wrt_bare>[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+|_\{[A-Za-z0-9]+\})?))\s*\}",
        rewrite_ordinary_derivative,
        raw,
    )

    # SymPy parses \frac{l}{T \left(...\right)} as (l/T)*(...) rather than
    # l/(T*(...)). Make the implicit product in the denominator explicit.
    raw = re.sub(
        r"(\\(?:d?frac)\s*\{(?:[^{}]|\{[^{}]*\})+\}\s*\{\s*[A-Za-z][A-Za-z0-9]*(?:_\{[^{}]+\}|_[A-Za-z0-9]+)?\s+)(\\left)",
        r"\1\\cdot \2",
        raw,
    )

    delta_placeholders: dict[str, str] = {}
    delta_symbol_literals: dict[str, str] = {}
    delta_index = 0

    def rewrite_delta_symbol(match: re.Match[str]) -> str:
        nonlocal delta_index
        token = (match.group(1) or match.group(2) or "").strip()
        if not token:
            return match.group(0)
        token_name = re.sub(r"[^0-9A-Za-z_]", "_", token)
        token_name = re.sub(r"_+", "_", token_name).strip("_")
        if not token_name:
            token_name = "sym"
        if token_name[0].isdigit():
            token_name = f"sym_{token_name}"
        python_name = f"d{token_name}"
        placeholder = f"Z_{{{940000 + delta_index}}}"
        delta_index += 1
        delta_placeholders[placeholder] = python_name
        delta_symbol_literals[python_name] = rf"\Delta {token}"
        return placeholder

    raw = re.sub(
        r"\\Delta\s*(?:\{([^{}]+)\}|([A-Za-z][A-Za-z0-9_]*))",
        rewrite_delta_symbol,
        raw,
    )

    text_subscript_symbol_names: set[str] = set()
    for match in re.finditer(
        r"([A-Za-z][A-Za-z0-9]*)\s*_\s*(?:\\text\s*\{([^{}]+)\}|\{\s*\\text\s*\{([^{}]+)\}\s*\})",
        raw,
    ):
        base = match.group(1)
        label = sanitize_text_label(match.group(2) or match.group(3) or "")
        text_subscript_symbol_names.add(f"{base}_{label}")

    constrained_partial_placeholders: dict[str, str] = {}
    constrained_partial_specs: dict[str, tuple[str, str, str]] = {}
    constrained_partial_index = 0

    def rewrite_constrained_partial(match: re.Match[str]) -> str:
        nonlocal constrained_partial_index
        dependent = sanitize_symbol_label(
            (match.group("dep_braced") or match.group("dep_bare") or "")
        )
        wrt = sanitize_symbol_label((match.group("wrt_braced") or match.group("wrt_bare") or ""))
        hold_text = match.group("hold_text") or match.group("hold_text_braced")
        hold_braced = match.group("hold_braced")
        hold_bare = match.group("hold_bare")
        hold_command = match.group("hold_cmd")
        hold_raw = hold_text or hold_braced or hold_bare or hold_command or ""
        hold = sanitize_symbol_label(hold_raw)
        partial_symbol_name = f"partial__{dependent}__{wrt}__{hold}"
        placeholder_id = 930000 + constrained_partial_index
        placeholder = f"Z_{{{placeholder_id}}}"
        constrained_partial_index += 1
        constrained_partial_placeholders[placeholder] = partial_symbol_name
        constrained_partial_specs[partial_symbol_name] = (dependent, wrt, hold)
        return placeholder

    # SymPy's LaTeX parser often drops constrained partial derivative factors.
    # Rewrite them to parser-safe placeholders and restore semantic names later.
    raw = re.sub(
        r"(?:\\left\()?\s*\\(?:d?frac)\s*\{\s*\\partial\s*(?:\{(?P<dep_braced>\\?[A-Za-z]+(?:_\{[A-Za-z0-9]+\}|_[A-Za-z0-9]+)?)\}|(?P<dep_bare>\\?[A-Za-z]+(?:_\{[A-Za-z0-9]+\}|_[A-Za-z0-9]+)?))\s*\}\s*\{\s*\\partial\s*(?:\{(?P<wrt_braced>\\?[A-Za-z]+(?:_\{[A-Za-z0-9]+\}|_[A-Za-z0-9]+)?)\}|(?P<wrt_bare>\\?[A-Za-z]+(?:_\{[A-Za-z0-9]+\}|_[A-Za-z0-9]+)?))\s*\}\s*(?:\\right\))?\s*_\s*(?:\\text\s*\{(?P<hold_text>[^{}]+)\}|\{\s*\\text\s*\{(?P<hold_text_braced>[^{}]+)\}\s*\}|\{(?P<hold_braced>\\?[A-Za-z]+(?:_\{[A-Za-z0-9]+\}|_[A-Za-z0-9]+)?)\}|(?P<hold_bare>\\?[A-Za-z]+(?:_\{[A-Za-z0-9]+\}|_[A-Za-z0-9]+)?)|\\(?P<hold_cmd>[A-Za-z]+))",
        rewrite_constrained_partial,
        raw,
    )

    wrapper_text_subscript_placeholders: dict[str, str] = {}
    wrapper_text_subscript_index = 0

    def rewrite_wrapper_with_subscript(match: re.Match[str]) -> str:
        nonlocal wrapper_text_subscript_index
        wrapper = match.group(1)
        base = re.sub(r"[^A-Za-z0-9]", "", match.group(2))
        text_label = match.group(3) or match.group(4)
        braced_label = match.group(5)
        bare_label = match.group(6)
        raw_label = text_label or braced_label or bare_label or ""
        label = sanitize_text_label(raw_label)
        placeholder_id = 910000 + wrapper_text_subscript_index
        placeholder = f"Z_{{{placeholder_id}}}"
        wrapper_text_subscript_index += 1
        wrapper_text_subscript_placeholders[placeholder] = f"{wrapper}{base}_{label}"
        return placeholder

    # SymPy's LaTeX parser can fail on wrapped symbols with subscripts such as
    # \mathscr{F}_\text{fric.} or \mathscr{V}_2. Rewrite these to parser-safe
    # placeholders and restore semantic symbol names after parsing.
    raw = re.sub(
        r"\\(mathscr|mathcal|mathbf|mathrm|mathit|mathsf|mathtt|boldsymbol)\s*\{([^{}]+)\}\s*_\s*(?:\\text\s*\{([^{}]+)\}|\{\s*\\text\s*\{([^{}]+)\}\s*\}|\{([^{}]+)\}|([A-Za-z0-9]+))",
        rewrite_wrapper_with_subscript,
        raw,
    )

    wrapper_symbol_placeholders: dict[str, str] = {}
    wrapper_symbol_index = 0

    def rewrite_wrapper_symbol(match: re.Match[str]) -> str:
        nonlocal wrapper_symbol_index
        wrapper = match.group(1)
        base = re.sub(r"[^A-Za-z0-9]", "", match.group(2))
        placeholder_id = 900000 + wrapper_symbol_index
        placeholder = f"Z_{{{placeholder_id}}}"
        wrapper_symbol_index += 1
        wrapper_symbol_placeholders[placeholder] = f"{wrapper}{base}"
        return placeholder

    # Rewrite standalone wrapped symbols before parsing so \mathscr{H}\,dM
    # stays mathscrH*dM instead of becoming the ambiguous product H*dM*mathscr.
    raw = re.sub(
        r"\\(mathscr|mathcal|mathbf|mathrm|mathit|mathsf|mathtt|boldsymbol)\s*\{([^{}]+)\}(?!\s*_)",
        rewrite_wrapper_symbol,
        raw,
    )

    # Keep text subscripts as atomic names by converting them to one-token commands:
    # T_\text{boil} -> T_{\boil}. SymPy then parses this as T_{boil}.
    def rewrite_text_subscript(match: re.Match[str]) -> str:
        command = sanitize_text_label(match.group(1))
        return f"_{{\\{command}}}"

    raw = re.sub(r"_\\text\s*\{([^{}]+)\}", rewrite_text_subscript, raw)

    text_symbol_placeholders: dict[str, str] = {}
    text_symbol_index = 0

    def rewrite_text_symbol(match: re.Match[str]) -> str:
        nonlocal text_symbol_index
        symbol_name = sanitize_symbol_label(match.group(1))
        placeholder_id = 920000 + text_symbol_index
        placeholder = f"Z_{{{placeholder_id}}}"
        text_symbol_index += 1
        text_symbol_placeholders[placeholder] = symbol_name
        return placeholder

    # Treat standalone text labels like \text{const} as one symbolic atom.
    raw = re.sub(r"\\text\s*\{([^{}]+)\}", rewrite_text_symbol, raw)

    parts = [part.strip() for part in raw.split("=") if part.strip()]
    parsed_exprs: List[Any] = [_parse_part(part) for part in parts]
    all_placeholders: dict[str, str] = {}
    all_placeholders.update(ordinary_derivative_placeholders)
    all_placeholders.update(delta_placeholders)
    all_placeholders.update(wrapper_symbol_placeholders)
    all_placeholders.update(wrapper_text_subscript_placeholders)
    all_placeholders.update(text_symbol_placeholders)
    all_placeholders.update(constrained_partial_placeholders)
    if all_placeholders:
        placeholder_name_map = {}
        for placeholder, target in all_placeholders.items():
            target_symbol = Symbol(target)
            placeholder_name_map[placeholder] = target_symbol
            placeholder_name_map[sanitize_symbol_label(placeholder)] = target_symbol

        def replace_placeholders(expr: Any) -> Any:
            if not isinstance(expr, Basic):
                return expr
            return expr.xreplace(
                {
                    symbol: placeholder_name_map[str(symbol)]
                    for symbol in expr.atoms(Symbol)
                    if str(symbol) in placeholder_name_map
                }
            )

        parsed_exprs = [replace_placeholders(expr) for expr in parsed_exprs]

    def collapse_differential_tuples(expr: Any) -> Any:
        # parse_latex may represent tokens like dU or dP as tuple(d, U/P),
        # and those tuples can appear nested inside larger expressions.
        if (
            isinstance(expr, Tuple)
            and len(expr) == 2
            and all(getattr(item, "is_Symbol", False) for item in expr)
            and str(expr[0]) == "d"
        ):
            return Symbol(f"d{expr[1]}")
        if (
            isinstance(expr, tuple)
            and len(expr) == 2
            and all(getattr(item, "is_Symbol", False) for item in expr)
            and str(expr[0]) == "d"
        ):
            return Symbol(f"d{expr[1]}")
        if isinstance(expr, tuple):
            return tuple(collapse_differential_tuples(item) for item in expr)
        if isinstance(expr, Basic):
            rebuilt_args = tuple(collapse_differential_tuples(arg) for arg in expr.args)
            if rebuilt_args != expr.args:
                return expr.func(*rebuilt_args)
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
    if all_placeholders:
        parsed_exprs = [replace_placeholders(expr) for expr in parsed_exprs]

    def normalize_sympy_calls(text: str) -> str:
        normalized = re.sub(r"(?<!spp\.)(?<!sp\.)Eq\(", "spp.Eq(", text)
        for func_name in (
            "sqrt",
            "log",
            "exp",
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "Integral",
            "Derivative",
        ):
            normalized = re.sub(
                rf"(?<!spp\.)(?<!sp\.)\b{func_name}\(",
                f"spp.{func_name}(",
                normalized,
            )
        return normalized

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
        if not normalized.startswith("partial__"):
            normalized = re.sub(r"_+", "_", normalized).strip("_")
        if not normalized:
            normalized = "sym"
        if normalized[0].isdigit():
            normalized = f"sym_{normalized}"
        return normalized

    def to_latex_symbol_name(name: str) -> str:
        constrained_partial_match = re.fullmatch(
            r"partial__(.+?)__(.+?)__(.+)", name
        )
        if constrained_partial_match:
            dependent, wrt, hold = constrained_partial_match.groups()
            hold_latex = hold
            if hold.isalpha() and len(hold) > 1:
                hold_latex = f"\\text{{{hold}}}"
            return (
                f"\\left(\\frac{{\\partial {dependent}}}{{\\partial {wrt}}}\\right)"
                f"_{{{hold_latex}}}"
            )
        for command in latex_wrapper_commands:
            if not name.startswith(command):
                continue
            wrapped = name[len(command) :]
            if not wrapped:
                continue
            wrapped_subscript_match = re.fullmatch(
                r"([A-Za-z0-9]+)_([A-Za-z0-9]+)", wrapped
            )
            if wrapped_subscript_match:
                wrapped_base, wrapped_subscript = wrapped_subscript_match.groups()
                if wrapped_subscript.isalpha() and len(wrapped_subscript) > 1:
                    return f"\\{command}{{{wrapped_base}}}_\\text{{{wrapped_subscript}}}"
                return f"\\{command}{{{wrapped_base}}}_{{{wrapped_subscript}}}"
            if re.fullmatch(r"[A-Za-z0-9_]+", wrapped):
                return f"\\{command}{{{wrapped}}}"
        subscript_match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)_([A-Za-z][A-Za-z0-9]*)", name)
        if subscript_match:
            base, subscript = subscript_match.groups()
            if name in text_subscript_symbol_names and subscript.isalpha() and len(subscript) > 1:
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

    sympy_text = "\n".join(normalize_sympy_calls(str(expr)) for expr in expressions)

    for partial_symbol_name, (dependent, wrt, hold) in constrained_partial_specs.items():
        partial_call = f"spp.partial({dependent}, {wrt}, hold={hold})"
        sympy_text = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(partial_symbol_name)}(?![A-Za-z0-9_])",
            partial_call,
            sympy_text,
        )

    symbol_names_set = {
        str(symbol)
        for expr in parsed_exprs
        for symbol in extract_declared_symbols(expr)
    }
    for partial_symbol_name, (dependent, wrt, hold) in constrained_partial_specs.items():
        if partial_symbol_name in symbol_names_set:
            symbol_names_set.remove(partial_symbol_name)
            symbol_names_set.update({dependent, wrt, hold})

    symbol_names = sorted(
        {
            symbol_name
            for symbol_name in symbol_names_set
        }
    )
    delta_symbol_names = sorted(name for name in symbol_names if name in delta_symbol_literals)
    regular_symbol_names = sorted(name for name in symbol_names if name not in delta_symbol_literals)
    symbol_literal_names = [to_latex_symbol_name(name) for name in regular_symbol_names]
    symbols_literal = " ".join(symbol_literal_names)
    escaped_symbols_literal = symbols_literal.replace("\\", "\\\\")
    symbols_literal_text = f"'{escaped_symbols_literal}'"
    regular_symbols_line = (
        f"{', '.join(regular_symbol_names)} = spp.symbols({symbols_literal_text})"
        if regular_symbol_names
        else ""
    )
    delta_symbol_lines: list[str] = []
    for name in delta_symbol_names:
        escaped_delta_literal = delta_symbol_literals[name].replace("\\", "\\\\")
        delta_symbol_lines.append(f"{name} = spp.Symbol('{escaped_delta_literal}')")
    declaration_lines = [*delta_symbol_lines]
    if regular_symbols_line:
        declaration_lines.append(regular_symbols_line)
    symbols_line = "\n".join(declaration_lines)
    code = f"{symbols_line}\n{sympy_text}" if symbols_line else sympy_text

    return {
        "sympy": sympy_text,
        "symbols": symbol_names,
        "symbols_line": symbols_line,
        "code": code,
    }


def convert_latex_to_sympy(latex: str) -> str:
    return str(convert_latex_to_bundle(latex)["sympy"])
