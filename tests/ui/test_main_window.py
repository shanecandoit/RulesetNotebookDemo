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
    assert "x=2, y=3" in window.results_edit.toPlainText()
    assert list(tmp_path.glob("*.rsjob"))
    window.close()
    assert application is not None
