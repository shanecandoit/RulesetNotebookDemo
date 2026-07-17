import inspect

import pytest

from ruleset_notebook.domain import (
    Application,
    GuardEvaluationError,
    Literal,
    Rule,
    UnboundVariableError,
    Var,
)
from ruleset_notebook.engine import (
    evaluate,
    evaluate_guard,
    match,
    rewrite_step,
    substitute,
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
    term = Application("add", (Literal(2), Literal(3)))
    result, changed = rewrite_step(term, [])
    assert changed is False
    assert result == term


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
