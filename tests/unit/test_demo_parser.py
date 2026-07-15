import pytest

from app import DemoSyntaxError, parse_rules


def test_parse_rules_generates_names_from_symbol_and_source_line():
    rules = parse_rules(
        """# comment
add(?x, 0) -> ?x
add(?x, ?y) -> add(inc(?x), dec(?y)) when ?y > 0
"""
    )

    assert [rule.name for rule in rules] == ["add-2", "add-3"]


def test_parse_rules_preserves_explicit_names():
    rules = parse_rules("add-zero: add(?x, 0) -> ?x")

    assert rules[0].name == "add-zero"


def test_parse_rules_rejects_duplicate_effective_names():
    with pytest.raises(DemoSyntaxError, match="duplicate rule name 'add-2'"):
        parse_rules(
            """add-2: add(?x, 0) -> ?x
add(?x, ?y) -> add(inc(?x), dec(?y))
"""
        )
