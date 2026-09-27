"""qa_report.md: the deployment-readiness summary a controls lead reads first.

No timestamps: the same input and rules produce a byte-identical report, so a
re-run shows up in git diff only when something actually changed.
"""

from __future__ import annotations

from pathlib import Path

from .. import __version__
from ..models import AUTO, FLAGGED, REVIEW
from ..pipeline import RunResult


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "n/a"


def build_report(run: RunResult) -> str:
    qa, counts = run.qa, run.qa.counts
    total = counts["total"]
    ready = [e for e in qa.readiness if e.ready]
    out = [
        f"# Deployment readiness: {run.site}",
        "",
        f"Source `{run.source}` · rules v{run.rules.version} · pointmap {__version__}",
        "",
        "## Summary",
        "",
        "| Points | Auto-accepted | Flagged for spot-check | Review queue | Equipment ready |",
        "|---:|---:|---:|---:|---:|",
        f"| {total} | {counts[AUTO]} ({_pct(counts[AUTO], total)}) "
        f"| {counts[FLAGGED]} ({_pct(counts[FLAGGED], total)}) "
        f"| {counts[REVIEW]} ({_pct(counts[REVIEW], total)}) "
        f"| {len(ready)} of {len(qa.readiness)} |",
        "",
        "## Equipment readiness",
        "",
        "Required points come from `rules/equipment_templates.yaml`. "
        "`A|B` means either point satisfies the requirement.",
        "",
        "| Equipment | Type | Mapped | In review | Status | Missing required | Missing recommended |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for e in qa.readiness:
        out.append(
            f"| {e.equipment.ref} | {e.label} | {len(e.mapped_roles)} | {e.review_points} "
            f"| {'READY' if e.ready else 'BLOCKED'} "
            f"| {', '.join(e.missing_required) or '-'} | {', '.join(e.missing_recommended) or '-'} |"
        )
    if not qa.readiness:
        out.append("| - | - | - | - | - | - | - |")

    out += ["", "## Site-level points", ""]
    if qa.site_points:
        out += [f"- `{p.record.point_name}` -> {p.canonical_name} ({p.status})" for p in qa.site_points]
    else:
        out.append("None.")

    out += ["", "## Anomalies", "",
            "Metadata that doesn't add up. Each one is a question for the site, not a guess.", ""]
    if qa.anomalies:
        grouped: dict[str, list[str]] = {}
        for name, message in qa.anomalies:   # one line per point, first-seen order
            grouped.setdefault(name, []).append(message)
        out += [f"- `{name}`: " + "; ".join(messages) for name, messages in grouped.items()]
    else:
        out.append("None.")

    out += ["", "## Review queue by reason", ""]
    if qa.review_reasons:
        out += ["| Reason | Points |", "|---|---:|"]
        out += [f"| {reason} | {n} |" for reason, n in sorted(qa.review_reasons.items(), key=lambda x: (-x[1], x[0]))]
        out += ["", "Point-level detail: `review_queue.csv`."]
    else:
        out.append("Empty.")

    if qa.naming_notes:
        out += ["", "## Naming notes", "",
                "Informational flags on accepted points (see the `flags` column in `tagged_points.csv`).", ""]
        out += [f"- {code}: {n}" for code, n in sorted(qa.naming_notes.items())]
    return "\n".join(out) + "\n"


def write_report(run: RunResult, out_dir: Path) -> Path:
    path = out_dir / "qa_report.md"
    path.write_text(build_report(run), encoding="utf-8")
    return path
