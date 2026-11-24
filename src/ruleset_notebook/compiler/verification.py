"""Compile and run generated C for comparison with the Python evaluator."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ..domain import EvaluationSettings
from ..engine import evaluate_with_trace
from ..language import format_term, parse_inputs, parse_rules


class VerificationError(RuntimeError):
    """The generated program failed to compile, run, or match Python."""


def _reference_trace(
    rules_text: str, inputs_text: str, settings: EvaluationSettings
) -> str:
    rules = parse_rules(rules_text)
    lines = ["TRACE 1"]
    for index, (source_line, term) in enumerate(parse_inputs(inputs_text), 1):
        result = evaluate_with_trace(
            term,
            rules,
            source_line=source_line,
            max_steps=settings.max_steps,
            max_depth=settings.max_depth,
        )
        original = format_term(term)
        lines.extend(
            [f"INPUT {index} LINE {source_line} TERM {original}", f"STEP 0 {original}"]
        )
        for event in result.events:
            position = ".".join(str(part) for part in event.position) or "root"
            name = json.dumps(event.rule_name, ensure_ascii=True)
            lines.append(
                f"STEP {event.index} {format_term(event.after)} "
                f"KIND {event.kind.value} POSITION {position} NAME {name}"
            )
        lines.extend(
            [
                f"RESULT {format_term(result.output_term)}",
                f"STATUS {result.stop_reason.value}",
            ]
        )
        if result.error is not None:
            lines.append(f"ERROR {result.error.code}")
    return "\n".join(lines) + "\n"


def _run(command: list[str], *, stage: str, timeout: float) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise VerificationError(
            f"{stage} timed out after {timeout:g} seconds"
        ) from error
    if result.returncode:
        diagnostics = (result.stderr or result.stdout).strip()
        message = f"{stage} exited with code {result.returncode}"
        raise VerificationError(f"{message}\n{diagnostics}" if diagnostics else message)
    return result.stdout


def verify_c(
    source: str, rules_text: str, inputs_text: str, settings: EvaluationSettings
) -> None:
    """Raise VerificationError if GCC or the native/Python comparison fails."""
    gcc = shutil.which("gcc")
    if gcc is None:
        raise VerificationError("gcc was not found on PATH")

    with TemporaryDirectory(prefix="ruleset-notebook-") as directory:
        source_path = Path(directory) / "notebook.c"
        binary_path = source_path.with_suffix(".exe" if os.name == "nt" else "")
        source_path.write_text(source, encoding="ascii")
        _run(
            [
                gcc,
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(source_path),
                "-o",
                str(binary_path),
            ],
            stage="gcc",
            timeout=30,
        )
        native = _run([str(binary_path)], stage="generated program", timeout=10)

    expected = _reference_trace(rules_text, inputs_text, settings)
    if expected != native:
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            native.splitlines(keepends=True),
            fromfile="Python",
            tofile="C",
        )
        raise VerificationError("generated trace differs from Python\n" + "".join(diff))
