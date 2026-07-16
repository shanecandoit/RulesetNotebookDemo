"""Tests for source positions, spans, and typed diagnostics."""

from ruleset_notebook.domain import (
    Diagnostic,
    Severity,
    SourcePosition,
    SourceSpan,
)


def test_source_position_repr():
    pos = SourcePosition(line=2, column=4, offset=10)
    assert pos.line == 2
    assert pos.column == 4
    assert pos.offset == 10


def test_source_span_repr_and_equality():
    start = SourcePosition(line=1, column=0, offset=0)
    end = SourcePosition(line=1, column=5, offset=5)
    span = SourceSpan(start, end)
    same = SourceSpan(
        SourcePosition(line=1, column=0, offset=0),
        SourcePosition(line=1, column=5, offset=5),
    )
    assert span == same
    assert hash(span) == hash(same)


def test_diagnostic_defaults_and_repr():
    diag = Diagnostic(code="E1", severity=Severity.ERROR, message="bad token")
    assert diag.span is None
    assert diag.hint is None
    assert "E1" in repr(diag)


def test_diagnostic_with_span_and_hint():
    span = SourceSpan(
        SourcePosition(line=1, column=0, offset=0),
        SourcePosition(line=1, column=3, offset=3),
    )
    diag = Diagnostic(
        code="E2",
        severity=Severity.WARNING,
        message="ambiguous rule",
        span=span,
        hint="add an explicit name",
    )
    assert diag.severity is Severity.WARNING
    assert diag.hint == "add an explicit name"
    assert diag.span == span


def test_severity_is_string_enum():
    assert Severity.ERROR.value == "error"
    assert Severity.WARNING.value == "warning"
    assert Severity.INFO.value == "info"
