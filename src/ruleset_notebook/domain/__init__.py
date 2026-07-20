"""Immutable domain types for the term-rewriting engine.

This package has no Qt or file-system dependencies so it can be imported, tested,
and driven from the command line on its own.
"""

from .diagnostics import Diagnostic, Severity
from .results import (
    DivisionByZeroError,
    EngineError,
    EvaluationResult,
    GuardEvaluationError,
    InvalidOperandError,
    RewriteEvent,
    StopReason,
    UnboundVariableError,
)
from .rules import (
    EvaluationSettings,
    GuardComparison,
    GuardConjunction,
    GuardExpr,
    GuardGroup,
    GuardValue,
    Rule,
)
from .source import SourcePosition, SourceSpan
from .terms import Application, Literal, Term, TermPosition, Var

__all__ = [
    "Application",
    "Literal",
    "Term",
    "TermPosition",
    "Var",
    "SourcePosition",
    "SourceSpan",
    "Diagnostic",
    "Severity",
    "Rule",
    "GuardValue",
    "GuardComparison",
    "GuardConjunction",
    "GuardExpr",
    "GuardGroup",
    "EvaluationSettings",
    "RewriteEvent",
    "EvaluationResult",
    "StopReason",
    "EngineError",
    "DivisionByZeroError",
    "InvalidOperandError",
    "GuardEvaluationError",
    "UnboundVariableError",
]
