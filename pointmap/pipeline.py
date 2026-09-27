"""Wire the stages together: ingest -> tokens -> classify -> qa.

This is the function the CLI and the tests call. It returns plain objects;
writing files is the export stage's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .classify import classify_point
from .ingest import read_export, site_from_frame, to_records
from .models import PointResult
from .qa import QAReport, run_qa
from .rules import RuleSet, load_rules
from .tokens import parse_name


@dataclass
class RunResult:
    site: str
    source: str
    rules: RuleSet
    results: list[PointResult]
    qa: QAReport


def run(csv_path: str | Path, site: str | None = None, rules: RuleSet | None = None) -> RunResult:
    rules = rules or load_rules()

    # Stage 1: ingest.
    frame = read_export(csv_path)
    site = site or site_from_frame(frame)
    if not site:
        raise ValueError("no site given: pass --site or include a single-valued 'site' column")
    records = to_records(frame, rules)

    # Stages 2 and 3, one point at a time. Input order is preserved end to end.
    results = [classify_point(site, record, parse_name(record.point_name, rules), rules)
               for record in records]

    # Stage 4: checks that need every point at once.
    qa = run_qa(site, results, rules)
    return RunResult(site=site, source=Path(csv_path).name, rules=rules, results=results, qa=qa)
