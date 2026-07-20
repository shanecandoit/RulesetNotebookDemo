import inspect

import pytest

from ruleset_notebook.domain import (
    Application,
    DivisionByZeroError,
    GuardEvaluationError,
    InvalidOperandError,
    Literal,
    RewriteKind,
    Rule,
    StopReason,
    UnboundVariableError,
    Var,
)
from ruleset_notebook.engine import (
    evaluate,
    evaluate_guard,
    evaluate_with_trace,
    format_trace_lines,
    iter_innermost_positions,
    match,
    replace_at_position,
    rewrite_step,
    substitute,
    term_at_position,
    term_depth,
)
from ruleset_notebook.language import parse_rules


def test_literal_equality():
    assert Literal(1) == Literal(1)
    assert Literal(1) != Literal(2)
    assert Literal("a") == Literal("a")


def test_var_repr():
    assert repr(Var("x")) == "x"


def test_application_repr():
    term = Application("add", (Literal(1), Literal(2)))
    assert repr(term) == "add(1, 2)"


def test_match_variable_binds():
    env = match(Var("x"), Literal(5))
    assert env == {"x": Literal(5)}


def test_match_variable_repeat_requires_equality():
    pattern = Application("pair", (Var("x"), Var("x")))
    subject = Application("pair", (Literal(1), Literal(1)))
    assert match(pattern, subject) == {"x": Literal(1)}
    assert match(pattern, Application("pair", (Literal(1), Literal(2)))) is None


def test_match_application_success():
    env = match(
        Application("add", (Var("a"), Literal(0))),
        Application("add", (Literal(5), Literal(0))),
    )
    assert env == {"a": Literal(5)}


def test_match_application_arity_mismatch():
    pattern = Application("add", (Var("a"),))
    subject = Application("add", (Literal(1), Literal(2)))
    assert match(pattern, subject) is None


def test_match_application_name_mismatch():
    pattern = Application("add", (Var("a"),))
    subject = Application("sub", (Var("a"),))
    assert match(pattern, subject) is None


def test_match_literal_failure():
    assert match(Literal(1), Literal(2)) is None


def test_match_bool_and_int_are_distinct_literals():
    assert match(Literal(True), Literal(1)) is None
    assert match(Literal(False), Literal(0)) is None


def test_match_failure_does_not_leak_partial_bindings():
    environment = {"existing": Literal(9)}
    pattern = Application("pair", (Var("x"), Literal(2)))
    subject = Application("pair", (Literal(1), Literal(3)))

    assert match(pattern, subject, environment) is None
    assert environment == {"existing": Literal(9)}


def test_substitute_variable():
    assert substitute(Var("x"), {"x": Literal(5)}) == Literal(5)


def test_substitute_unbound_raises_defensive_error():
    with pytest.raises(UnboundVariableError, match="unbound variable 'x'"):
        substitute(Var("x"), {})


def test_substitute_nested_application():
    term = Application("add", (Var("a"), Literal(3)))
    assert substitute(term, {"a": Literal(2)}) == Application(
        "add", (Literal(2), Literal(3))
    )


def test_substitute_does_not_mutate_template_or_bindings():
    term = Application("pair", (Var("x"), Application("box", (Var("x"),))))
    bindings = {"x": Literal(7)}

    result = substitute(term, bindings)

    assert result == Application(
        "pair", (Literal(7), Application("box", (Literal(7),)))
    )
    assert term == Application("pair", (Var("x"), Application("box", (Var("x"),))))
    assert bindings == {"x": Literal(7)}


def test_rewrite_step_with_no_rules_does_not_change_term():
    term = Application("unknown", (Literal(2), Literal(3)))
    result, changed = rewrite_step(term, [])
    assert changed is False
    assert result == term


@pytest.mark.parametrize(
    ("symbol", "children", "expected"),
    [
        ("inc", (Literal(2),), Literal(3)),
        ("dec", (Literal(2),), Literal(1)),
        ("add", (Literal(2), Literal(3)), Literal(5)),
        ("sub", (Literal(2), Literal(3)), Literal(-1)),
        ("mul", (Literal(2), Literal(3)), Literal(6)),
        ("div", (Literal(5), Literal(2)), Literal(2.5)),
    ],
)
def test_documented_numeric_builtins_are_traced(symbol, children, expected):
    result = evaluate_with_trace(Application(symbol, children), [])

    assert result.output_term == expected
    assert result.stop_reason is StopReason.NORMAL_FORM
    assert result.step_count() == 1
    assert result.events[0].kind is RewriteKind.BUILTIN
    assert result.events[0].rule_name == symbol
    assert f"builtin:{symbol}" in format_trace_lines(result)[1]


