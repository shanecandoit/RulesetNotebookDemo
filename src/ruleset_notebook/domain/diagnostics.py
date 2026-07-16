"""Typed diagnostics produced during parsing, validation, and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .source import SourceSpan


class Severity(str, Enum):
    """Diagnostic severity level."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Diagnostic:
    """A typed diagnostic with a stable code, severity, message, span, and hint."""

    code: str
    severity: Severity
    message: str
    span: Optional[SourceSpan] = None
    hint: Optional[str] = None

    def __repr__(self) -> str:
        span_text = f" @ {self.span}" if self.span is not None else ""
        return (
            f"Diagnostic({self.severity.value}:{self.code}: {self.message}{span_text})"
        )
