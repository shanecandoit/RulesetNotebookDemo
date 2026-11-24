"""Command-line entry point for the standalone C producer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..domain import EvaluationSettings
from .codegen import generate_c
from .verification import VerificationError, verify_c


def main(argv: list[str] | None = None) -> int:
    defaults = EvaluationSettings()
    parser = argparse.ArgumentParser(
        prog="python -m ruleset_notebook.compiler",
        description="Generate a standalone C11 program from notebook rules and inputs.",
    )
    parser.add_argument("rules", type=Path, help="UTF-8 notebook rules file")
    parser.add_argument("inputs", type=Path, help="UTF-8 notebook inputs file")
    parser.add_argument(
        "-o", "--output", type=Path, help="C output file (default: stdout)"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=defaults.max_steps,
        help="rewrite limit per input",
    )
    parser.add_argument(
        "--max-depth", type=int, default=defaults.max_depth, help="term depth limit"
    )
    parser.add_argument(
        "--verify", action="store_true", help="compile with GCC and compare with Python"
    )
    args = parser.parse_args(argv)

    try:
        settings = EvaluationSettings(
            max_steps=args.max_steps, max_depth=args.max_depth
        )
        if args.output is not None:
            output = args.output.resolve()
            if output in {args.rules.resolve(), args.inputs.resolve()}:
                raise ValueError("output must differ from the rules and inputs files")
        rules_text = args.rules.read_text(encoding="utf-8")
        inputs_text = args.inputs.read_text(encoding="utf-8")
        source = generate_c(rules_text, inputs_text, settings)
        if args.output is None:
            sys.stdout.write(source)
        else:
            args.output.write_text(source, encoding="ascii")
        if args.verify:
            verify_c(source, rules_text, inputs_text, settings)
            print("Generated C trace matches Python.", file=sys.stderr)
    except (OSError, ValueError, RecursionError, VerificationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
