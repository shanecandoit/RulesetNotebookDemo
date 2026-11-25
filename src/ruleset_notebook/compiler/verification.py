"""Compile and run generated C for comparison with the Python evaluator."""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

from ..domain import EvaluationResult, EvaluationSettings, Rule, Term
from ..engine import evaluate_with_trace
from ..language import format_term, parse_inputs, parse_rules


class VerificationError(RuntimeError):
    """The generated program failed to compile, run, or match Python."""


def evaluate_inputs(
    rules: list[Rule], inputs: list[tuple[int, Term]], settings: EvaluationSettings
) -> Iterator[EvaluationResult]:
    for source_line, term in inputs:
        yield evaluate_with_trace(
            term,
            rules,
            source_line=source_line,
            max_steps=settings.max_steps,
            max_depth=settings.max_depth,
        )


def format_reference_trace(results: Iterable[EvaluationResult]) -> str:
    lines = ["TRACE 1"]
    for index, result in enumerate(results, 1):
        original = format_term(result.input_term)
        lines.append(f"INPUT {index} LINE {result.source_line} TERM {original}")
        lines.append(f"STEP 0 {original}")
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


def compile_c(source_path: Path, directory: Path) -> Path:
    gcc = shutil.which("gcc")
    if gcc is None:
        raise VerificationError("gcc was not found on PATH")
    binary_path = directory / ("notebook.exe" if os.name == "nt" else "notebook")
    _run(
        [
            gcc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(source_path.resolve()),
            "-o",
            str(binary_path),
        ],
        stage="gcc",
        timeout=30,
    )
    return binary_path


def run_c(binary_path: Path) -> str:
    return _run([str(binary_path)], stage="C program", timeout=10)


def compare_traces(expected: str, native: str) -> None:
    if expected != native:
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            native.splitlines(keepends=True),
            fromfile="Python",
            tofile="C",
        )
        raise VerificationError("C trace differs from Python\n" + "".join(diff))


def verify_c(
    source: str, rules_text: str, inputs_text: str, settings: EvaluationSettings
) -> None:
    """Raise VerificationError if GCC or the native/Python comparison fails."""
    with TemporaryDirectory(prefix="ruleset-notebook-") as directory:
        source_path = Path(directory) / "notebook.c"
        source_path.write_text(source, encoding="ascii")
        native = run_c(compile_c(source_path, Path(directory)))

    results = evaluate_inputs(
        parse_rules(rules_text), parse_inputs(inputs_text), settings
    )
    compare_traces(format_reference_trace(results), native)
