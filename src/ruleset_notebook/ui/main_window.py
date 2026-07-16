"""PySide6 shell for the shared Ruleset Notebook parser and rewrite engine."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

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

from ruleset_notebook.engine import evaluate_with_trace, format_trace_lines
from ruleset_notebook.jobs import JobRecord, JobStore
from ruleset_notebook.language import LanguageSyntaxError, parse_inputs, parse_rules

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


class RulesetNotebookWindow(QMainWindow):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self.jobs: dict[str, JobRecord] = {}
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
        job_id = JobRecord.new_id()
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
                result = evaluate_with_trace(
                    term,
                    active_rules,
                    source_line=line_number,
                )
                trace_lines = format_trace_lines(result)
                input_status = result.stop_reason.value
                sections.extend(
                    [
                        f"input {display_index} (source line {line_number}): {term}",
                        *trace_lines,
                        f"result: {result.output_term}",
                        f"status: {input_status}",
                        "",
                    ]
                )
                summaries.append(str(result.output_term))
                statuses.append(input_status)
            results_text = "\n".join(sections).rstrip()
            result_summary = "; ".join(summaries)
            if any(item == "step limit" for item in statuses):
                status = "step limit"
        except LanguageSyntaxError as error:
            status = "parse error"
            result_summary = "syntax error"
            results_text = f"status: parse error\nerror: {error}"

        job = JobRecord(
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

    def _write_job(self, job: JobRecord) -> None:
        JobStore(self.cache_dir).write(job)

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
        self.jobs = JobStore(self.cache_dir).list_jobs()

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

    def selected_job(self) -> JobRecord | None:
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
            f"Historical job {job.job_id} - duplicate it to make changes"
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
            JobStore(self.cache_dir).delete(job)
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
    return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
