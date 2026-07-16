"""Tests for immutable term variants and structural equality/hashing."""

from ruleset_notebook.domain import Application, Literal, Term, Var


def test_var_repr():
    assert repr(Var("x")) == "x"


def test_literal_repr():
    assert repr(Literal(5)) == "5"
    assert repr(Literal("a")) == "'a'"


def test_application_repr():
    term = Application("add", (Literal(1), Literal(2)))
    assert repr(term) == "add(1, 2)"


def test_var_equality_and_hash():
    assert Var("x") == Var("x")
    assert Var("x") != Var("y")
    assert hash(Var("x")) == hash(Var("x"))


def test_literal_equality_and_hash():
    assert Literal(1) == Literal(1)
    assert Literal(1) != Literal(2)
    assert Literal("a") == Literal("a")
    assert hash(Literal(1)) == hash(Literal(1))


def test_application_equality_and_hash():
    left = Application("add", (Literal(1), Literal(2)))
    same = Application("add", (Literal(1), Literal(2)))
    different = Application("sub", (Literal(1), Literal(2)))
    assert left == same
    assert left != different
    assert hash(left) == hash(same)


def test_application_children_are_tuples():
    term = Application("add", (Literal(1), Literal(2)))
    assert isinstance(term.children, tuple)
    assert len(term.children) == 2


def test_terms_are_immutable():
    term = Application("add", (Literal(1),))
    try:
        term.symbol = "sub"  # type: ignore[misc]
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("Application was unexpectedly mutable")


def test_nested_structural_equality():
    nested = Application(
        "pair",
        (Application("add", (Literal(1), Literal(2))), Var("x")),
    )
    same = Application(
        "pair",
        (Application("add", (Literal(1), Literal(2))), Var("x")),
    )
    assert nested == same
    assert hash(nested) == hash(same)


def test_different_shapes_are_not_equal():
    pairs: list[tuple[Term, Term]] = [
        (Var("x"), Literal("x")),
        (Literal(1), Application("f", ())),
        (Var("x"), Application("x", ())),
    ]
    for left, right in pairs:
        assert left != right
