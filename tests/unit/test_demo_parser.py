import pytest

from ruleset_notebook.language import LanguageSyntaxError, parse_inputs, parse_rules


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("value", "value()"),
        ("pair(left, tree(a, b))", "pair(left(), tree(a(), b()))"),
        ("-3", "-3"),
        ("add(2, -3)", "add(2, -3)"),
    ],
)
def test_parse_inputs_accepts_supported_terms(source, expected):
    [(line, term)] = parse_inputs(source)

    assert line == 1
    assert repr(term) == expected


@pytest.mark.parametrize(
    "source",
    ["add(2 3)", "add(2, 3", "add(2, 3))", "add(2, @)", ""],
)
def test_parse_inputs_rejects_invalid_terms(source):
    with pytest.raises(LanguageSyntaxError):
        parse_inputs(source)


def test_parse_rules_generates_names_from_symbol_and_source_line():
    rules = parse_rules(
        """# comment
add(x, 0) => x
add(x, y) => add(inc(x), dec(y)) when y > 0
"""
    )

    assert [rule.name for rule in rules] == ["add-2", "add-3"]


def test_parse_rules_preserves_explicit_names():
    rules = parse_rules("add-zero: add(x, 0) => x")

    assert rules[0].name == "add-zero"


def test_parse_rules_rejects_duplicate_effective_names():
    with pytest.raises(LanguageSyntaxError, match="duplicate rule name 'add-2'"):
        parse_rules(
            """add-2: add(x, 0) => x
add(x, y) => add(inc(x), dec(y))
"""
        )


def test_rule_context_treats_lowercase_leaves_as_variables():
    rule = parse_rules("add(x, Zero) => x")[0]

    assert repr(rule.lhs) == "add(x, Zero())"
    assert repr(rule.rhs) == "x"


def test_input_context_treats_lowercase_leaves_as_symbols():
    [(line, term)] = parse_inputs("value")

    assert line == 1
    assert repr(term) == "value()"
