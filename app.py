"""Prototype term-rewriting engine and first-pass PySide6 demo UI.

The engine types at the top of this file retain the original prototype API.  The
UI below them demonstrates the v1 workflow described in README.md: edit two plain
text buffers, run them as one immutable job, and reload cached job text later.
"""

from __future__ import annotations

import operator
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class Term:
    pass


class Const(Term):
    def __init__(self, value: object):
        self.value = value

    def __repr__(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Const) and self.value == other.value


class Var(Term):
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Var) and self.name == other.name


class Func(Term):
    def __init__(self, name: str, args: list[Term]):
        self.name = name
        self.args = list(args)

    def __repr__(self) -> str:
        return f"{self.name}({', '.join(map(str, self.args))})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Func)
            and self.name == other.name
            and self.args == other.args
        )


def match(pattern: Term, subject: Term, env=None) -> dict | None:
    """Match a pattern and return its variable bindings."""
    if env is None:
        env = {}

    if isinstance(pattern, Var):
        if pattern.name in env:
            return env if env[pattern.name] == subject else None
        new_env = env.copy()
        new_env[pattern.name] = subject
        return new_env

    if isinstance(pattern, Const):
        if isinstance(subject, Const) and pattern.value == subject.value:
            return env
        return None

    if isinstance(pattern, Func):
        if not isinstance(subject, Func) or pattern.name != subject.name:
            return None
        if len(pattern.args) != len(subject.args):
            return None

        current_env = env
        for pattern_arg, subject_arg in zip(pattern.args, subject.args):
            current_env = match(pattern_arg, subject_arg, current_env)
            if current_env is None:
                return None
        return current_env

    return None


def substitute(template: Term, env: dict) -> Term:
    """Replace variables and reduce the tiny prototype arithmetic built-ins."""
    if isinstance(template, Var):
        return env.get(template.name, template)
    if isinstance(template, Const):
        return template
    if isinstance(template, Func):
        args = [substitute(arg, env) for arg in template.args]
        if template.name in ("+", "-") and len(args) == 2:
            left, right = args
            if isinstance(left, Const) and isinstance(right, Const):
                if template.name == "+":
                    return Const(left.value + right.value)
                return Const(left.value - right.value)
        if template.name in ("inc", "dec") and len(args) == 1:
            value = args[0]
            if isinstance(value, Const) and isinstance(value.value, int):
                amount = 1 if template.name == "inc" else -1
                return Const(value.value + amount)
        return Func(template.name, args)
    return template


Guard = Callable[[dict[str, Term]], bool]


class Rule:
    def __init__(
        self,
        lhs: Term,
        rhs: Term,
        name: str = "rule",
        guard: Guard | None = None,
    ):
        self.lhs = lhs
        self.rhs = rhs
        self.name = name
        self.guard = guard


def _attempt_rewrite(
    term: Term, rules: list[Rule]
) -> tuple[Term, bool, Rule | None, dict[str, Term]]:
    for rule in rules:
        env = match(rule.lhs, term)
        if env is not None and (rule.guard is None or rule.guard(env)):
            return substitute(rule.rhs, env), True, rule, env
    return term, False, None, {}


def rewrite_step(term: Term, rules: list[Rule]) -> tuple[Term, bool]:
    """Try the ordered rules at the root of a term."""
    result, changed, _rule, _env = _attempt_rewrite(term, rules)
    return result, changed


def evaluate(term: Term, rules: list[Rule]) -> Term:
    """Original prototype's recursive, innermost evaluation strategy."""
    if isinstance(term, Func):
        term = Func(term.name, [evaluate(arg, rules) for arg in term.args])

    result, changed = rewrite_step(term, rules)
    if changed:
        return evaluate(result, rules)
    return result


def add_expr(left: Term, right: Term) -> Func:
    return Func("+", [left, right])


def sub_expr(left: Term, right: Term) -> Func:
    return Func("-", [left, right])


rule1 = Rule(Func("add", [Var("a"), Const(0)]), Var("a"), "add-zero")
rule2 = Rule(
    Func("add", [Var("a"), Var("b")]),
    Func("add", [add_expr(Var("a"), Const(1)), sub_expr(Var("b"), Const(1))]),
    "add-step",
)
rules = [rule1, rule2]


class DemoSyntaxError(ValueError):
    """A source error produced by the deliberately small demo parser."""


TOKEN_RE = re.compile(r"\s*(?:(-?\d+)|([A-Za-z_]\w*)|([(),]))")


