"""Shared deterministic rewrite engine used by every front end."""

from __future__ import annotations

import operator
from collections.abc import Callable, Iterator, Mapping
from types import MappingProxyType
from typing import cast

from .domain import (
    Application,
    DivisionByZeroError,
    EngineError,
    EvaluationResult,
    GuardComparison,
    GuardConjunction,
    GuardEvaluationError,
    GuardExpr,
    GuardGroup,
    GuardValue,
    InvalidOperandError,
    Literal,
    RewriteEvent,
    RewriteKind,
    Rule,
    StopReason,
    Term,
    TermPosition,
    UnboundVariableError,
    Var,
)

Bindings = dict[str, Term]
CancellationCheck = Callable[[], bool]

BUILTIN_ARITIES = {
    "inc": 1,
    "dec": 1,
    "add": 2,
    "sub": 2,
    "mul": 2,
    "div": 2,
    "+": 2,
    "-": 2,
}


class _EvaluationCancelled(Exception):
    pass


def _term_equal(left: Term, right: Term) -> bool:
    if isinstance(left, Literal) and isinstance(right, Literal):
        return type(left.value) is type(right.value) and left.value == right.value
    return left == right


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
            return current if _term_equal(current[pattern.name], subject) else None
        current[pattern.name] = subject
        return current
    if isinstance(pattern, Literal):
        return current if _term_equal(pattern, subject) else None
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
        if template.name not in bindings:
            raise UnboundVariableError(
                f"cannot substitute unbound variable {template.name!r}"
            )
        return bindings[template.name]
    if isinstance(template, Literal):
        return template
    return Application(
        template.symbol,
        tuple(substitute(child, bindings) for child in template.children),
    )


def _numeric_value(term: Term, symbol: str) -> int | float:
    if (
        not isinstance(term, Literal)
        or isinstance(term.value, bool)
        or not isinstance(term.value, (int, float))
    ):
        raise InvalidOperandError(f"{symbol} requires numeric literal operands")
    return term.value


def attempt_builtin_rewrite(term: Term) -> tuple[Term, bool, str | None]:
    """Reduce one documented numeric built-in when ``term`` names one."""
    if not isinstance(term, Application) or term.symbol not in BUILTIN_ARITIES:
        return term, False, None
    expected_arity = BUILTIN_ARITIES[term.symbol]
    if len(term.children) != expected_arity:
        raise InvalidOperandError(
            f"{term.symbol} requires {expected_arity} operand"
            f"{'s' if expected_arity != 1 else ''}"
        )
    values = tuple(_numeric_value(child, term.symbol) for child in term.children)
    if term.symbol == "inc":
        result = values[0] + 1
    elif term.symbol == "dec":
        result = values[0] - 1
    elif term.symbol in {"add", "+"}:
        result = values[0] + values[1]
    elif term.symbol in {"sub", "-"}:
        result = values[0] - values[1]
    elif term.symbol == "mul":
        result = values[0] * values[1]
    else:
        if values[1] == 0:
            raise DivisionByZeroError("div cannot divide by zero")
        result = values[0] / values[1]
    return Literal(result), True, term.symbol


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


def term_at_position(term: Term, position: TermPosition) -> Term:
    """Read the subtree identified by an ordered child-index path."""
    current = term
    for index in position:
        if not isinstance(current, Application):
            raise ValueError(f"position {position!r} descends through a leaf term")
        if index < 0 or index >= len(current.children):
            raise IndexError(f"child index {index} is outside position {position!r}")
        current = current.children[index]
    return current


def replace_at_position(term: Term, position: TermPosition, replacement: Term) -> Term:
    """Return a new term with one subtree replaced, preserving the input term."""
    if not position:
        return replacement
    if not isinstance(term, Application):
        raise ValueError(f"position {position!r} descends through a leaf term")
    index, *remainder = position
    if index < 0 or index >= len(term.children):
        raise IndexError(f"child index {index} is outside position {position!r}")
    children = list(term.children)
    children[index] = replace_at_position(
        children[index], tuple(remainder), replacement
    )
    return Application(term.symbol, tuple(children))


def iter_innermost_positions(
    term: Term, position: TermPosition = ()
) -> Iterator[TermPosition]:
    """Yield positions in deterministic left-to-right post-order."""
    if isinstance(term, Application):
        for index, child in enumerate(term.children):
            yield from iter_innermost_positions(child, (*position, index))
    yield position


