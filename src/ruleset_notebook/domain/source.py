"""Source position and span types used for diagnostics and traces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePosition:
    """A zero-based position inside a source string."""

    line: int
    column: int
    offset: int

    def __repr__(self) -> str:
        return (
            f"SourcePosition(line={self.line}, column={self.column}, "
            f"offset={self.offset})"
        )


@dataclass(frozen=True)
class SourceSpan:
    """A contiguous region of source text from ``start`` to ``end`` (inclusive)."""

    start: SourcePosition
    end: SourcePosition

    def __repr__(self) -> str:
        return (
            f"SourceSpan(line={self.start.line}, "
            f"column={self.start.column}, "
            f"end_line={self.end.line}, "
            f"end_column={self.end.column})"
        )