def test_user_rule_has_priority_over_builtin_at_same_position():
    user_inc = Rule(
        "user-inc",
        Application("inc", (Var("x"),)),
        Application("wrapped", (Var("x"),)),
    )

    result = evaluate_with_trace(Application("inc", (Literal(2),)), [user_inc])

    assert result.output_term == Application("wrapped", (Literal(2),))
    assert result.events[0].kind is RewriteKind.RULE
    assert result.events[0].rule_name == "user-inc"


@pytest.mark.parametrize(
    "term",
    [
        Application("inc", (Literal("two"),)),
        Application("add", (Literal(True), Literal(1))),
        Application("mul", (Application("box", ()), Literal(2))),
        Application("inc", (Literal(1), Literal(2))),
    ],
)
def test_invalid_builtin_operands_return_typed_runtime_error(term):
    result = evaluate_with_trace(term, [])

    assert result.output_term == term
    assert result.stop_reason is StopReason.RUNTIME_ERROR
    assert isinstance(result.error, InvalidOperandError)
    assert "error:" in format_trace_lines(result)[-1]


def test_division_by_zero_returns_typed_runtime_error():
    term = Application("div", (Literal(1), Literal(0)))

    result = evaluate_with_trace(term, [])

    assert result.stop_reason is StopReason.RUNTIME_ERROR
    assert isinstance(result.error, DivisionByZeroError)


def test_step_limit_returns_exact_event_count_and_partial_term():
    loop = Rule(
        "loop", Application("loop", (Var("x"),)), Application("loop", (Var("x"),))
    )

    result = evaluate_with_trace(
        Application("loop", (Literal(1),)), [loop], max_steps=3
    )

    assert result.stop_reason is StopReason.STEP_LIMIT
    assert result.step_count() == 3
    assert result.output_term == Application("loop", (Literal(1),))


def test_depth_limit_rejects_replacement_before_it_is_recorded():
    grow = Rule(
        "grow",
        Application("grow", (Var("x"),)),
        Application("box", (Application("grow", (Var("x"),)),)),
    )

    result = evaluate_with_trace(
        Application("grow", (Literal(1),)), [grow], max_depth=3
    )

    assert result.stop_reason is StopReason.DEPTH_LIMIT
    assert result.step_count() == 1
    assert term_depth(result.output_term) == 3


def test_cancellation_is_checked_during_traversal_and_after_a_step():
    calls = 0

    def cancelled() -> bool:
        nonlocal calls
        calls += 1
        return calls == 3

    unwrap = Rule("unwrap", Application("box", (Var("x"),)), Var("x"))
    result = evaluate_with_trace(
        Application("box", (Literal(1),)), [unwrap], cancelled=cancelled
    )

    assert result.stop_reason is StopReason.CANCELLED
    assert result.step_count() == 1
    assert result.output_term == Literal(1)


def test_trace_bindings_are_immutable_snapshots():
    unwrap = Rule("unwrap", Application("box", (Var("x"),)), Var("x"))
    result = evaluate_with_trace(Application("box", (Literal(1),)), [unwrap])

    with pytest.raises(TypeError):
        result.events[0].bindings["x"] = Literal(2)  # type: ignore[index]


def test_term_positions_read_replace_and_enumerate_without_mutation():
    term = Application(
        "outer",
        (
            Application("left", (Literal(1),)),
            Application("right", (Literal(2), Literal(3))),
        ),
    )

    assert term_at_position(term, (1, 0)) == Literal(2)
    assert list(iter_innermost_positions(term)) == [
        (0, 0),
        (0,),
        (1, 0),
        (1, 1),
        (1,),
        (),
    ]
    assert replace_at_position(term, (1, 0), Literal(9)) == Application(
        "outer",
        (
            Application("left", (Literal(1),)),
            Application("right", (Literal(9), Literal(3))),
        ),
    )
    assert term_at_position(term, (1, 0)) == Literal(2)


