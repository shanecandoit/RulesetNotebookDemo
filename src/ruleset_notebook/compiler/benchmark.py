"""Measure the Python and C backends and check their trace parity."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import TypeVar
from unittest.mock import patch

from .. import engine
from ..domain import EvaluationSettings, Rule, Term
from ..examples import example_by_key
from ..language import parse_inputs, parse_rules
from .codegen import generate_c
from .verification import (
    VerificationError,
    compare_traces,
    compile_c,
    evaluate_inputs,
    format_reference_trace,
    run_c,
)

T = TypeVar("T")


@dataclass(frozen=True)
class Workload:
    name: str
    rules_text: str
    inputs_text: str


def _wide_workload(width: int, *, distinct: bool) -> Workload:
    rules = "done: count(0) => 0\nnext: count(n) => count(dec(n)) when n > 0"
    shape = "distinct" if distinct else "repeated"
    items = ", ".join(f"box({index if distinct else 0})" for index in range(width))
    return Workload(f"{width} {shape}", rules, f"wrap(data({items}), count(48))")


def _built_in_workloads(suite: str) -> Iterator[Workload]:
    if suite == "baseline":
        for width, distinct in [(0, False), (128, False), (512, False), (512, True)]:
            yield _wide_workload(width, distinct=distinct)
    if suite in {"stress", "wide"}:
        for width in (1024, 2048):
            yield _wide_workload(width, distinct=True)
    if suite in {"stress", "deep"}:
        for depth in (128, 256):
            wrappers = depth - 2  # The leaf application and its literal add two levels.
            term = "box(" * wrappers + "leaf(41)" + ")" * wrappers
            yield Workload(f"depth {depth}", "finish: leaf(n) => inc(n)", term)
    if suite in {"stress", "batch"}:
        rules = example_by_key("factorial").rules_text
        for size in (64, 512):
            inputs = "\n".join(f"factorial({index % 21})" for index in range(size))
            yield Workload(f"batch {size}", rules, inputs)


def _measure(
    action: Callable[[], T], runs: int, *, check: Callable[[T], None] | None = None
) -> tuple[T, float]:
    durations = []
    for _ in range(runs + 1):
        start = perf_counter()
        result = action()
        durations.append(perf_counter() - start)
        if check is not None:
            check(result)
    return result, 1000 * median(durations[1:])  # Exclude the warm-up.


def _count_positions(
    rules: list[Rule], inputs: list[tuple[int, Term]], settings: EvaluationSettings
) -> int:
    count = 0
    attempt_rewrite = engine.attempt_rewrite

    def counted(
        term: Term, ordered_rules: list[Rule]
    ) -> tuple[Term, bool, Rule | None, engine.Bindings]:
        nonlocal count
        count += 1
        return attempt_rewrite(term, ordered_rules)

    # Count in a separate pass so instrumentation stays out of the timings.
    with patch.object(engine, "attempt_rewrite", counted):
        for _ in evaluate_inputs(rules, inputs, settings):
            pass
    return count


def _report(
    workload: Workload,
    settings: EvaluationSettings,
    runs: int,
    c_source: Path | None,
) -> None:
    rules = parse_rules(workload.rules_text)
    inputs = parse_inputs(workload.inputs_text)

    with TemporaryDirectory(prefix="ruleset-benchmark-") as temporary:
        directory = Path(temporary)
        if c_source is None:
            c_source = directory / "notebook.c"
            c_source.write_text(
                generate_c(workload.rules_text, workload.inputs_text, settings),
                encoding="ascii",
            )
        start = perf_counter()
        binary = compile_c(c_source, directory)
        compile_ms = 1000 * (perf_counter() - start)

        results, python_ms = _measure(
            lambda: list(evaluate_inputs(rules, inputs, settings)), runs
        )
        _, format_ms = _measure(
            lambda: [engine.format_trace_lines(result) for result in results], runs
        )
        expected = format_reference_trace(results)
        c_trace, c_ms = _measure(
            lambda: run_c(binary),
            runs,
            check=lambda trace: compare_traces(expected, trace),
        )

    positions = _count_positions(rules, inputs, settings)
    rewrites = sum(result.step_count() for result in results)
    trace_kib = len(c_trace.encode("utf-8")) / 1024
    stops = Counter(result.stop_reason.value for result in results)
    stop_summary = ", ".join(f"{count} {reason}" for reason, count in stops.items())
    print(
        f"{workload.name:<14} {len(inputs):>6} {rewrites:>8} {positions:>10} "
        f"{python_ms:>10.2f} {format_ms:>10.2f} {compile_ms:>9.2f} "
        f"{c_ms:>10.2f} {trace_kib:>9.1f}  {stop_summary}",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    defaults = EvaluationSettings()
    parser = argparse.ArgumentParser(
        description="Benchmark and verify notebook rules in Python and C.",
        epilog="Omit both files to run a built-in suite.",
    )
    parser.add_argument("rules", type=Path, nargs="?", help="UTF-8 notebook rules")
    parser.add_argument("inputs", type=Path, nargs="?", help="UTF-8 notebook inputs")
    parser.add_argument(
        "--suite",
        choices=("baseline", "wide", "deep", "batch", "stress"),
        help="workload suite (default: baseline, stress runs wide, deep, and batch)",
    )
    parser.add_argument("--runs", type=int, default=7, help="timed runs (default: 7)")
    parser.add_argument("--max-steps", type=int, default=defaults.max_steps)
    parser.add_argument("--max-depth", type=int, default=defaults.max_depth)
    parser.add_argument("--c-source", type=Path, help="alternate C source to verify")
    args = parser.parse_args(argv)
    if (args.rules is None) != (args.inputs is None):
        parser.error("provide both a rules file and an inputs file")
    if args.suite is not None and args.rules is not None:
        parser.error("--suite cannot be used with rules and inputs files")
    if args.c_source is not None and args.rules is None:
        parser.error("--c-source requires rules and inputs files")
    if args.runs < 1:
        parser.error("--runs must be a positive integer")

    try:
        settings = EvaluationSettings(args.max_steps, args.max_depth)
        workloads: Iterable[Workload]
        if args.rules is None:
            workloads = _built_in_workloads(args.suite or "baseline")
        else:
            workloads = (
                Workload(
                    "custom",
                    args.rules.read_text(encoding="utf-8"),
                    args.inputs.read_text(encoding="utf-8"),
                ),
            )
        print(
            f"Median of {args.runs} timed runs after one warm-up per case.", flush=True
        )
        print(
            f"{'Case':<14} {'Inputs':>6} {'Rewrites':>8} {'Positions':>10} "
            f"{'Python ms':>10} {'Format ms':>10} {'GCC ms':>9} "
            f"{'C run ms':>10} {'Trace KiB':>9}  Stops",
            flush=True,
        )
        for workload in workloads:
            _report(workload, settings, args.runs, args.c_source)
    except (OSError, ValueError, RecursionError, VerificationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print("C and Python traces match for every workload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
