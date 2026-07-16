import dataclasses
import json

import pytest

from ruleset_notebook.jobs import JobImportConflictError, JobRecord, JobStore
from ruleset_notebook.language import LanguageSyntaxError


def make_job() -> JobRecord:
    return JobRecord(
        job_id="20260716010101-abc123",
        created_at="2026-07-16T01:01:01-05:00",
        status="normal form",
        rules_text="add(x, 0) => x",
        inputs_text="add(2, 0)",
        results_text="result: 2",
        rule_count=1,
        input_count=1,
        result_summary=(("add(2, 0)", "2"),),
    )


def test_job_record_round_trips_text():
    job = make_job()

    restored = JobRecord.from_text(job.to_text())

    assert restored == job


def test_job_store_writes_lists_and_deletes_records(tmp_path):
    store = JobStore(tmp_path)
    job = make_job()

    store.write(job)
    assert store.list_jobs() == {job.job_id: job}

    store.delete(job)
    assert store.list_jobs() == {}


def test_job_store_ignores_malformed_records_but_keeps_valid_ones(tmp_path):
    store = JobStore(tmp_path)
    valid = make_job()
    store.write(valid)
    (tmp_path / "broken.rsjob").write_text("not a job", encoding="utf-8")

    assert store.list_jobs() == {valid.job_id: valid}


def test_export_then_import_round_trips_complete_job_text(tmp_path):
    store = JobStore(tmp_path / "cache")
    other = JobStore(tmp_path / "other-cache")
    job = make_job()
    store.write(job)
    exported = tmp_path / "shared.rsjob"

    store.export_to(job, exported)
    imported = other.import_from(exported)

    assert imported == job
    assert exported.read_text(encoding="utf-8") == job.to_text()
    assert other.list_jobs() == {job.job_id: job}


def test_import_identical_duplicate_is_a_noop(tmp_path):
    store = JobStore(tmp_path / "cache")
    job = make_job()
    store.write(job)
    exported = tmp_path / "copy.rsjob"
    store.export_to(job, exported)

    assert store.import_from(exported) == job
    assert store.list_jobs() == {job.job_id: job}


def test_import_conflicting_duplicate_is_rejected_without_cache_change(tmp_path):
    store = JobStore(tmp_path / "cache")
    original = make_job()
    store.write(original)
    conflicting = dataclasses.replace(original, results_text="result: 99")
    source = tmp_path / "conflict.rsjob"
    source.write_text(conflicting.to_text(), encoding="utf-8")

    with pytest.raises(JobImportConflictError, match=original.job_id):
        store.import_from(source)

    assert store.list_jobs() == {original.job_id: original}


def test_import_malformed_file_raises_and_leaves_cache_untouched(tmp_path):
    store = JobStore(tmp_path / "cache")
    source = tmp_path / "broken.rsjob"
    source.write_text("not a job", encoding="utf-8")

    with pytest.raises(LanguageSyntaxError):
        store.import_from(source)

    assert store.list_jobs() == {}


def test_job_record_rejects_malformed_summary_pairs():
    payload = json.loads(make_job().to_text())
    payload["result_summary"] = "2"
    source = json.dumps(payload)

    try:
        JobRecord.from_text(source)
    except LanguageSyntaxError as error:
        assert "result_summary" in str(error)
    else:
        raise AssertionError("malformed summary should be rejected")