class TermParser:
    def __init__(self, source: str, *, lowercase_variables: bool = False):
        self.source = source
        self.lowercase_variables = lowercase_variables
        self.tokens: list[str] = []
        position = 0
        while position < len(source):
            token_match = TOKEN_RE.match(source, position)
            if token_match is None:
                raise DemoSyntaxError(
                    f"unexpected text at column {position + 1}: "
                    f"{source[position : position + 12]!r}"
                )
            self.tokens.append(next(part for part in token_match.groups() if part))
            position = token_match.end()
        self.index = 0

    def parse(self) -> Term:
        if not self.tokens:
            raise DemoSyntaxError("expected a term")
        term = self._parse_term()
        if self.index != len(self.tokens):
            raise DemoSyntaxError(f"unexpected token {self.tokens[self.index]!r}")
        return term

    def _parse_term(self) -> Term:
        token = self._take()
        if re.fullmatch(r"-?\d+", token):
            return Const(int(token))
        if not re.fullmatch(r"[A-Za-z_]\w*", token):
            raise DemoSyntaxError(f"expected a term, found {token!r}")

        if self._peek() != "(":
            if self.lowercase_variables and token[0].islower():
                return Var(token)
            return Func(token, [])
        self._take("(")
        args: list[Term] = []
        if self._peek() != ")":
            while True:
                args.append(self._parse_term())
                if self._peek() != ",":
                    break
                self._take(",")
        self._take(")")
        return Func(token, args)

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self, expected: str | None = None) -> str:
        token = self._peek()
        if token is None:
            wanted = f" {expected!r}" if expected else ""
            raise DemoSyntaxError(f"expected{wanted}, found end of line")
        if expected is not None and token != expected:
            raise DemoSyntaxError(f"expected {expected!r}, found {token!r}")
        self.index += 1
        return token


def parse_term(source: str, *, lowercase_variables: bool = False) -> Term:
    return TermParser(source, lowercase_variables=lowercase_variables).parse()


GUARD_RE = re.compile(r"^([a-z][A-Za-z0-9_]*)\s*(==|!=|<=|>=|<|>)\s*(-?\d+)$")
GUARD_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def parse_guard(source: str, line_number: int) -> Guard:
    guard_match = GUARD_RE.fullmatch(source.strip())
    if guard_match is None:
        raise DemoSyntaxError(
            f"rules line {line_number}: demo guards use 'name <op> integer'"
        )
    variable, operation, expected_source = guard_match.groups()
    expected = int(expected_source)
    compare = GUARD_OPERATORS[operation]

    def guard(env: dict[str, Term]) -> bool:
        value = env.get(variable)
        return (
            isinstance(value, Const)
            and isinstance(value.value, int)
            and compare(value.value, expected)
        )

    return guard


def parse_rules(source: str) -> list[Rule]:
    parsed: list[Rule] = []
    names: set[str] = set()
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            lhs_and_name, rhs_and_guard = line.split("=>", 1)
        except ValueError as error:
            raise DemoSyntaxError(
                f"rules line {line_number}: expected '[name:] lhs => rhs'"
            ) from error

        explicit_name, separator, lhs_source = lhs_and_name.partition(":")
        if not separator:
            lhs_source = explicit_name
            explicit_name = ""

        rhs_source, separator, guard_source = rhs_and_guard.partition(" when ")
        try:
            lhs = parse_term(lhs_source.strip(), lowercase_variables=True)
            rhs = parse_term(rhs_source.strip(), lowercase_variables=True)
            guard = parse_guard(guard_source, line_number) if separator else None
        except DemoSyntaxError as error:
            raise DemoSyntaxError(f"rules line {line_number}: {error}") from error

        name = explicit_name.strip() or generated_rule_name(lhs, line_number)
        if name in names:
            raise DemoSyntaxError(
                f"rules line {line_number}: duplicate rule name {name!r}"
            )
        names.add(name)
        parsed.append(Rule(lhs, rhs, name, guard))
    if not parsed:
        raise DemoSyntaxError("rules: enter at least one rule")
    return parsed


def generated_rule_name(lhs: Term, line_number: int) -> str:
    """Create a readable, stable name for an unnamed source rule."""
    if isinstance(lhs, Func):
        stem = lhs.name
    elif isinstance(lhs, Var):
        stem = "variable"
    else:
        stem = "literal"
    return f"{stem}-{line_number}"


def parse_inputs(source: str) -> list[tuple[int, Term]]:
    parsed: list[tuple[int, Term]] = []
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parsed.append((line_number, parse_term(line)))
        except DemoSyntaxError as error:
            raise DemoSyntaxError(f"inputs line {line_number}: {error}") from error
    if not parsed:
        raise DemoSyntaxError("inputs: enter at least one term")
    return parsed


