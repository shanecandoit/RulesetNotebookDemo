"""Compatibility launcher for running the Ruleset Notebook from the repo root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ruleset_notebook.ui.main_window import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
