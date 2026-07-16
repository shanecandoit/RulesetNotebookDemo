"""Immutable rule and evaluation settings domain types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .terms import Term


@dataclass(frozen=True)
class ComparisonGuard:
    """A safe comparison between a bound variable and an integer literal."""

    variable: str
    operation: str
    expected: int


@dataclass(frozen=True)
class Rule:
    """An immutable rewrite rule with a stable identity.

    A rule maps a left-hand side pattern (``lhs``) to a right-hand side template
    (``rhs``). Pattern variables in ``lhs`` bind terms that are substituted into
    ``rhs``. An optional guard restricts when the rule applies, and ``enabled``
    allows rules to be toggled without changing their identity.
    """

    name: str
    lhs: Term
    rhs: Term
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    guard: ComparisonGuard | None = None
    enabled: bool = True
    source_line: int = 0

    def __repr__(self) -> str:
        state = "" if self.enabled else " (disabled)"
        return f"Rule({self.name!r}: {self.lhs} => {self.rhs}{state})"


@dataclass(frozen=True)
class EvaluationSettings:
    """Validated limits for a single evaluation run.

    Both ``max_steps`` and ``max_depth`` must be positive; otherwise construction
    raises ``ValueError`` so invalid limits never reach the engine.
    """

    max_steps: int = 100
    max_depth: int = 1000

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        if self.max_depth <= 0:
            raise ValueError("max_depth must be a positive integer")

    def __repr__(self) -> str:
        return (
            f"EvaluationSettings(max_steps={self.max_steps}, "
            f"max_depth={self.max_depth})"
        )
