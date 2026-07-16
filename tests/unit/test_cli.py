"""Smoke tests for the command-line front end."""

from ruleset_notebook.cli import main


def test_cli_no_args_prints_help(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Ruleset Notebook" in out or "usage" in out.lower()


def test_cli_parses_and_prints_term(capsys):
    assert main(["add(2, 3)"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == "add(2, 3)"


def test_cli_repr_flag(capsys):
    assert main(["--repr", "add(2, 3)"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == "add(2, 3)"


def test_cli_variable_term(capsys):
    assert main(["x"]) == 0
    assert capsys.readouterr().out.strip() == "x"


def test_cli_reports_parse_error(capsys):
    assert main(["add(2,"]) == 2
    assert "error" in capsys.readouterr().err


def test_cli_rejects_trailing_tokens(capsys):
    assert main(["add(1) extra"]) == 2
