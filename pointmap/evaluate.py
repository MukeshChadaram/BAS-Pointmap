"""Score a mapping run against a hand-labelled answer key.

Answer key format (one CSV per site, in data/ground_truth/). Scoring uses:

    point_name, device_instance, expected_equip, expected_point

    expected_equip   canonical equipment id ("RTU-01"), blank for site-level points
    expected_point   canonical point ("DA-T", "HTG-STG2-C"), or NONE when the
                     correct behaviour is to refuse the point (spares, junk,
                     out-of-scope points, orphans, points whose name and
                     metadata describe different physical things)

The keys also carry expected_role, expected_canonical_name, expected_outcome
(map | refuse) and a note; tests check those agree with the scoring columns.
The key records what each point IS. It deliberately does not record auto vs
flagged: that is the tool's confidence, and labelling it would grade the tool
against its own output.

Rows are matched on point_name + device_instance, because the same name can
legitimately exist on two controllers.

The metrics answer the questions that matter operationally:

    auto precision      when the tool says "safe to load", how often is it right?
    silent errors       auto-accepted AND wrong: the number that must be ~zero
    correct refusals    of the points that should be refused, how many were
    coverage            share of points accepted with no human involvement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .models import AUTO, FLAGGED, REVIEW

REFUSE = "NONE"


@dataclass
class Evaluation:
    site: str = ""
    total: int = 0
    auto: int = 0
    auto_correct: int = 0
    accepted: int = 0
    accepted_correct: int = 0
    review: int = 0
    should_refuse: int = 0
    refused_correctly: int = 0
    missed: int = 0                                  # mappable, but sent to review
    silent_errors: list = field(default_factory=list)
    accepted_errors: list = field(default_factory=list)
    unmatched: list = field(default_factory=list)    # tagged rows with no answer-key entry

    def __add__(self, other: "Evaluation") -> "Evaluation":
        """Combine per-site evaluations into a benchmark total."""
        combined = Evaluation(site="All sites")
        for name in ("total", "auto", "auto_correct", "accepted", "accepted_correct",
                     "review", "should_refuse", "refused_correctly", "missed"):
            setattr(combined, name, getattr(self, name) + getattr(other, name))
        for name in ("silent_errors", "accepted_errors", "unmatched"):
            setattr(combined, name, getattr(self, name) + getattr(other, name))
        return combined

    def as_markdown(self) -> str:
        lines = [
            "| Metric | Result |",
            "|---|---:|",
            f"| Points evaluated | {self.total} |",
            f"| Auto-accepted precision | {ratio(self.auto_correct, self.auto)} |",
            f"| Accepted precision (auto + flagged) | {ratio(self.accepted_correct, self.accepted)} |",
            f"| Coverage (auto-accepted share) | {ratio(self.auto, self.total)} |",
            f"| Review-queue rate | {ratio(self.review, self.total)} |",
            f"| Correct refusals | {ratio(self.refused_correctly, self.should_refuse)} |",
            f"| Silent errors (auto-accepted and wrong) | {len(self.silent_errors)} |",
        ]
        if self.silent_errors:
            lines += ["", "Silent errors:", ""]
            lines += [f"- `{name}`: got {got}, expected {want}" for name, got, want in self.silent_errors]
        if self.accepted_errors:
            flagged = [x for x in self.accepted_errors if x not in self.silent_errors]
            if flagged:
                lines += ["", "Wrong but flagged for spot-check (caught by the flagged tier):", ""]
                lines += [f"- `{name}`: got {got}, expected {want}" for name, got, want in flagged]
        return "\n".join(lines)


def ratio(a: int, b: int) -> str:
    return f"{a / b:.1%} ({a}/{b})" if b else "n/a"


def per_site_markdown(evaluations: list[Evaluation]) -> str:
    """One row per site, for spotting where the rules are weakest."""
    lines = ["| Site | Points | Auto precision | Silent errors | Coverage | Review rate | Correct refusals |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for ev in evaluations:
        lines.append(
            f"| {ev.site} | {ev.total} | {_pct(ev.auto_correct, ev.auto)} | {len(ev.silent_errors)} "
            f"| {_pct(ev.auto, ev.total)} | {_pct(ev.review, ev.total)} "
            f"| {ev.refused_correctly}/{ev.should_refuse} |")
    return "\n".join(lines)


def _pct(a: int, b: int) -> str:
    return f"{a / b:.1%}" if b else "n/a"


def evaluate(tagged_csv: str | Path, truth_csv: str | Path) -> Evaluation:
    tagged = pd.read_csv(tagged_csv, dtype=str, keep_default_na=False)
    truth = pd.read_csv(truth_csv, dtype=str, keep_default_na=False)
    if "device_instance" not in truth.columns:
        truth["device_instance"] = ""

    key = {
        (row["point_name"].strip(), row["device_instance"].strip()): row
        for row in truth.to_dict("records")
    }

    sites = sorted({s for s in tagged.get("site", []) if s})
    result = Evaluation(site=", ".join(sites) or Path(tagged_csv).parent.name)
    for row in tagged.to_dict("records"):
        expected = key.get((row["original_name"].strip(), row["device_instance"].strip()))
        if expected is None:
            result.unmatched.append(row["original_name"])
            continue
        result.total += 1
        status = row["status"]
        want_point = expected["expected_point"].strip()
        want_equip = expected["expected_equip"].strip()
        correct = (row["canonical_point"] == want_point and row["equip_ref"] == want_equip)
        got = f"{row['equip_ref'] or '(site)'}.{row['canonical_point'] or '?'}"
        want = REFUSE if want_point == REFUSE else f"{want_equip or '(site)'}.{want_point}"

        if want_point == REFUSE:
            result.should_refuse += 1
            if status == REVIEW:
                result.refused_correctly += 1

        if status == REVIEW:
            result.review += 1
            if want_point != REFUSE:
                result.missed += 1
            continue

        result.accepted += 1
        result.accepted_correct += correct
        if not correct:
            result.accepted_errors.append((row["original_name"], got, want))
        if status == AUTO:
            result.auto += 1
            result.auto_correct += correct
            if not correct:
                result.silent_errors.append((row["original_name"], got, want))
        elif status != FLAGGED:  # pragma: no cover - defensive
            raise ValueError(f"unexpected status {status!r}")
    return result
