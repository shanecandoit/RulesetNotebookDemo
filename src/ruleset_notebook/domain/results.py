"""Structured evaluation results, rewrite events, stop reasons, and errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

from .source import SourceSpan
from .terms import Term


class StopReason(str, Enum):
    """Why a single-input evaluation stopped."""

    NORMAL_FORM = "normal form"
    STEP_LIMIT = "step limit"
    DEPTH_LIMIT = "depth limit"
    CANCELLED = "cancelled"
    RUNTIME_ERROR = "runtime error"


class EngineError(Exception):
    """Base class for typed engine failures raised during evaluation."""

    code: str = "engine-error"

    def __init__(self, message: str, *, span: Optional[SourceSpan] = None) -> None:
        super().__init__(message)
        self.message = message
        self.span = span

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r})"


class DivisionByZeroError(EngineError):
    """A built-in numeric division by zero was attempted."""

    code = "division-by-zero"


class InvalidOperandError(EngineError):
    """A built-in received an operand of an unsupported type or shape."""

    code = "invalid-operand"


class UnboundVariableError(EngineError):
    """A substitution referenced a variable with no binding."""

    code = "unbound-variable"


@dataclass(frozen=True)
class RewriteEvent:
    """One successful rewrite step applied at a position in the term."""

    index: int
    before: Term
    after: Term
    rule_name: str
    rule_id: object
    position: tuple[int, ...]
    bindings: Mapping[str, Term]

    def __repr__(self) -> str:
        return (
            f"RewriteEvent(#{self.index} {self.rule_name} at {self.position or 'root'})"
        )


@dataclass(frozen=True)
class EvaluationResult:
    """The structured outcome of evaluating one input term."""

    input_term: Term
    output_term: Term
    events: tuple[RewriteEvent, ...]
    stop_reason: StopReason
    error: Optional[EngineError] = None
    source_line: int = 0

    def step_count(self) -> int:
        return len(self.events)

    def __repr__(self) -> str:
        return (
            f"EvaluationResult({self.input_term} -> {self.output_term}; "
            f"{self.step_count()} steps; {self.stop_reason.value})"
        )
