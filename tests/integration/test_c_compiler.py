import shutil

import pytest

from ruleset_notebook.compiler import CompilationError, generate_c
from ruleset_notebook.compiler.__main__ import main
from ruleset_notebook.compiler.verification import VerificationError, verify_c
from ruleset_notebook.domain import EvaluationSettings
from ruleset_notebook.examples import DEFAULT_EXAMPLE

requires_gcc = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not on PATH")


@requires_gcc
def test_cli_generates_and_verifies_the_addition_program(tmp_path, capsys):
    rules = tmp_path / "rules.txt"
    inputs = tmp_path / "inputs.txt"
    output = tmp_path / "addition.c"
    rules.write_text(DEFAULT_EXAMPLE.rules_text, encoding="utf-8")
    inputs.write_text(DEFAULT_EXAMPLE.inputs_text, encoding="utf-8")

    assert main([str(rules), str(inputs), "-o", str(output), "--verify"]) == 0
    source = output.read_text(encoding="ascii")
    assert "static RewriteStatus rule_1(" in source
    assert "static RewriteStatus rule_2(" in source
    assert "int main(void)" in source
    assert "Generated C trace matches Python." in capsys.readouterr().err


@requires_gcc
def test_generated_rules_match_patterns_guards_and_builtin_precedence():
    rules = """\
equal "??": pick(pair(x, x), y) => labelé(y)
ordered: pick(pair(x, y), z) => y when (x < y and y >= 2)
fallback: pick(pair(x, y), z) => z
override: inc(0) => 9
short-circuit: gate(x) => 99 when (0 == 1 and x > 0)
bad-guard: checked(x) => 0 when x > 0
"""
    inputs = """\
# The trace must preserve physical line numbers.
pick(pair(box(5), box(5)), -9223372036854775808)
pick(pair(1, 2), 3)
pick(pair(2, 1), 3)
box(inc(0), mul(-7, -8), dec(0))
gate(symbol)
checked(symbol)
inc(1, 2)
div(1, 0)
"""
    settings = EvaluationSettings()
    verify_c(generate_c(rules, inputs, settings), rules, inputs, settings)


@requires_gcc
def test_c_trace_matches_step_and_depth_limit_boundaries():
    rules = """\
loop: loop(x) => loop(x)
grow: grow(x) => grow(box(x))
once: once(x) => x
"""
    inputs = "loop(1)\ngrow(1)\nonce(1)\ngrow(box(box(1)))"
    settings = EvaluationSettings(max_steps=1, max_depth=2)
    verify_c(generate_c(rules, inputs, settings), rules, inputs, settings)


@requires_gcc
def test_verification_reports_the_c_runtime_overflow_difference():
    rules = "keep(x) => x"
    inputs = "mul(-9223372036854775808, -1)"
    settings = EvaluationSettings()

    with pytest.raises(VerificationError, match=r"\+ERROR integer-overflow"):
        verify_c(generate_c(rules, inputs, settings), rules, inputs, settings)


@pytest.mark.parametrize(
    ("rules", "inputs", "error"),
    [
        ("f(x) => true", "f(0)", "rules line 1: .*requires integer literals"),
        (
            "f(x) => x",
            "# comment\nf(1.5)",
            "inputs line 2: .*requires integer literals",
        ),
        ("f(x) => x", "f(9223372036854775808)", "inputs line 1: .*signed 64-bit range"),
    ],
)
def test_codegen_reports_unsupported_literals_with_source_lines(rules, inputs, error):
    with pytest.raises(CompilationError, match=error):
        generate_c(rules, inputs)
