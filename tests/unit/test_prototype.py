from app import Const, Func, Rule, Var, evaluate, match, rewrite_step, substitute


def test_const_equality():
    assert Const(1) == Const(1)
    assert Const(1) != Const(2)
    assert Const("a") == Const("a")


def test_var_repr():
    assert repr(Var("x")) == "?x"


def test_func_repr():
    assert repr(Func("add", [Const(1), Const(2)])) == "add(1, 2)"


def test_match_variable_binds():
    env = match(Var("x"), Const(5))
    assert env == {"x": Const(5)}


def test_match_variable_repeat_requires_equality():
    env = match(Func("pair", [Var("x"), Var("x")]), Func("pair", [Const(1), Const(1)]))
    assert env == {"x": Const(1)}


def test_match_application_success():
    env = match(
        Func("add", [Var("a"), Const(0)]),
        Func("add", [Const(5), Const(0)]),
    )
    assert env == {"a": Const(5)}


def test_match_application_arity_mismatch():
    assert match(Func("add", [Var("a")]), Func("add", [Const(1), Const(2)])) is None


def test_match_application_name_mismatch():
    assert match(Func("add", [Var("a")]), Func("sub", [Var("a")])) is None


def test_match_literal_failure():
    assert match(Const(1), Const(2)) is None


def test_substitute_variable():
    env = {"x": Const(5)}
    assert substitute(Var("x"), env) == Const(5)


def test_substitute_unbound_retains_variable():
    assert substitute(Var("x"), {}) == Var("x")


def test_substitute_nested_function():
    env = {"a": Const(2)}
    term = Func("add", [Var("a"), Const(3)])
    assert substitute(term, env) == Func("add", [Const(2), Const(3)])


def test_rewrite_step_applies_first_matching_rule():
    term = Func("add", [Const(2), Const(3)])
    result, changed = rewrite_step(term, [])
    assert changed is False
    assert result == term


def test_evaluate_add_two_plus_three_reaches_five():
    rule1 = Rule(Func("add", [Var("a"), Const(0)]), Var("a"))
    rule2 = Rule(
        Func("add", [Var("a"), Var("b")]),
        Func("add", [Func("+", [Var("a"), Const(1)]), Func("-", [Var("b"), Const(1)])]),
    )
    result = evaluate(Func("add", [Const(2), Const(3)]), [rule1, rule2])
    assert result == Const(5)
