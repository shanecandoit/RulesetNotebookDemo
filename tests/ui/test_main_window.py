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
