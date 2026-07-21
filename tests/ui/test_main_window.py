import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ruleset_notebook.ui.main_window import RulesetNotebookWindow


def test_window_runs_default_draft_through_shared_core(tmp_path):
    application = QApplication.instance() or QApplication([])
    window = RulesetNotebookWindow()
    window.cache_dir = tmp_path
    window.refresh_jobs()
    window.new_draft()

    window.run_draft()

    assert window.job_table.rowCount() == 1
    assert "result: 5" in window.results_edit.toPlainText()
    assert "{rule:add-3, x:2, y:3, position:root}" in window.results_edit.toPlainText()
    assert list(tmp_path.glob("*.rsjob"))
    window.close()
    assert application is not None


def test_export_then_open_round_trips_a_job(tmp_path):
    application = QApplication.instance() or QApplication([])
    window = RulesetNotebookWindow()
    window.cache_dir = tmp_path / "cache-a"
    window.cache_dir.mkdir(parents=True)
    window.refresh_jobs()
    window.new_draft()
    window.run_draft()
    job = next(iter(window.jobs.values()))
    window.refresh_jobs(select_job_id=job.job_id)
    exported = tmp_path / "shared.rsjob"

    window.export_selected_job(path=exported)
    assert exported.exists()

    window.cache_dir = tmp_path / "cache-b"
    window.cache_dir.mkdir(parents=True)
    window.refresh_jobs()
    window.open_job_file(path=exported)

    assert window.jobs[job.job_id] == job
    assert window.selected_job() == job
    assert window.results_edit.toPlainText() == job.results_text
    window.close()
    assert application is not None


def test_load_example_control_replaces_the_draft_and_runs_it(tmp_path):
    application = QApplication.instance() or QApplication([])
    window = RulesetNotebookWindow()
    window.cache_dir = tmp_path
    window.refresh_jobs()

    larger_index = window.example_combo.findData("larger")
    assert larger_index >= 0
    window.example_combo.setCurrentIndex(larger_index)
    window.load_example_action.trigger()

    assert "larger-left" in window.rules_edit.toPlainText()
    assert "larger(9, 4)" in window.inputs_edit.toPlainText()
    assert window.rules_edit.isReadOnly() is False
    assert "Choose the larger value" in window.statusBar().currentMessage()

    window.run_draft()

    assert "result: 9" in window.results_edit.toPlainText()
    assert "result: 7" in window.results_edit.toPlainText()
    window.close()
    assert application is not None


def test_runtime_error_is_cached_and_later_inputs_still_run(tmp_path):
    application = QApplication.instance() or QApplication([])
    window = RulesetNotebookWindow()
    window.cache_dir = tmp_path
    window.refresh_jobs()
    window.rules_edit.setPlainText("unwrap(x) => x")
    window.inputs_edit.setPlainText("div(1, 0)\nadd(2, 3)")

    window.run_draft()

    job = next(iter(window.jobs.values()))
    assert job.status == "runtime error"
    assert "error: div cannot divide by zero" in job.results_text
    assert "result: 5" in job.results_text
    assert job.input_count == 2
    window.close()
    assert application is not None
