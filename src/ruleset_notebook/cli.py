"""Command-line front end for the Ruleset Notebook term rewriter.

This is intentionally thin and stands on top of the UI-independent ``domain``
package so the rewriter can be exercised from the shell before the larger
language/engine layers land. It currently accepts a single term and prints its
canonical structure; richer rule evaluation is added as the engine (todo.md
sections 5-6) is implemented.
"""

from __future__ import annotations

import argparse
import sys

from .language import LanguageSyntaxError, parse_term


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ruleset-notebook",
        description="Inspect term-rewriting terms and rules from the command line.",
    )
    parser.add_argument(
        "term",
        nargs="?",
        help="A term to parse and display, e.g. 'add(2, 3)'.",
    )
    parser.add_argument(
        "--repr",
        dest="show_repr",
        action="store_true",
        help="Print the developer repr of the parsed term.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.term:
        parser.print_help()
        return 0

    try:
        term = parse_term(args.term, lowercase_variables=True)
    except LanguageSyntaxError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(term if not args.show_repr else repr(term))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