def evaluate_with_trace(
    term: Term, active_rules: list[Rule], max_steps: int = 100
) -> tuple[Term, list[str], str]:
    """Evaluate root rewrites and return human-readable demo trace lines."""
    current = term
    lines = [f"  0. {current}"]
    for index in range(1, max_steps + 1):
        next_term, changed, selected_rule, bindings = _attempt_rewrite(
            current, active_rules
        )
        if not changed or selected_rule is None:
            return current, lines, "normal form"
        binding_text = ", ".join(
            f"{name}={value}" for name, value in sorted(bindings.items())
        )
        lines.append(
            f"  {index}. {next_term} "
            f"[{selected_rule.name}; {binding_text}; position=root]"
        )
        current = next_term
    return current, lines, "step limit"


@dataclass(frozen=True)
class DemoJob:
    job_id: str
    created_at: str
    status: str
    rules_text: str
    inputs_text: str
    results_text: str
    rule_count: int
    input_count: int
    result_summary: str

    @property
    def filename(self) -> str:
        return f"{self.job_id}.rsjob"

    def to_text(self) -> str:
        return (
            "RULESET-NOTEBOOK-JOB 1\n"
            f"job-id: {self.job_id}\n"
            f"created-at: {self.created_at}\n"
            f"status: {self.status}\n"
            "max-steps: 100\n"
            f"rule-count: {self.rule_count}\n"
            f"input-count: {self.input_count}\n"
            f"result-summary: {self.result_summary}\n"
            "\n--- RULES ---\n"
            f"{self.rules_text.rstrip()}\n"
            "\n--- INPUTS ---\n"
            f"{self.inputs_text.rstrip()}\n"
            "\n--- RESULTS-AND-TRACES ---\n"
            f"{self.results_text.rstrip()}\n"
        )

    @classmethod
    def from_text(cls, source: str) -> DemoJob:
        try:
            header, remainder = source.split("\n--- RULES ---\n", 1)
            rules_text, remainder = remainder.split("\n--- INPUTS ---\n", 1)
            inputs_text, results_text = remainder.split(
                "\n--- RESULTS-AND-TRACES ---\n", 1
            )
        except ValueError as error:
            raise DemoSyntaxError("job file has missing or invalid sections") from error

        header_lines = header.splitlines()
        if not header_lines or header_lines[0] != "RULESET-NOTEBOOK-JOB 1":
            raise DemoSyntaxError("unsupported job file header")
        metadata: dict[str, str] = {}
        for line in header_lines[1:]:
            if not line.strip():
                continue
            key, separator, value = line.partition(": ")
            if not separator:
                raise DemoSyntaxError(f"invalid job header line: {line!r}")
            metadata[key] = value
        required = {"job-id", "created-at", "status", "rule-count", "input-count"}
        if missing := required - metadata.keys():
            raise DemoSyntaxError(f"job file is missing: {', '.join(sorted(missing))}")
        return cls(
            job_id=metadata["job-id"],
            created_at=metadata["created-at"],
            status=metadata["status"],
            rules_text=rules_text.strip("\n"),
            inputs_text=inputs_text.strip("\n"),
            results_text=results_text.strip("\n"),
            rule_count=int(metadata["rule-count"]),
            input_count=int(metadata["input-count"]),
            result_summary=metadata.get("result-summary", ""),
        )


DEFAULT_RULES = """\
# Rules are tried from top to bottom.
add(x, 0) => x
add(x, y) => add(inc(x), dec(y)) when y > 0
"""

DEFAULT_INPUTS = """\
# One input term per non-empty line.
add(2, 3)
add(10, 4)
"""


class RulesetNotebookWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.jobs: dict[str, DemoJob] = {}
        self.cache_dir = self._cache_directory()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.setWindowTitle("Ruleset Notebook - Text Job Demo")
        self.resize(1320, 820)

        self.job_table = QTableWidget(0, 6)
        self.job_table.setHorizontalHeaderLabels(
            ["Job ID", "Rules", "Inputs", "Result", "Status", "Created"]
        )
        self.job_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.job_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.job_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.job_table.verticalHeader().setVisible(False)
        table_palette = self.job_table.palette()
        for color_group in (
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
        ):
            table_palette.setColor(
                color_group,
                QPalette.ColorRole.Highlight,
                QColor("#3b82f6"),
            )
            table_palette.setColor(
                color_group,
                QPalette.ColorRole.HighlightedText,
                QColor("#ffffff"),
            )
        self.job_table.setPalette(table_palette)
        self.job_table.setStyleSheet(
            """
            QTableWidget {
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
                gridline-color: #d8e2ef;
            }
            QTableWidget::item:selected:!active {
                background-color: #75a7e8;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #eaf2fc;
                color: #17365d;
                border: 0;
                border-right: 1px solid #c7d7eb;
                border-bottom: 1px solid #b8cce4;
                padding: 5px 7px;
                font-weight: 600;
            }
            """
        )
        header = self.job_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.job_table.itemSelectionChanged.connect(self.load_selected_job)

        self.rules_edit = self._make_editor("Ordered rules, one per line")
        self.inputs_edit = self._make_editor("Input terms, one per line")
        self.results_edit = self._make_editor("Cached results and traces")
        self.results_edit.setReadOnly(True)

        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.addWidget(self._labeled_pane("Rules", self.rules_edit))
        panes.addWidget(self._labeled_pane("Notebook inputs", self.inputs_edit))
        panes.addWidget(self._labeled_pane("Results / traces", self.results_edit))
        panes.setSizes([380, 380, 560])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 8)
        jobs_label = QLabel("Cached jobs")
        jobs_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(jobs_label)
        layout.addWidget(self.job_table, 2)
        layout.addWidget(panes, 5)
        self.setCentralWidget(central)

        self._create_actions()
        self._create_toolbar()
        self.statusBar().showMessage("Draft mode - edit text and choose Run")
        self.refresh_jobs()
        self.new_draft()

    def _cache_directory(self) -> Path:
        location = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        if not location:
            location = str(Path.home() / ".ruleset-notebook")
        return Path(location) / "jobs"

    def _make_editor(self, placeholder: str) -> QPlainTextEdit:
        editor = QPlainTextEdit()
        editor.setPlaceholderText(placeholder)
        editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        return editor

    def _labeled_pane(self, title: str, editor: QPlainTextEdit) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)
        label = QLabel(title)
        label.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(label)
        layout.addWidget(editor)
        return widget

    def _create_actions(self) -> None:
        self.new_action = QAction("New Draft", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_draft)

        self.run_action = QAction("Run", self)
        self.run_action.setShortcut("Ctrl+Return")
        self.run_action.triggered.connect(self.run_draft)

        self.duplicate_action = QAction("Duplicate as Draft", self)
        self.duplicate_action.triggered.connect(self.duplicate_as_draft)

        self.delete_action = QAction("Delete Job", self)
        self.delete_action.triggered.connect(self.delete_selected_job)

        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.setShortcut("F5")
        self.refresh_action.triggered.connect(self.refresh_jobs)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Job actions")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_action)
        toolbar.addSeparator()
        toolbar.addAction(self.run_action)
        toolbar.addSeparator()
        toolbar.addAction(self.duplicate_action)
        toolbar.addAction(self.delete_action)
        toolbar.addAction(self.refresh_action)
        self.addToolBar(toolbar)

    def new_draft(self) -> None:
        self.job_table.clearSelection()
        self.rules_edit.setReadOnly(False)
        self.inputs_edit.setReadOnly(False)
        self.rules_edit.setPlainText(DEFAULT_RULES)
        self.inputs_edit.setPlainText(DEFAULT_INPUTS)
        self.results_edit.clear()
        self.run_action.setEnabled(True)
        self.statusBar().showMessage("Draft mode - edit text and choose Run")

    def run_draft(self) -> None:
        rules_text = self.rules_edit.toPlainText()
        inputs_text = self.inputs_edit.toPlainText()
        job_id = f"{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        status = "normal form"
        result_summary = ""
        results_text = ""
        rule_count = 0
        input_count = 0

        try:
            active_rules = parse_rules(rules_text)
            inputs = parse_inputs(inputs_text)
            rule_count = len(active_rules)
            input_count = len(inputs)
            sections: list[str] = []
            summaries: list[str] = []
            statuses: list[str] = []
            for display_index, (line_number, term) in enumerate(inputs, 1):
                result, trace_lines, input_status = evaluate_with_trace(
                    term, active_rules
                )
                sections.extend(
                    [
                        f"input {display_index} (source line {line_number}): {term}",
                        *trace_lines,
                        f"result: {result}",
                        f"status: {input_status}",
                        "",
                    ]
                )
                summaries.append(str(result))
                statuses.append(input_status)
            results_text = "\n".join(sections).rstrip()
            result_summary = "; ".join(summaries)
            if any(item == "step limit" for item in statuses):
                status = "step limit"
        except DemoSyntaxError as error:
            status = "parse error"
            result_summary = "syntax error"
            results_text = f"status: parse error\nerror: {error}"

        job = DemoJob(
            job_id=job_id,
            created_at=created_at,
            status=status,
            rules_text=rules_text,
            inputs_text=inputs_text,
            results_text=results_text,
            rule_count=rule_count,
            input_count=input_count,
            result_summary=result_summary,
        )
        try:
            self._write_job(job)
        except OSError as error:
            QMessageBox.warning(
                self,
                "Job could not be cached",
                f"The result is shown, but its job file was not saved.\n\n{error}",
            )
            self.results_edit.setPlainText(results_text)
            self.statusBar().showMessage(f"Job {job_id} finished but was not cached")
            return

        self.refresh_jobs(select_job_id=job_id)
        self.statusBar().showMessage(f"Cached job {job_id} - {status}")

    def _write_job(self, job: DemoJob) -> None:
        target = self.cache_dir / job.filename
        temporary = target.with_suffix(".tmp")
        temporary.write_text(job.to_text(), encoding="utf-8")
        temporary.replace(target)

    def _job_status_brush(self, status: str) -> QBrush | None:
        if status == "normal form":
            return QBrush(QColor("#cce5ff"))
        if status in {"parse error", "runtime error", "internal error"}:
            return QBrush(QColor("#f8d7da"))
        if status in {"step limit", "depth limit", "cancelled"}:
            return QBrush(QColor("#e2e3e5"))
        return None

    def _update_selection_color(self) -> None:
        for row in range(self.job_table.rowCount()):
            for column in range(self.job_table.columnCount()):
                item = self.job_table.item(row, column)
                if item is not None:
                    item.setBackground(QBrush(QColor("#ffffff")))
        job = self.selected_job()
        if job is None:
            return
        brush = self._job_status_brush(job.status)
        current_row = self.job_table.currentRow()
        if brush is not None and current_row >= 0:
            for column in range(self.job_table.columnCount()):
                item = self.job_table.item(current_row, column)
                if item is not None:
                    item.setBackground(brush)

    def refresh_jobs(self, select_job_id: str | None = None) -> None:
        self.jobs.clear()
        for path in self.cache_dir.glob("*.rsjob"):
            try:
                job = DemoJob.from_text(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            self.jobs[job.job_id] = job

        ordered = sorted(
            self.jobs.values(), key=lambda job: job.created_at, reverse=True
        )
        self.job_table.setRowCount(len(ordered))
        selected_row = -1
        for row, job in enumerate(ordered):
            values = [
                job.job_id,
                str(job.rule_count),
                str(job.input_count),
                job.result_summary,
                job.status,
                job.created_at.replace("T", " "),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.job_table.setItem(row, column, item)
            if job.job_id == select_job_id:
                selected_row = row
        if selected_row >= 0:
            self.job_table.selectRow(selected_row)
        self._update_selection_color()

    def selected_job(self) -> DemoJob | None:
        row = self.job_table.currentRow()
        if row < 0:
            return None
        item = self.job_table.item(row, 0)
        return self.jobs.get(item.text()) if item else None

    def load_selected_job(self) -> None:
        self._update_selection_color()
        job = self.selected_job()
        if job is None:
            return
        self.rules_edit.setPlainText(job.rules_text)
        self.inputs_edit.setPlainText(job.inputs_text)
        self.results_edit.setPlainText(job.results_text)
        self.rules_edit.setReadOnly(True)
        self.inputs_edit.setReadOnly(True)
        self.run_action.setEnabled(False)
        self.statusBar().showMessage(
            f"Historical job {job.job_id} — duplicate it to make changes"
        )

    def duplicate_as_draft(self) -> None:
        job = self.selected_job()
        if job is None:
            self.statusBar().showMessage("Select a cached job to duplicate")
            return
        self.job_table.clearSelection()
        self.rules_edit.setReadOnly(False)
        self.inputs_edit.setReadOnly(False)
        self.rules_edit.setPlainText(job.rules_text)
        self.inputs_edit.setPlainText(job.inputs_text)
        self.results_edit.clear()
        self.run_action.setEnabled(True)
        self.statusBar().showMessage(f"Draft duplicated from {job.job_id}")

    def delete_selected_job(self) -> None:
        job = self.selected_job()
        if job is None:
            self.statusBar().showMessage("Select a cached job to delete")
            return
        response = QMessageBox.question(
            self,
            "Delete cached job?",
            f"Delete {job.job_id}? This cannot be undone.",
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        try:
            (self.cache_dir / job.filename).unlink()
        except OSError as error:
            QMessageBox.warning(self, "Could not delete job", str(error))
            return
        self.refresh_jobs()
        self.new_draft()


def main() -> int:
    application = QApplication(sys.argv)
    application.setOrganizationName("RulesetNotebook")
    application.setApplicationName("Ruleset Notebook")
    window = RulesetNotebookWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
