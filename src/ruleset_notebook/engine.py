"""Shared deterministic rewrite engine used by every front end."""

from __future__ import annotations

import operator
from collections.abc import Mapping

from .domain import (
    Application,
    ComparisonGuard,
    EvaluationResult,
    Literal,
    RewriteEvent,
    Rule,
    StopReason,
    Term,
    Var,
)

Bindings = dict[str, Term]

GUARD_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def match(
    pattern: Term,
    subject: Term,
    env: Mapping[str, Term] | None = None,
) -> Bindings | None:
    current = dict(env or {})
    if isinstance(pattern, Var):
        if pattern.name in current:
            return current if current[pattern.name] == subject else None
        current[pattern.name] = subject
        return current
    if isinstance(pattern, Literal):
        return current if pattern == subject else None
    if isinstance(pattern, Application):
        if not isinstance(subject, Application):
            return None
        if pattern.symbol != subject.symbol or len(pattern.children) != len(
            subject.children
        ):
            return None
        for pattern_child, subject_child in zip(pattern.children, subject.children):
            matched = match(pattern_child, subject_child, current)
            if matched is None:
                return None
            current = matched
        return current
    return None


def substitute(template: Term, bindings: Mapping[str, Term]) -> Term:
    if isinstance(template, Var):
        return bindings.get(template.name, template)
    if isinstance(template, Literal):
        return template
    children = tuple(substitute(child, bindings) for child in template.children)
    if template.symbol in {"+", "-"} and len(children) == 2:
        left, right = children
        if (
            isinstance(left, Literal)
            and isinstance(left.value, (int, float))
            and isinstance(right, Literal)
            and isinstance(right.value, (int, float))
        ):
            if template.symbol == "+":
                return Literal(left.value + right.value)
            return Literal(left.value - right.value)
    if template.symbol in {"inc", "dec"} and len(children) == 1:
        value = children[0]
        if isinstance(value, Literal) and isinstance(value.value, int):
            amount = 1 if template.symbol == "inc" else -1
            return Literal(value.value + amount)
    return Application(template.symbol, children)


def guard_allows(guard: ComparisonGuard | None, bindings: Bindings) -> bool:
    if guard is None:
        return True
    value = bindings.get(guard.variable)
    compare = GUARD_OPERATORS[guard.operation]
    return (
        isinstance(value, Literal)
        and isinstance(value.value, int)
        and compare(value.value, guard.expected)
    )


def attempt_rewrite(
    term: Term, rules: list[Rule]
) -> tuple[Term, bool, Rule | None, Bindings]:
    for rule in rules:
        if not rule.enabled:
            continue
        bindings = match(rule.lhs, term)
        if bindings is not None and guard_allows(rule.guard, bindings):
            return substitute(rule.rhs, bindings), True, rule, bindings
    return term, False, None, {}


def rewrite_step(term: Term, rules: list[Rule]) -> tuple[Term, bool]:
    result, changed, _rule, _bindings = attempt_rewrite(term, rules)
    return result, changed


def evaluate(term: Term, rules: list[Rule]) -> Term:
    """Preserve the prototype's recursive innermost behavior."""
    if isinstance(term, Application):
        term = Application(
            term.symbol,
            tuple(evaluate(child, rules) for child in term.children),
        )
    result, changed = rewrite_step(term, rules)
    return evaluate(result, rules) if changed else result


def evaluate_with_trace(
    term: Term,
    rules: list[Rule],
    *,
    max_steps: int = 100,
    source_line: int = 0,
) -> EvaluationResult:
    current = term
    events: list[RewriteEvent] = []
    for index in range(1, max_steps + 1):
        next_term, changed, selected_rule, bindings = attempt_rewrite(current, rules)
        if not changed or selected_rule is None:
            return EvaluationResult(
                input_term=term,
                output_term=current,
                events=tuple(events),
                stop_reason=StopReason.NORMAL_FORM,
                source_line=source_line,
            )
        events.append(
            RewriteEvent(
                index=index,
                before=current,
                after=next_term,
                rule_name=selected_rule.name,
                rule_id=selected_rule.id,
                position=(),
                bindings=dict(bindings),
            )
        )
        current = next_term
    return EvaluationResult(
        input_term=term,
        output_term=current,
        events=tuple(events),
        stop_reason=StopReason.STEP_LIMIT,
        source_line=source_line,
    )


def format_trace_lines(result: EvaluationResult) -> list[str]:
    lines = [f"  0. {result.input_term}"]
    for event in result.events:
        binding_text = ", ".join(
            f"{name}={value}" for name, value in sorted(event.bindings.items())
        )
        lines.append(
            f"  {event.index}. {event.after} "
            f"[{event.rule_name}; {binding_text}; position=root]"
        )
    return lines
