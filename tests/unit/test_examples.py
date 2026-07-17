import pytest

from ruleset_notebook.engine import evaluate_with_trace
from ruleset_notebook.examples import EXAMPLES, example_by_key
from ruleset_notebook.language import parse_inputs, parse_rules


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example.key)
def test_shipped_examples_parse_and_produce_documented_outputs(example):
    rules = parse_rules(example.rules_text)
    inputs = parse_inputs(example.inputs_text)

    outputs = tuple(
        str(evaluate_with_trace(term, rules, source_line=line).output_term)
        for line, term in inputs
    )

    assert outputs == example.expected_outputs


def test_example_keys_are_unique_and_lookup_is_stable():
    assert len({example.key for example in EXAMPLES}) == len(EXAMPLES)
    assert all(example_by_key(example.key) is example for example in EXAMPLES)


def test_unknown_example_key_is_rejected():
    with pytest.raises(KeyError):
        example_by_key("missing")
