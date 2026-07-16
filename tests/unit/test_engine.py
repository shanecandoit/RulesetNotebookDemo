from ruleset_notebook.domain import Application, Literal, Rule, Var
from ruleset_notebook.engine import evaluate, match, rewrite_step, substitute


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


def test_substitute_variable():
    assert substitute(Var("x"), {"x": Literal(5)}) == Literal(5)


def test_substitute_unbound_retains_variable():
    assert substitute(Var("x"), {}) == Var("x")


def test_substitute_nested_application():
    term = Application("add", (Var("a"), Literal(3)))
    assert substitute(term, {"a": Literal(2)}) == Application(
        "add", (Literal(2), Literal(3))
    )


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
