"""Lower notebook rules to a Vine program that can be compiled to Ivy."""

from __future__ import annotations

import json
from collections.abc import Iterator
from importlib.resources import files

from ..domain import (
    Application,
    EvaluationSettings,
    GuardConjunction,
    GuardExpr,
    GuardGroup,
    Literal,
    Rule,
    Term,
    Var,
)
from ..engine import BUILTIN_ARITIES

Variants = dict[tuple[str, int], str]
_MAX_N32 = (1 << 32) - 1


class IvyCompilationError(ValueError):
    """The notebook uses a construct outside the supported Ivy subset."""


def _string(value: str) -> str:
    # Vine treats an unescaped opening brace as string interpolation.
    return json.dumps(value, ensure_ascii=False).replace("{", r"\{")


def _integer(literal: Literal) -> str:
    value = literal.value
    if not isinstance(value, int) or isinstance(value, bool):
        raise IvyCompilationError(
            f"Ivy code generation requires integer literals: {value!r}"
        )
    return f"{value}[Int]"


def _applications(term: Term) -> Iterator[tuple[str, int]]:
    if isinstance(term, Application):
        yield (term.symbol, len(term.children))
        for child in term.children:
            yield from _applications(child)


def _constructor(variant: str, fields: list[str]) -> str:
    return f"Term::{variant}({', '.join(fields)})"


def _emit_term(term: Term, variants: Variants, bindings: dict[str, str]) -> str:
    if isinstance(term, Var):
        return bindings[term.name]
    if isinstance(term, Literal):
        return _constructor("Number", [_integer(term)])
    variant = variants[(term.symbol, len(term.children))]
    return _constructor(
        variant, [_emit_term(child, variants, bindings) for child in term.children]
    )


def _emit_pattern(
    pattern: Term, variants: Variants, bindings: dict[str, str], checks: list[str]
) -> str:
    if isinstance(pattern, Application):
        variant = variants[(pattern.symbol, len(pattern.children))]
        return _constructor(
            variant,
            [
                _emit_pattern(child, variants, bindings, checks)
                for child in pattern.children
            ],
        )
    if isinstance(pattern, Literal):
        name = f"literal_{len(checks)}"
        checks.append(f"{name} == {_integer(pattern)}")
        return _constructor("Number", [name])

    if pattern.name in bindings:
        name = f"repeat_{len(checks)}"
        checks.append(f"terms_equal(&{bindings[pattern.name]}, &{name})")
        return name
    name = f"binding_{len(bindings)}"
    bindings[pattern.name] = name
    return name


def _guard_operand(term: Term, bindings: dict[str, str], lines: list[str]) -> str:
    if isinstance(term, Var):
        name = f"guard_{len(lines)}"
        lines.append(
            f"  assert &{bindings[term.name]} is &Term::Number({name}) "
            'else { Attempt::Fail("guard-evaluation-error") }'
        )
        return name
    if isinstance(term, Literal):
        return _integer(term)
    raise IvyCompilationError("Ivy guards require integer literals or bound variables")


def _emit_guard(guard: GuardExpr, bindings: dict[str, str], lines: list[str]) -> None:
    if isinstance(guard, GuardGroup):
        _emit_guard(guard.expression, bindings, lines)
    elif isinstance(guard, GuardConjunction):
        for item in guard.items:
            _emit_guard(item, bindings, lines)
    else:
        left = _guard_operand(guard.left.term, bindings, lines)
        right = _guard_operand(guard.right.term, bindings, lines)
        lines.append(
            f"  assert {left} {guard.operation} {right} else {{ Attempt::Miss() }}"
        )


def _emit_rule(rule: Rule, index: int, variants: Variants) -> str:
    bindings: dict[str, str] = {}
    checks: list[str] = []
    pattern = _emit_pattern(rule.lhs, variants, bindings, checks)
    lines = [
        f"fn rule_{index}(subject: &Term) -> Attempt {{",
        f"  assert subject is &{pattern} else {{ Attempt::Miss() }}",
    ]
    for check in checks:
        lines.append(f"  assert {check} else {{ Attempt::Miss() }}")
    if rule.guard is not None:
        _emit_guard(rule.guard, bindings, lines)
    rhs = _emit_term(rule.rhs, variants, bindings)
    name = _string(json.dumps(rule.name, ensure_ascii=True))
    lines.extend([f'  Attempt::Rewrite({rhs}, "rule", {name}, [])', "}"])
    return "\n".join(lines)


def _builtin_arms(symbol: str, variant: str, arity: int) -> list[str]:
    if symbol not in BUILTIN_ARITIES:
        return []
    invalid_pattern = _constructor(variant, ["_"] * arity)
    invalid = f'    &{invalid_pattern} {{ Attempt::Fail("invalid-operand") }}'
    if BUILTIN_ARITIES[symbol] != arity:
        return [invalid]

    names = ["a", "b"][:arity]
    operands = [_constructor("Number", [name]) for name in names]
    pattern = _constructor(variant, operands)
    if symbol == "div":
        body = [
            '      if b == 0[Int] { Attempt::Fail("division-by-zero") }',
            '      else { Attempt::Fail("unsupported-builtin-division") }',
        ]
    else:
        expression = {
            "inc": "a + 1[Int]",
            "dec": "a - 1[Int]",
            "add": "a + b",
            "+": "a + b",
            "sub": "a - b",
            "-": "a - b",
            "mul": "a * b",
        }[symbol]
        name = _string(json.dumps(symbol))
        body = [
            f'      Attempt::Rewrite(Term::Number({expression}), "built-in", '
            f"{name}, [])"
        ]
    return [f"    &{pattern} {{", *body, "    }", invalid]


