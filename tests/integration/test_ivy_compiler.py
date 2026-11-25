import shutil

import pytest

from ruleset_notebook.compiler.ivy import main
from ruleset_notebook.compiler.ivy_codegen import IvyCompilationError, generate_vine
from ruleset_notebook.domain import EvaluationSettings
from ruleset_notebook.examples import example_by_key
from ruleset_notebook.language import parse_inputs, parse_rules

requires_ivy = pytest.mark.skipif(
    not (shutil.which("vine") and shutil.which("ivm")),
    reason="Vine and standalone IVM are required on PATH",
)


@requires_ivy
@pytest.mark.parametrize("key", ["larger", "addition", "factorial"])
def test_ivy_cli_verifies_a_shipped_example(key, tmp_path, capsys):
    example = example_by_key(key)
    rules = tmp_path / "rules.txt"
    inputs = tmp_path / "inputs.txt"
    output = tmp_path / "notebook.ivy"
    rules.write_text(example.rules_text, encoding="utf-8")
    inputs.write_text(example.inputs_text, encoding="utf-8")

    assert main([str(rules), str(inputs), "-o", str(output), "--verify"]) == 0
    assert output.read_text(encoding="utf-8").lstrip().startswith("iv:main {")
    assert "Generated Ivy trace matches Python." in capsys.readouterr().err


@requires_ivy
def test_ivy_verifies_limits_and_runtime_errors(tmp_path, capsys):
    rules = tmp_path / "rules.txt"
    inputs = tmp_path / "inputs.txt"
    rules.write_text(
        "loop: loop(x) => loop(x)\ngrow: grow(x) => grow(box(x))", encoding="utf-8"
    )
    inputs.write_text(
        "loop(1)\ngrow(1)\ngrow(box(box(1)))\ndiv(1, 0)\ninc(1, 2)",
        encoding="utf-8",
    )

    assert (
        main(
            [
                str(rules),
                str(inputs),
                "-o",
                str(tmp_path / "limits.ivy"),
                "--max-steps",
                "2",
                "--max-depth",
                "3",
                "--verify",
            ]
        )
        == 0
    )
    assert "Generated Ivy trace matches Python." in capsys.readouterr().err


@requires_ivy
def test_ivy_verifies_repeated_patterns_guards_and_integer_boundaries(tmp_path, capsys):
    rules = tmp_path / "rules.txt"
    inputs = tmp_path / "inputs.txt"
    rules.write_text(
        """\
equal {arm} "quoted": pick(pair(x, x)) => labelé(x)
fallback: pick(pair(x, y)) => y
guarded: check(x) => x when (x >= 0 and x <= 10)
inc-override: inc(0) => 42
""",
        encoding="utf-8",
    )
    inputs.write_text(
        """\
# Preserve physical source line numbers.
pick(pair(box(7), box(7)))
pick(pair(box(7), box(8)))
check(symbol)
check(10)
box(dec(inc(0)), inc(9223372036854775807))
dec(-9223372036854775808)
""",
        encoding="utf-8",
    )

    assert (
        main(
            [str(rules), str(inputs), "-o", str(tmp_path / "matching.ivy"), "--verify"]
        )
        == 0
    )
    assert "Generated Ivy trace matches Python." in capsys.readouterr().err


@pytest.mark.parametrize(
    ("rules", "inputs", "error"),
    [
        ("f(x) => true", "f(0)", "rules line 1: .*requires integer literals"),
        (
            "f(x) => x",
            "# comment\nf(1.5)",
            "inputs line 2: .*requires integer literals",
        ),
    ],
)
def test_ivy_reports_unsupported_literals_with_source_lines(rules, inputs, error):
    with pytest.raises(IvyCompilationError, match=error):
        generate_vine(parse_rules(rules), parse_inputs(inputs), EvaluationSettings())
