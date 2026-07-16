import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(1)


def run_coverage(python: str) -> None:
    cmd = [
        python,
        "-m",
        "pytest",
        "--cov=src/ruleset_notebook",
        "--cov-report=term-missing",
    ]
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    report = result.stdout + result.stderr
    marker = "=============================== tests coverage"
    summary = report[report.find(marker) :] if marker in report else report
    Path("coverage.txt").write_text(summary, encoding="utf-8")
    print(report, end="")
    if result.returncode != 0:
        raise SystemExit(1)


def main() -> None:
    python = sys.executable
    run([python, "-m", "ruff", "format", "--check", "."])
    run([python, "-m", "ruff", "check", "."])
    run([python, "-m", "mypy", "src"])
    run_coverage(python)


if __name__ == "__main__":
    main()
