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

from .domain import Application, Literal, Term, Var


def _parse_term(source: str) -> Term:
    """A minimal recursive-descent term parser for ad-hoc CLI use.

    Supports lowercase variables, integers, and parenthesized applications. A
    lowercase leaf is a variable; a name followed by ``(`` is an application.
    The production lexer/parser (todo.md section 2) replaces this.
    """
    import re

    tokenizer = re.compile(r"\s*([\w]+|-?\d+|\(|\)|,)", re.ASCII)
    tokens: list[str] = []
    position = 0
    while position < len(source):
        match = tokenizer.match(source, position)
        if match is None:
            raise ValueError(
                f"unexpected text at column {position + 1}: "
                f"{source[position : position + 12]!r}"
            )
        tokens.append(match.group(1))
        position = match.end()
    if not tokens:
        raise ValueError("expected a term")

    index = 0

    def peek() -> str | None:
        return tokens[index] if index < len(tokens) else None

    def take() -> str:
        nonlocal index
        token = peek()
        if token is None:
            raise ValueError("unexpected end of input")
        index += 1
        return token

    def parse() -> Term:
        token = take()
        if re.fullmatch(r"-?\d+", token):
            return Literal(int(token))
        if not re.fullmatch(r"[\w]+", token):
            raise ValueError(f"expected a term, found {token!r}")
        if peek() != "(":
            if token[0].islower():
                return Var(token)
            return Application(token, ())
        take()
        children: list[Term] = []
        if peek() != ")":
            while True:
                children.append(parse())
                if peek() != ",":
                    break
                take()
        if peek() != ")":
            raise ValueError("missing closing parenthesis")
        take()
        return Application(token, tuple(children))

    term = parse()
    if index != len(tokens):
        raise ValueError(f"unexpected token {tokens[index]!r}")
    return term


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
        term = _parse_term(args.term)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(term if not args.show_repr else repr(term))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
