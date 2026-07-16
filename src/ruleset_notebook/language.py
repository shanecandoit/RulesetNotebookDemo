"""Shared plain-text parser for the GUI and command-line interfaces."""

from __future__ import annotations

import re

from .domain import Application, ComparisonGuard, Literal, Rule, Term, Var


class LanguageSyntaxError(ValueError):
    """A line-oriented syntax error suitable for user-facing diagnostics."""


TOKEN_RE = re.compile(r"\s*(?:(-?\d+)|([A-Za-z_]\w*)|([(),]))")
GUARD_RE = re.compile(r"^([a-z][A-Za-z0-9_]*)\s*(==|!=|<=|>=|<|>)\s*(-?\d+)$")


class TermParser:
    """Parse one term, with contextual lowercase-variable handling."""

    def __init__(self, source: str, *, lowercase_variables: bool = False):
        self.source = source
        self.lowercase_variables = lowercase_variables
        self.tokens: list[str] = []
        position = 0
        while position < len(source):
            token_match = TOKEN_RE.match(source, position)
            if token_match is None:
                raise LanguageSyntaxError(
                    f"unexpected text at column {position + 1}: "
                    f"{source[position : position + 12]!r}"
                )
            self.tokens.append(next(part for part in token_match.groups() if part))
            position = token_match.end()
        self.index = 0

    def parse(self) -> Term:
        if not self.tokens:
            raise LanguageSyntaxError("expected a term")
        term = self._parse_term()
        if self.index != len(self.tokens):
            raise LanguageSyntaxError(f"unexpected token {self.tokens[self.index]!r}")
        return term

    def _parse_term(self) -> Term:
        token = self._take()
        if re.fullmatch(r"-?\d+", token):
            return Literal(int(token))
        if not re.fullmatch(r"[A-Za-z_]\w*", token):
            raise LanguageSyntaxError(f"expected a term, found {token!r}")

        if self._peek() != "(":
            if self.lowercase_variables and token[0].islower():
                return Var(token)
            return Application(token, ())

        self._take("(")
        children: list[Term] = []
        if self._peek() != ")":
            while True:
                children.append(self._parse_term())
                if self._peek() != ",":
                    break
                self._take(",")
        self._take(")")
        return Application(token, tuple(children))

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self, expected: str | None = None) -> str:
        token = self._peek()
        if token is None:
            wanted = f" {expected!r}" if expected else ""
            raise LanguageSyntaxError(f"expected{wanted}, found end of line")
        if expected is not None and token != expected:
            raise LanguageSyntaxError(f"expected {expected!r}, found {token!r}")
        self.index += 1
        return token


def parse_term(source: str, *, lowercase_variables: bool = False) -> Term:
    return TermParser(source, lowercase_variables=lowercase_variables).parse()


def parse_guard(source: str, line_number: int) -> ComparisonGuard:
    guard_match = GUARD_RE.fullmatch(source.strip())
    if guard_match is None:
        raise LanguageSyntaxError(
            f"rules line {line_number}: guards use 'name <op> integer'"
        )
    variable, operation, expected = guard_match.groups()
    return ComparisonGuard(variable, operation, int(expected))


def generated_rule_name(lhs: Term, line_number: int) -> str:
    if isinstance(lhs, Application):
        stem = lhs.symbol
    elif isinstance(lhs, Var):
        stem = "variable"
    else:
        stem = "literal"
    return f"{stem}-{line_number}"


def parse_rules(source: str) -> list[Rule]:
    parsed: list[Rule] = []
    names: set[str] = set()
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            lhs_and_name, rhs_and_guard = line.split("=>", 1)
        except ValueError as error:
            raise LanguageSyntaxError(
                f"rules line {line_number}: expected '[name:] lhs => rhs'"
            ) from error

        explicit_name, separator, lhs_source = lhs_and_name.partition(":")
        if not separator:
            lhs_source = explicit_name
            explicit_name = ""

        rhs_source, separator, guard_source = rhs_and_guard.partition(" when ")
        try:
            lhs = parse_term(lhs_source.strip(), lowercase_variables=True)
            rhs = parse_term(rhs_source.strip(), lowercase_variables=True)
            guard = parse_guard(guard_source, line_number) if separator else None
        except LanguageSyntaxError as error:
            raise LanguageSyntaxError(f"rules line {line_number}: {error}") from error

        name = explicit_name.strip() or generated_rule_name(lhs, line_number)
        if name in names:
            raise LanguageSyntaxError(
                f"rules line {line_number}: duplicate rule name {name!r}"
            )
        names.add(name)
        parsed.append(
            Rule(
                name=name,
                lhs=lhs,
                rhs=rhs,
                guard=guard,
                source_line=line_number,
            )
        )

    if not parsed:
        raise LanguageSyntaxError("rules: enter at least one rule")
    return parsed


def parse_inputs(source: str) -> list[tuple[int, Term]]:
    parsed: list[tuple[int, Term]] = []
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parsed.append((line_number, parse_term(line)))
        except LanguageSyntaxError as error:
            raise LanguageSyntaxError(f"inputs line {line_number}: {error}") from error
    if not parsed:
        raise LanguageSyntaxError("inputs: enter at least one term")
    return parsed