def term_depth(term: Term) -> int:
    """Return one for a leaf and one plus the deepest child for an application."""
    if not isinstance(term, Application) or not term.children:
        return 1
    return 1 + max(term_depth(child) for child in term.children)


def attempt_innermost_rewrite(
    term: Term,
    rules: list[Rule],
    *,
    cancelled: CancellationCheck | None = None,
) -> tuple[
    Term,
    bool,
    str | None,
    object | None,
    Bindings,
    TermPosition,
    RewriteKind,
]:
    """Apply the first rule at the first left-to-right innermost position."""
    for position in iter_innermost_positions(term):
        if cancelled is not None and cancelled():
            raise _EvaluationCancelled
        candidate = term_at_position(term, position)
        replacement, changed, rule, bindings = attempt_rewrite(candidate, rules)
        if changed and rule is not None:
            return (
                replace_at_position(term, position, replacement),
                True,
                rule.name,
                rule.id,
                bindings,
                position,
                RewriteKind.RULE,
            )
        replacement, changed, builtin_name = attempt_builtin_rewrite(candidate)
        if changed and builtin_name is not None:
            return (
                replace_at_position(term, position, replacement),
                True,
                builtin_name,
                None,
                {},
                position,
                RewriteKind.BUILTIN,
            )
    return term, False, None, None, {}, (), RewriteKind.RULE


def rewrite_step(term: Term, rules: list[Rule]) -> tuple[Term, bool]:
    result, changed, *_metadata = attempt_innermost_rewrite(term, rules)
    return result, changed


def evaluate(term: Term, rules: list[Rule]) -> Term:
    """Evaluate to normal form using deterministic innermost rewrites."""
    current = term
    while True:
        result, changed = rewrite_step(current, rules)
        if not changed:
            return current
        current = result


def evaluate_with_trace(
    term: Term,
    rules: list[Rule],
    *,
    max_steps: int = 100,
    max_depth: int = 1000,
    cancelled: CancellationCheck | None = None,
    source_line: int = 0,
) -> EvaluationResult:
    if max_steps <= 0:
        raise ValueError("max_steps must be a positive integer")
    if max_depth <= 0:
        raise ValueError("max_depth must be a positive integer")
    current = term
    events: list[RewriteEvent] = []
    if term_depth(current) > max_depth:
        return EvaluationResult(
            input_term=term,
            output_term=current,
            events=(),
            stop_reason=StopReason.DEPTH_LIMIT,
            source_line=source_line,
        )
    for index in range(1, max_steps + 1):
        try:
            (
                next_term,
                changed,
                rewrite_name,
                rewrite_id,
                bindings,
                position,
                kind,
            ) = attempt_innermost_rewrite(current, rules, cancelled=cancelled)
        except _EvaluationCancelled:
            return EvaluationResult(
                input_term=term,
                output_term=current,
                events=tuple(events),
                stop_reason=StopReason.CANCELLED,
                source_line=source_line,
            )
        except EngineError as error:
            return EvaluationResult(
                input_term=term,
                output_term=current,
                events=tuple(events),
                stop_reason=StopReason.RUNTIME_ERROR,
                error=error,
                source_line=source_line,
            )
        if not changed or rewrite_name is None:
            return EvaluationResult(
                input_term=term,
                output_term=current,
                events=tuple(events),
                stop_reason=StopReason.NORMAL_FORM,
                source_line=source_line,
            )
        if term_depth(next_term) > max_depth:
            return EvaluationResult(
                input_term=term,
                output_term=current,
                events=tuple(events),
                stop_reason=StopReason.DEPTH_LIMIT,
                source_line=source_line,
            )
        events.append(
            RewriteEvent(
                index=index,
                before=current,
                after=next_term,
                rule_name=rewrite_name,
                rule_id=rewrite_id,
                position=position,
                bindings=MappingProxyType(dict(bindings)),
                kind=kind,
            )
        )
        current = next_term
        if cancelled is not None and cancelled():
            return EvaluationResult(
                input_term=term,
                output_term=current,
                events=tuple(events),
                stop_reason=StopReason.CANCELLED,
                source_line=source_line,
            )
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
        label = "rule" if event.kind is RewriteKind.RULE else "builtin"
        fields = [f"{label}:{event.rule_name}"]
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
    if result.error is not None:
        lines.append(f"  error: {result.error.message}")
    return lines
