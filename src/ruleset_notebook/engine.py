"""Shared deterministic rewrite engine used by every front end."""

from __future__ import annotations

import operator
from collections.abc import Mapping
from typing import cast

from .domain import (
    Application,
    EvaluationResult,
    GuardComparison,
    GuardConjunction,
    GuardEvaluationError,
    GuardExpr,
    GuardGroup,
    GuardValue,
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


def _guard_value(value: GuardValue, bindings: Bindings) -> object:
    term = value.term
    if isinstance(term, Var):
        bound = bindings.get(term.name)
        if bound is None:
            raise GuardEvaluationError(
                f"guard variable {term.name!r} has no match binding"
            )
        term = bound
    if not isinstance(term, Literal):
        raise GuardEvaluationError("guards can compare literal values only")
    return term.value


def _compare_guard(comparison: GuardComparison, bindings: Bindings) -> bool:
    left = _guard_value(comparison.left, bindings)
    right = _guard_value(comparison.right, bindings)
    if comparison.operation in {"==", "!="}:
        equal = type(left) is type(right) and left == right
        return equal if comparison.operation == "==" else not equal
    numeric = (int, float)
    if isinstance(left, bool) or isinstance(right, bool):
        raise GuardEvaluationError("boolean values cannot be ordered")
    if not (
        (isinstance(left, numeric) and isinstance(right, numeric))
        or (isinstance(left, str) and isinstance(right, str))
    ):
        raise GuardEvaluationError("guard values have incompatible types")
    try:
        return cast(bool, GUARD_OPERATORS[comparison.operation](left, right))
    except TypeError as error:
        raise GuardEvaluationError("guard values have incompatible types") from error


def evaluate_guard(guard: GuardExpr, bindings: Bindings) -> bool:
    if isinstance(guard, GuardGroup):
        return evaluate_guard(guard.expression, bindings)
    if isinstance(guard, GuardConjunction):
        return all(evaluate_guard(item, bindings) for item in guard.items)
    return _compare_guard(guard, bindings)


def guard_allows(guard: GuardExpr | None, bindings: Bindings) -> bool:
    if guard is None:
        return True
    return evaluate_guard(guard, bindings)


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
        fields = [f"rule:{event.rule_name}"]
        fields.extend(
            f"{name}:{value}" for name, value in sorted(event.bindings.items())
        )
        position = (
            "root"
            if not event.position
            else ".".join(str(index) for index in event.position)
        )
        fields.append(f"position:{position}")
        lines.append(f"  {event.index}. {event.after} {{{', '.join(fields)}}}")
    return lines
