"""Shared plain-text parser for the GUI and command-line interfaces."""

from __future__ import annotations

import ast
import json
import re

from .domain import (
    Application,
    Diagnostic,
    GuardComparison,
    GuardConjunction,
    GuardExpr,
    GuardGroup,
    GuardValue,
    Literal,
    Rule,
    Severity,
    SourcePosition,
    SourceSpan,
    Term,
    Var,
)


class LanguageSyntaxError(ValueError):
    """A line-oriented syntax error suitable for user-facing diagnostics."""


TOKEN_RE = re.compile(
    r'\s*(?:(-?(?:\d+\.\d*|\.\d+))|(-?\d+)|("(?:\\.|[^"\\])*")|([A-Za-z_]\w*)|([(),]))'
)
GUARD_TOKEN_RE = re.compile(
    r"\s*(?:(==|!=|<=|>=|<|>)|(\()|(\))|(and\b)|(-?(?:\d+\.\d*|\.\d+))|"
    r'(-?\d+)|("(?:\\.|[^"\\])*")|([A-Za-z_]\w*))'
)


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
                if source[position] == '"':
                    raise LanguageSyntaxError("unterminated string literal")
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
        if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+)", token):
            return Literal(float(token))
        if re.fullmatch(r"-?\d+", token):
            return Literal(int(token))
        if token.startswith('"'):
            try:
                value = ast.literal_eval(token)
            except (SyntaxError, ValueError) as error:
                raise LanguageSyntaxError("invalid string literal") from error
            return Literal(value)
        if not re.fullmatch(r"[A-Za-z_]\w*", token):
            raise LanguageSyntaxError(f"expected a term, found {token!r}")

        if token in {"true", "false"}:
            return Literal(token == "true")

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


def format_term(term: Term) -> str:
    """Return the canonical text form accepted by the term parser."""

    if isinstance(term, Var):
        return term.name
    if isinstance(term, Application):
        children = ", ".join(format_term(child) for child in term.children)
        return f"{term.symbol}({children})"
    value = term.value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


class GuardParser:
    def __init__(self, source: str, line_number: int):
        self.line_number = line_number
        self.tokens: list[str] = []
        position = 0
        while position < len(source):
            match = GUARD_TOKEN_RE.match(source, position)
            if match is None:
                raise LanguageSyntaxError(
                    f"rules line {line_number}: invalid guard near "
                    f"column {position + 1}"
                )
            self.tokens.append(next(part for part in match.groups() if part))
            position = match.end()
        self.index = 0

    def parse(self) -> GuardExpr:
        items = [self._parse_group()]
        while self._peek() == "and":
            self._take()
            items.append(self._parse_group())
        if self._peek() is not None and self._peek() != ")":
            raise LanguageSyntaxError(
                f"rules line {self.line_number}: unexpected guard token "
                f"{self._peek()!r}"
            )
        if len(items) == 1:
            return items[0]
        return GuardConjunction(tuple(items))

    def _parse_group(self) -> GuardExpr:
        if self._peek() == "(":
            self._take()
            expression = self.parse()
            if self._take() != ")":
                raise LanguageSyntaxError(
                    f"rules line {self.line_number}: expected ')' in guard"
                )
            return GuardGroup(expression)
        left = self._parse_value()
        operation = self._take()
        if operation not in {"==", "!=", "<", "<=", ">", ">="}:
            raise LanguageSyntaxError(
                f"rules line {self.line_number}: expected comparison operator"
            )
        return GuardComparison(left, operation, self._parse_value())

    def _parse_value(self) -> GuardValue:
        token = self._take()
        return GuardValue(parse_term(token, lowercase_variables=True))

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise LanguageSyntaxError(
                f"rules line {self.line_number}: incomplete guard"
            )
        self.index += 1
        return token


def parse_guard(source: str, line_number: int) -> GuardExpr:
    return GuardParser(source.strip(), line_number).parse()


def generated_rule_name(lhs: Term, line_number: int) -> str:
    if isinstance(lhs, Application):
        stem = lhs.symbol
    elif isinstance(lhs, Var):
        stem = "variable"
    else:
        stem = "literal"
    return f"{stem}-{line_number}"


def _variable_names(term: Term) -> set[str]:
    if isinstance(term, Var):
        return {term.name}
    if isinstance(term, Application):
        names: set[str] = set()
        for child in term.children:
            names.update(_variable_names(child))
        return names
    return set()


def _guard_variable_names(guard: GuardExpr) -> set[str]:
    names: set[str] = set()
    if isinstance(guard, GuardGroup):
        return _guard_variable_names(guard.expression)
    if isinstance(guard, GuardConjunction):
        for item in guard.items:
            names.update(_guard_variable_names(item))
    else:
        names.update(_variable_names(guard.left.term))
        names.update(_variable_names(guard.right.term))
    return names


def validate_rule(rule: Rule) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if isinstance(rule.lhs, Var):
        diagnostics.append(
            Diagnostic(
                code="catch-all-rule",
                severity=Severity.ERROR,
                message="a rule LHS must contain a symbol or literal",
            )
        )
    bound = _variable_names(rule.lhs)
    for name in sorted(_variable_names(rule.rhs) - bound):
        diagnostics.append(
            Diagnostic(
                code="unbound-rhs-variable",
                severity=Severity.ERROR,
                message=f"RHS variable {name!r} is not bound by the LHS",
            )
        )
    if rule.guard is not None:
        for name in sorted(_guard_variable_names(rule.guard) - bound):
            diagnostics.append(
                Diagnostic(
                    code="unbound-guard-variable",
                    severity=Severity.ERROR,
                    message=f"guard variable {name!r} is not bound by the LHS",
                )
            )
    return diagnostics


def validate_rules_text(source: str) -> list[Diagnostic]:
    """Return rule diagnostics without raising a UI-facing exception."""

    try:
        rules = parse_rules(source)
    except LanguageSyntaxError as error:
        line_number = 1
        match = re.search(r"rules line (\d+):", str(error))
        if match:
            line_number = int(match.group(1))
        line = source.splitlines()[line_number - 1] if source.splitlines() else ""
        end_column = max(len(line), 1)
        span = SourceSpan(
            SourcePosition(line_number - 1, 0, 0),
            SourcePosition(line_number - 1, end_column, end_column),
        )
        message = str(error)
        code = "rule-syntax"
        if "RHS variable" in message:
            code = "unbound-rhs-variable"
        elif "LHS must contain" in message:
            code = "catch-all-rule"
        return [
            Diagnostic(
                code=code,
                severity=Severity.ERROR,
                message=message,
                span=span,
            )
        ]
    diagnostics: list[Diagnostic] = []
    for rule in rules:
        diagnostics.extend(validate_rule(rule))
    return diagnostics


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
        rule = Rule(
            name=name,
            lhs=lhs,
            rhs=rhs,
            guard=guard,
            source_line=line_number,
        )
        validation_errors = validate_rule(rule)
        if validation_errors:
            raise LanguageSyntaxError(
                f"rules line {line_number}: {validation_errors[0].message}"
            )
        parsed.append(rule)

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
