"""Immutable term variants for the term-rewriting engine.

A term is one of three shapes:

* ``Var``: a lowercase pattern variable such as ``x``.
* ``Literal``: an immutable literal value (int, float, str, bool, ...).
* ``Application``: a named symbol applied to a tuple of child terms.

Terms are frozen dataclasses so they are hashable and structurally comparable.
Child terms are stored as tuples to preserve immutability and ordering. ``repr``
is intended only for development readability; it is not a canonical serialization
format (see the language formatter for that).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class Var:
    """A lowercase pattern variable bound during rule matching."""

    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Literal:
    """An immutable literal value such as an integer, float, string, or bool."""

    value: object

    def __repr__(self) -> str:
        return repr(self.value)


@dataclass(frozen=True)
class Application:
    """A symbol applied to a tuple of child terms, e.g. ``add(1, 2)``."""

    symbol: str
    children: tuple[Term, ...]

    def __repr__(self) -> str:
        joined = ", ".join(repr(child) for child in self.children)
        return f"{self.symbol}({joined})"


Term = Union[Var, Literal, Application]
TermPosition = tuple[int, ...]


def is_variable(term: Term) -> bool:
    return isinstance(term, Var)


def symbol_of(term: Term) -> str | None:
    """Return the application symbol, or ``None`` for variables/literals."""
    return term.symbol if isinstance(term, Application) else None
