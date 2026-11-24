"""Standalone C backend for Ruleset Notebook."""

from .codegen import CompilationError, generate_c

__all__ = ["CompilationError", "generate_c"]
