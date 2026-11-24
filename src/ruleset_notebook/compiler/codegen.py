"""Lower the notebook's parsed rules and inputs to a standalone C program."""

from __future__ import annotations

import json
from importlib.resources import files

from ..domain import (
    EvaluationSettings,
    GuardConjunction,
    GuardExpr,
    GuardGroup,
    Literal,
    Rule,
    Term,
    Var,
)
from ..language import parse_inputs, parse_rules

MIN_INTEGER = -(1 << 63)
MAX_INTEGER = (1 << 63) - 1
MAX_LIMIT = (1 << 31) - 1


class CompilationError(ValueError):
    """Source uses a construct outside the C backend's supported subset."""


def _c_string(value: str) -> str:
    """Emit an ASCII C string literal containing the UTF-8 bytes of value."""
    escaped = "".join(
        chr(byte) if 32 <= byte <= 126 and byte not in b'"\\?' else f"\\{byte:03o}"
        for byte in value.encode("utf-8")
    )
    return f'"{escaped}"'


def _integer(literal: Literal) -> str:
    value = literal.value
    if not isinstance(value, int) or isinstance(value, bool):
        raise CompilationError(
            f"C code generation requires integer literals: {value!r}"
        )
    if not MIN_INTEGER <= value <= MAX_INTEGER:
        raise CompilationError(f"integer is outside the signed 64-bit range: {value}")
    if value == MIN_INTEGER:
        return "INT64_MIN"
    if value < 0:
        return f"(-INT64_C({-value}))"
    return f"INT64_C({value})"


def _emit_pattern(
    pattern: Term, subject: str, bindings: dict[str, str], body: list[str]
) -> None:
    if isinstance(pattern, Var):
        previous = bindings.setdefault(pattern.name, subject)
        if previous != subject:
            body.append(f"if (!terms_equal({previous}, {subject})) return NO_MATCH;")
    elif isinstance(pattern, Literal):
        body.append(
            f"if (!is_integer({subject}) || {subject}->value != {_integer(pattern)}) "
            "return NO_MATCH;"
        )
    else:
        body.append(
            f"if (!is_application({subject}, {_c_string(pattern.symbol)}, "
            f"{len(pattern.children)})) return NO_MATCH;"
        )
        for index, child in enumerate(pattern.children):
            _emit_pattern(child, f"{subject}->children[{index}]", bindings, body)


def _comparison_operand(
    operand: Term, bindings: dict[str, str], body: list[str]
) -> str:
    if isinstance(operand, Var):
        reference = bindings[operand.name]
        body.extend(
            [
                f"if (!is_integer({reference})) {{",
                '    evaluation->error = "guard-evaluation-error";',
                "    return REWRITE_ERROR;",
                "}",
            ]
        )
        return f"{reference}->value"
    if isinstance(operand, Literal):
        return _integer(operand)
    raise CompilationError("C guards require integer literals or bound variables")


def _emit_guard(guard: GuardExpr, bindings: dict[str, str], body: list[str]) -> None:
    if isinstance(guard, GuardGroup):
        _emit_guard(guard.expression, bindings, body)
    elif isinstance(guard, GuardConjunction):
        for item in guard.items:
            _emit_guard(item, bindings, body)
    else:
        left = _comparison_operand(guard.left.term, bindings, body)
        right = _comparison_operand(guard.right.term, bindings, body)
        body.append(f"if (!({left} {guard.operation} {right})) return NO_MATCH;")


def _emit_term(term: Term, bindings: dict[str, str], body: list[str]) -> str:
    if isinstance(term, Var):
        return bindings[term.name]
    if isinstance(term, Literal):
        constructor = f"make_integer(evaluation, {_integer(term)})"
    else:
        children = [_emit_term(child, bindings, body) for child in term.children]
        references = (
            "(const Term *[]){" + ", ".join(children) + "}" if children else "NULL"
        )
        constructor = (
            f"make_application(evaluation, {_c_string(term.symbol)}, "
            f"{len(children)}, {references})"
        )
    name = f"term_{len(body)}"
    body.append(f"const Term *{name} = {constructor};")
    return name


def _emit_rule(rule: Rule, index: int) -> str:
    # A rule that only returns a binding may make no use of its evaluation state.
    body = ["(void)evaluation;"]
    bindings: dict[str, str] = {}
    _emit_pattern(rule.lhs, "subject", bindings, body)
    if rule.guard is not None:
        _emit_guard(rule.guard, bindings, body)
    replacement = _emit_term(rule.rhs, bindings, body)
    body.extend([f"*replacement = {replacement};", "return REWRITTEN;"])
    return "\n".join(
        [
            f"static RewriteStatus rule_{index}(Evaluation *evaluation,",
            "    const Term *subject, const Term **replacement)",
            "{",
            *(f"    {line}" for line in body),
            "}",
        ]
    )


def _emit_main(inputs: list[tuple[int, Term]], settings: EvaluationSettings) -> str:
    lines = ["int main(void)", "{", '    puts("TRACE 1");']
    for index, (source_line, term) in enumerate(inputs, 1):
        body = ["Evaluation state = {0};", "Evaluation *evaluation = &state;"]
        try:
            reference = _emit_term(term, {}, body)
        except CompilationError as error:
            raise CompilationError(f"inputs line {source_line}: {error}") from error
        body.extend(
            [
                f"run_input(evaluation, {index}, {source_line}, {reference},",
                "    rules, sizeof(rules) / sizeof(rules[0]),",
                f"    {settings.max_steps}, {settings.max_depth});",
                "release_terms(evaluation);",
            ]
        )
        lines.extend(["    {", *(f"        {line}" for line in body), "    }"])
    lines.extend(["    return EXIT_SUCCESS;", "}"])
    return "\n".join(lines)


def _generate_program(
    rules: list[Rule], inputs: list[tuple[int, Term]], settings: EvaluationSettings
) -> str:
    if max(settings.max_steps, settings.max_depth) > MAX_LIMIT:
        raise CompilationError(f"evaluation limits must be at most {MAX_LIMIT}")
    runtime = files(__package__).joinpath("runtime.c").read_text(encoding="ascii")
    sections = ["/* Generated by Ruleset Notebook. */", runtime.rstrip()]
    entries = ["static const RuleEntry rules[] = {"]
    for index, rule in enumerate(rules, 1):
        try:
            sections.append(_emit_rule(rule, index))
        except CompilationError as error:
            raise CompilationError(f"rules line {rule.source_line}: {error}") from error
        trace_name = _c_string(json.dumps(rule.name, ensure_ascii=True))
        entries.append(f"    {{{trace_name}, rule_{index}}},")
    entries.append("};")
    sections.extend(["\n".join(entries), _emit_main(inputs, settings)])
    return "\n\n".join(sections) + "\n"


def generate_c(
    rules_text: str, inputs_text: str, settings: EvaluationSettings | None = None
) -> str:
    """Parse notebook source and return a self-contained C translation unit."""
    return _generate_program(
        parse_rules(rules_text),
        parse_inputs(inputs_text),
        settings or EvaluationSettings(),
    )