def test_evaluate_with_trace_rewrites_left_to_right_innermost_then_root():
    mark = Rule("mark", Application("mark", (Var("x"),)), Var("x"))
    collapse = Rule(
        "collapse",
        Application("pair", (Var("x"), Var("y"))),
        Application("done", (Var("x"), Var("y"))),
    )
    term = Application(
        "pair",
        (
            Application("mark", (Literal(1),)),
            Application("mark", (Literal(2),)),
        ),
    )

    result = evaluate_with_trace(term, [mark, collapse])

    assert result.output_term == Application("done", (Literal(1), Literal(2)))
    assert [event.rule_name for event in result.events] == [
        "mark",
        "mark",
        "collapse",
    ]
    assert [event.position for event in result.events] == [(0,), (1,), ()]
    assert "position:0" in format_trace_lines(result)[1]
    assert "position:1" in format_trace_lines(result)[2]
    assert "position:root" in format_trace_lines(result)[3]


def test_innermost_rewrite_uses_source_order_at_candidate_position():
    term = Application("box", (Application("mark", (Literal(1),)),))
    first_then_second = parse_rules(
        "first: mark(x) => chosen(x)\nsecond: mark(x) => other(x)"
    )
    second_then_first = parse_rules(
        "second: mark(x) => other(x)\nfirst: mark(x) => chosen(x)"
    )

    first_result = evaluate_with_trace(term, first_then_second)
    second_result = evaluate_with_trace(term, second_then_first)

    assert first_result.output_term == Application(
        "box", (Application("chosen", (Literal(1),)),)
    )
    assert second_result.output_term == Application(
        "box", (Application("other", (Literal(1),)),)
    )
    assert [event.rule_name for event in first_result.events] == ["first"]
    assert [event.rule_name for event in second_result.events] == ["second"]
    assert first_result.events[0].position == (0,)


def test_innermost_rewrite_skips_disabled_rules():
    disabled = Rule(
        "disabled",
        Application("mark", (Var("x"),)),
        Application("wrong", (Var("x"),)),
        enabled=False,
    )
    enabled = Rule(
        "enabled",
        Application("mark", (Var("x"),)),
        Application("right", (Var("x"),)),
    )

    result = evaluate_with_trace(
        Application("box", (Application("mark", (Literal(1),)),)),
        [disabled, enabled],
    )

    assert result.output_term == Application(
        "box", (Application("right", (Literal(1),)),)
    )
    assert [event.rule_name for event in result.events] == ["enabled"]


def test_evaluate_add_two_plus_three_reaches_five():
    zero = Rule(
        "add-zero",
        Application("add", (Var("a"), Literal(0))),
        Var("a"),
    )
    step = Rule(
        "add-step",
        Application("add", (Var("a"), Var("b"))),
        Application(
            "add",
            (
                Application("+", (Var("a"), Literal(1))),
                Application("-", (Var("b"), Literal(1))),
            ),
        ),
    )
    term = Application("add", (Literal(2), Literal(3)))
    assert evaluate(term, [zero, step]) == Literal(5)


def test_guard_true_false_and_grouped_conjunction():
    true_rule = parse_rules("pair(x, y) => x when y > 0 and (x < 10)")[0]
    false_rule = parse_rules("pair(x, y) => x when y > 0 and (x < 10)")[0]

    assert evaluate_guard(true_rule.guard, {"x": Literal(2), "y": Literal(3)})
    assert not evaluate_guard(false_rule.guard, {"x": Literal(12), "y": Literal(3)})


def test_guard_missing_binding_and_type_error_are_typed():
    rule = parse_rules("pair(x, y) => x when y > 0")[0]

    with pytest.raises(GuardEvaluationError, match="no match binding"):
        evaluate_guard(rule.guard, {"x": Literal(2)})
    with pytest.raises(GuardEvaluationError, match="incompatible types"):
        evaluate_guard(rule.guard, {"x": Literal(2), "y": Literal("three")})


def test_guard_implementation_does_not_use_eval_or_exec():
    source = inspect.getsource(evaluate_guard)

    assert "eval(" not in source
    assert "exec(" not in source
