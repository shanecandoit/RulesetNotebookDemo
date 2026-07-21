"""Small, executable examples shipped with Ruleset Notebook."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotebookExample:
    """A named rules-and-inputs draft that can be loaded in the GUI."""

    key: str
    title: str
    description: str
    rules_text: str
    inputs_text: str
    expected_outputs: tuple[str, ...]


EXAMPLES = (
    NotebookExample(
        key="addition",
        title="Addition by counting",
        description="Recursion, guards, ordered rules, and multiple inputs.",
        rules_text="""\
# Move one unit from y to x until y reaches zero.
add(x, 0) => x
add(x, y) => add(inc(x), dec(y)) when y > 0
""",
        inputs_text="""\
add(2, 3)
add(10, 4)
""",
        expected_outputs=("5", "14"),
    ),
    NotebookExample(
        key="larger",
        title="Choose the larger value",
        description="A guarded rule followed by an ordered fallback rule.",
        rules_text="""\
# The first matching rule wins, so the unguarded rule is the fallback.
larger-left: larger(x, y) => x when x >= y
larger-right: larger(x, y) => y
""",
        inputs_text="""\
larger(9, 4)
larger(2, 7)
larger(-1, -1)
""",
        expected_outputs=("9", "7", "-1"),
    ),
    NotebookExample(
        key="records",
        title="Unpack simple records",
        description="Structural patterns bind and extract parts of nested data.",
        rules_text="""\
unbox: unbox(box(x)) => x
first: first(pair(x, y)) => x
second: second(pair(x, y)) => y
""",
        inputs_text="""\
unbox(box(42))
first(pair("Ada", "Lovelace"))
second(pair(10, 20))
""",
        expected_outputs=("42", "'Ada'", "20"),
    ),
    NotebookExample(
        key="booleans",
        title="Boolean logic and De Morgan's laws",
        description="Truth tables for not/and/or plus symbolic De Morgan rewrites.",
        rules_text="""\
# Negation.
not-true: not(true) => false
not-false: not(false) => true

# Conjunction truth table.
and-true-true: and(true, true) => true
and-true-false: and(true, false) => false
and-false-true: and(false, true) => false
and-false-false: and(false, false) => false

# Disjunction truth table.
or-true-true: or(true, true) => true
or-true-false: or(true, false) => true
or-false-true: or(false, true) => true
or-false-false: or(false, false) => false

# De Morgan's laws are most visible with unresolved symbolic inputs.
de-morgan-and: not(and(x, y)) => or(not(x), not(y))
de-morgan-or: not(or(x, y)) => and(not(x), not(y))
""",
        inputs_text="""\
not(true)
and(true, false)
or(false, true)
not(and(left, right))
not(or(left, right))
not(and(true, false))
""",
        expected_outputs=(
            "False",
            "False",
            "True",
            "or(not(left()), not(right()))",
            "and(not(left()), not(right()))",
            "True",
        ),
    ),
)

DEFAULT_EXAMPLE = EXAMPLES[0]


def example_by_key(key: str) -> NotebookExample:
    """Return a shipped example by its stable key."""

    for example in EXAMPLES:
        if example.key == key:
            return example
    raise KeyError(key)
