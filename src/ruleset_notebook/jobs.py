"""Immutable job records and the plain-text job cache."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .language import LanguageSyntaxError


@dataclass(frozen=True)
class JobRecord:
    """The complete source/result snapshot of one evaluation attempt."""

    job_id: str
    created_at: str
    status: str
    rules_text: str
    inputs_text: str
    results_text: str
    rule_count: int
    input_count: int
    result_summary: tuple[tuple[str, str], ...]

    @classmethod
    def new_id(cls) -> str:
        return f"{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"

    @property
    def filename(self) -> str:
        return f"{self.job_id}.rsjob"

    def to_text(self) -> str:
        payload = {
            "format": "ruleset-notebook-job",
            "version": 1,
            "job_id": self.job_id,
            "created_at": self.created_at,
            "status": self.status,
            "rule_count": self.rule_count,
            "input_count": self.input_count,
            "result_summary": [list(pair) for pair in self.result_summary],
            "rules_text": self.rules_text,
            "inputs_text": self.inputs_text,
            "results_text": self.results_text,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_text(cls, source: str) -> JobRecord:
        try:
            payload = json.loads(source)
        except json.JSONDecodeError as error:
            raise LanguageSyntaxError("job file is not valid JSON") from error
        if not isinstance(payload, dict):
            raise LanguageSyntaxError("job file must contain a JSON object")
        if payload.get("format") != "ruleset-notebook-job":
            raise LanguageSyntaxError("unsupported job file format")
        if payload.get("version") != 1:
            raise LanguageSyntaxError("unsupported job file version")
        required = {
            "job_id",
            "created_at",
            "status",
            "rule_count",
            "input_count",
            "result_summary",
            "rules_text",
            "inputs_text",
            "results_text",
        }
        if missing := required - payload.keys():
            raise LanguageSyntaxError(
                f"job file is missing: {', '.join(sorted(missing))}"
            )
        try:
            rule_count = int(payload["rule_count"])
            input_count = int(payload["input_count"])
        except (TypeError, ValueError) as error:
            raise LanguageSyntaxError("job counts must be integers") from error
        text_fields = ("job_id", "created_at", "status")
        if any(not isinstance(payload[field], str) for field in text_fields):
            raise LanguageSyntaxError("job metadata fields must be strings")
        raw_summary = payload["result_summary"]
        if not isinstance(raw_summary, list):
            raise LanguageSyntaxError("result_summary must be a list of pairs")
        summary: list[tuple[str, str]] = []
        for pair in raw_summary:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(value, str) for value in pair)
            ):
                raise LanguageSyntaxError(
                    "result_summary entries must be [input, output] pairs"
                )
            summary.append((pair[0], pair[1]))
        source_fields = ("rules_text", "inputs_text", "results_text")
        if any(not isinstance(payload[field], str) for field in source_fields):
            raise LanguageSyntaxError("job text fields must be strings")
        return cls(
            job_id=payload["job_id"],
            created_at=payload["created_at"],
            status=payload["status"],
            rules_text=payload["rules_text"],
            inputs_text=payload["inputs_text"],
            results_text=payload["results_text"],
            rule_count=rule_count,
            input_count=input_count,
            result_summary=tuple(summary),
        )


def format_result_summary(summary: tuple[tuple[str, str], ...]) -> str:
    """Render summary pairs compactly for the Jobs table."""

    return "; ".join(
        f"{input_term}:{output_term}" for input_term, output_term in summary
    )


class JobStore:
    """Filesystem service for immutable ``.rsjob`` records."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def list_jobs(self) -> dict[str, JobRecord]:
        jobs: dict[str, JobRecord] = {}
        for path in self.cache_dir.glob("*.rsjob"):
            try:
                job = JobRecord.from_text(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            jobs[job.job_id] = job
        return jobs

    def write(self, job: JobRecord) -> None:
        target = self.cache_dir / job.filename
        temporary = target.with_suffix(".tmp")
        temporary.write_text(job.to_text(), encoding="utf-8")
        temporary.replace(target)

    def delete(self, job: JobRecord) -> None:
        (self.cache_dir / job.filename).unlink()
