from ruleset_notebook.cli import main as cli_main
from ruleset_notebook.domain import Literal, StopReason
from ruleset_notebook.engine import evaluate_with_trace
from ruleset_notebook.language import parse_inputs, parse_rules

RULES = """\
add(x, 0) => x
add(x, y) => add(inc(x), dec(y)) when y > 0
"""


def test_shared_parser_and_engine_evaluate_gui_example():
    rules = parse_rules(RULES)
    [(source_line, term)] = parse_inputs("add(2, 3)")

    result = evaluate_with_trace(term, rules, source_line=source_line)

    assert result.output_term == Literal(5)
    assert result.stop_reason is StopReason.NORMAL_FORM
    assert [event.rule_name for event in result.events] == [
        "add-2",
        "add-2",
        "add-2",
        "add-1",
    ]


def test_cli_uses_shared_term_parser(capsys):
    assert cli_main(["add(2, 3)"]) == 0
    assert capsys.readouterr().out.strip() == "add(2, 3)"
