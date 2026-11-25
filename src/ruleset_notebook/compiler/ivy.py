"""Command-line producer for standalone Ivy programs."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from ..domain import EvaluationSettings
from ..language import parse_inputs, parse_rules
from .ivy_codegen import generate_vine
from .verification import (
    VerificationError,
    compare_traces,
    evaluate_inputs,
    format_reference_trace,
    run_tool,
)


def _find_tool(executable: str, flag: str) -> str:
    path = shutil.which(executable)
    if path is None:
        raise VerificationError(f"cannot find {executable!r}; set {flag} to its path")
    return path


def main(argv: list[str] | None = None) -> int:
    defaults = EvaluationSettings()
    parser = argparse.ArgumentParser(
        prog="python -m ruleset_notebook.compiler.ivy",
        description="Generate an Ivy program from notebook rules and inputs.",
    )
    parser.add_argument("rules", type=Path, help="UTF-8 notebook rules file")
    parser.add_argument("inputs", type=Path, help="UTF-8 notebook inputs file")
    parser.add_argument("-o", "--output", type=Path, help="Ivy file (default: stdout)")
    parser.add_argument("--vine", default="vine", help="path to the Vine compiler")
    parser.add_argument(
        "--ivm", default="ivm", help="path to the standalone IVM runner"
    )
    parser.add_argument("--max-steps", type=int, default=defaults.max_steps)
    parser.add_argument("--max-depth", type=int, default=defaults.max_depth)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="run Ivy and compare its trace with Python",
    )
    args = parser.parse_args(argv)

    try:
        settings = EvaluationSettings(args.max_steps, args.max_depth)
        if args.output is not None and args.output.resolve() in {
            args.rules.resolve(),
            args.inputs.resolve(),
        }:
            raise ValueError("output must differ from the rules and inputs files")
        rules = parse_rules(args.rules.read_text(encoding="utf-8"))
        inputs = parse_inputs(args.inputs.read_text(encoding="utf-8"))
        source = generate_vine(rules, inputs, settings)
        vine = _find_tool(args.vine, "--vine")
        ivm = _find_tool(args.ivm, "--ivm") if args.verify else None
        with TemporaryDirectory(prefix="ruleset-notebook-ivy-") as directory:
            vine_path = Path(directory) / "notebook.vi"
            ivy_path = vine_path.with_suffix(".ivy")
            vine_path.write_text(source, encoding="utf-8")
            run_tool(
                [vine, "build", str(vine_path), "--out", str(ivy_path)],
                stage="Vine build",
                timeout=60,
            )
            ivy_source = ivy_path.read_text(encoding="utf-8")
            if args.output is None:
                sys.stdout.write(ivy_source)
            else:
                args.output.write_text(ivy_source, encoding="utf-8")
            if ivm is not None:
                native = run_tool(
                    [ivm, "run", str(ivy_path), "--no-stats"],
                    stage="IVM",
                    timeout=30,
                )
                expected = format_reference_trace(
                    evaluate_inputs(rules, inputs, settings)
                )
                compare_traces(expected, native, backend="Ivy")
                print("Generated Ivy trace matches Python.", file=sys.stderr)
    except (OSError, ValueError, RecursionError, VerificationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