def _emit_root(variants: Variants, rule_count: int) -> str:
    lines = ["fn try_root(subject: &Term) -> Attempt {"]
    for index in range(1, rule_count + 1):
        lines.extend(
            [
                f"  match rule_{index}(subject) {{",
                "    Attempt::Miss() {}",
                "    result { return result; }",
                "  }",
            ]
        )
    lines.append("  match subject {")
    for (symbol, arity), variant in variants.items():
        lines.extend(_builtin_arms(symbol, variant, arity))
    lines.extend(["    _ { Attempt::Miss() }", "  }", "}"])
    return "\n".join(lines)


def _emit_step(variants: Variants) -> str:
    lines = ["fn try_step(subject: &Term) -> Attempt {", "  match subject {"]
    for (_, arity), variant in variants.items():
        if arity == 0:
            continue
        children = [f"child_{index}" for index in range(arity)]
        lines.append(f"    &{_constructor(variant, children)} {{")
        for index, child in enumerate(children):
            replaced = [*children[:index], "next", *children[index + 1 :]]
            term = _constructor(variant, replaced)
            lines.extend(
                [
                    f"      match try_step(&{child}) {{",
                    "        Attempt::Miss() {}",
                    "        Attempt::Fail(code) { return Attempt::Fail(code); }",
                    "        Attempt::Rewrite(next, kind, name, path) {",
                    f"          path.push_front({index});",
                    f"          return Attempt::Rewrite({term}, kind, name, path);",
                    "        }",
                    "      }",
                ]
            )
        lines.append("    }")
    lines.extend(["    _ {}", "  }", "  try_root(subject)", "}"])
    return "\n".join(lines)


def _emit_term_helpers(variants: Variants) -> str:
    depth_arms = ["    &Term::Number(_) { 1 }"]
    render_arms = ['    &Term::Number(value) { "{value}" }']
    equality_arms = ["    (&Term::Number(a), &Term::Number(b)) { a == b }"]
    for (symbol, arity), variant in variants.items():
        left = [f"a_{index}" for index in range(arity)]
        right = [f"b_{index}" for index in range(arity)]
        pattern = _constructor(variant, left)
        other = _constructor(variant, right)
        equal = (
            " and ".join(f"terms_equal(&{a}, &{b})" for a, b in zip(left, right))
            or "true"
        )
        equality_arms.append(f"    (&{pattern}, &{other}) {{ {equal} }}")
        fields = ", ".join(f"{{render(&{name})}}" for name in left)
        render_arms.extend(
            [
                f"    &{pattern} {{",
                f"      let symbol = {_string(symbol)};",
                f'      "{{symbol}}({fields})"',
                "    }",
            ]
        )
        depth_arms.extend(
            [
                f"    &{pattern} {{",
                "      let deepest = 0;",
                *(
                    f"      let depth = term_depth(&{name}); "
                    "if depth > deepest { deepest = depth; }"
                    for name in left
                ),
                "      1 + deepest",
                "    }",
            ]
        )
    sections = [
        ["fn term_depth(subject: &Term) -> N32 {", "  match subject {", *depth_arms],
        ["fn render(subject: &Term) -> String {", "  match subject {", *render_arms],
        [
            "fn terms_equal(a: &Term, b: &Term) -> Bool {",
            "  match (a, b) {",
            *equality_arms,
            "    _ { false }",
        ],
    ]
    return "\n\n".join("\n".join([*lines, "  }", "}"]) for lines in sections)


def generate_vine(
    rules: list[Rule], inputs: list[tuple[int, Term]], settings: EvaluationSettings
) -> str:
    """Generate the Vine intermediate for the notebook's integer rewrite subset."""
    if max(settings.max_steps, settings.max_depth) > _MAX_N32:
        raise IvyCompilationError(f"Ivy evaluation limits must be at most {_MAX_N32}")

    terms = [term for rule in rules for term in (rule.lhs, rule.rhs)]
    terms.extend(term for _, term in inputs)
    signatures = dict.fromkeys(
        signature for term in terms for signature in _applications(term)
    )
    variants = {signature: f"App{index}" for index, signature in enumerate(signatures)}
    declaration = ["enum* Term {", "  Number(Int),"]
    for (_, arity), variant in variants.items():
        fields = ", ".join(["Term"] * arity)
        declaration.append(f"  {variant}({fields}),")
    declaration.append("}")

    sections = ["// Generated by Ruleset Notebook.", "\n".join(declaration)]
    for index, rule in enumerate(rules, 1):
        try:
            sections.append(_emit_rule(rule, index, variants))
        except IvyCompilationError as error:
            raise IvyCompilationError(
                f"rules line {rule.source_line}: {error}"
            ) from error

    main = ["pub fn main(&io: &IO) {", '  io.println("TRACE 1");']
    for index, (source_line, term) in enumerate(inputs, 1):
        try:
            value = _emit_term(term, variants, {})
        except IvyCompilationError as error:
            raise IvyCompilationError(f"inputs line {source_line}: {error}") from error
        main.append(
            f"  evaluate_input(&io, {value}, {index}, {source_line}, "
            f"{settings.max_steps}, {settings.max_depth});"
        )
    main.append("}")
    runtime = files(__package__).joinpath("ivy_runtime.vi").read_text(encoding="utf-8")
    sections.extend(
        [
            _emit_term_helpers(variants),
            _emit_root(variants, len(rules)),
            _emit_step(variants),
            runtime.rstrip(),
            "\n".join(main),
        ]
    )
    return "\n\n".join(sections) + "\n"
