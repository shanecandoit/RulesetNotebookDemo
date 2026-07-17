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
        title="Boolean decisions",
        description="Literal matching can select one of two values.",
        rules_text="""\
choose-true: choose(true, x, y) => x
choose-false: choose(false, x, y) => y
""",
        inputs_text="""\
choose(true, "keep", "discard")
choose(false, 1, 2)
""",
        expected_outputs=("'keep'", "2"),
    ),
)

DEFAULT_EXAMPLE = EXAMPLES[0]


def example_by_key(key: str) -> NotebookExample:
    """Return a shipped example by its stable key."""

    for example in EXAMPLES:
        if example.key == key:
            return example
    raise KeyError(key)
