"""Stage 4: commissioning checks on the classified points.

Mapping individual points is not the goal. The goal is a building that is
ready to deploy. This stage answers the questions a controls lead asks before
signing off a site:

  * Does every piece of equipment have the points the platform needs?
  * Are two points claiming to be the same thing?
  * Which points have metadata that doesn't add up?
"""

from __future__ import annotations

import fnmatch
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .models import AUTO, FLAGGED, REVIEW, Equipment, PointResult
from .rules import RuleSet

# Flag codes surfaced as anomalies in the report (the rest are naming notes).
ANOMALY_CODES = (
    "STATUS_ON_ANALOG", "UNITS_CONFLICT", "TYPE_MISMATCH", "UNITS_UNKNOWN",
    "TYPE_UNKNOWN", "DESC_DISAGREES", "DUPLICATE", "NO_EQUIPMENT", "UNUSUAL_EQUIPMENT",
)


@dataclass
class EquipmentReadiness:
    equipment: Equipment
    label: str
    mapped_roles: list          # role ids of accepted points on this equipment
    review_points: int          # points on this equipment stuck in the review queue
    missing_required: list      # human-readable, e.g. "ZN-T-SP|ZN-T-CLG-SP"
    missing_recommended: list

    @property
    def ready(self) -> bool:
        return not self.missing_required


@dataclass
class QAReport:
    site: str
    counts: dict                                  # auto / flagged / review / total
    readiness: list = field(default_factory=list)
    site_points: list = field(default_factory=list)  # accepted points with no equipment
    anomalies: list = field(default_factory=list)    # (point name, message)
    review_reasons: Counter = field(default_factory=Counter)
    naming_notes: Counter = field(default_factory=Counter)


def run_qa(site: str, results: list[PointResult], rules: RuleSet) -> QAReport:
    _mark_duplicates(results)
    counts = Counter(r.status for r in results)
    report = QAReport(
        site=site,
        counts={"total": len(results), AUTO: counts[AUTO], FLAGGED: counts[FLAGGED], REVIEW: counts[REVIEW]},
    )

    # Site-level points (e.g. outside air temp) satisfy requirements for every unit on site.
    site_roles = {r.role_id for r in results if r.accepted and r.equipment is None}
    report.site_points = [r for r in results if r.accepted and r.equipment is None]

    # Group by equipment id, keeping first-seen order so the report is stable.
    # (Keyed on type + ref, not the raw text: "RTU_1" and "rtu 1" are one unit.)
    by_equipment: dict[tuple, list[PointResult]] = defaultdict(list)
    for result in results:
        if result.equipment is not None:
            by_equipment[(result.equipment.type, result.equipment.ref)].append(result)

    for points in by_equipment.values():
        equipment = points[0].equipment
        template = rules.equipment[equipment.type]
        mapped = [p.role_id for p in points if p.accepted]
        report.readiness.append(EquipmentReadiness(
            equipment=equipment,
            label=template.label,
            mapped_roles=mapped,
            review_points=sum(1 for p in points if p.status == REVIEW),
            missing_required=_missing(template.required, mapped, site_roles, rules),
            missing_recommended=_missing(template.recommended, mapped, site_roles, rules),
        ))

    for result in results:
        for flag in result.flags:
            code, _, message = flag.partition(": ")
            if code in ANOMALY_CODES:
                report.anomalies.append((result.record.point_name, f"{code}: {message}"))
            else:
                report.naming_notes[code] += 1
        if result.status == REVIEW:
            report.review_reasons[_reason_bucket(result.review_reason)] += 1

    return report


def _missing(groups, mapped_roles, site_roles, rules: RuleSet) -> list[str]:
    """Which requirement groups have no satisfying point.

    A group is a tuple of alternatives ("ZN-T", "RA-T"); globs like "HTG-STG-*"
    are allowed. Site-level roles can be satisfied by a point at the site.
    """
    site_level = {r.id for r in rules.roles if r.site_level}
    missing = []
    for group in groups:
        satisfied = any(
            fnmatch.filter(mapped_roles, pattern)
            or (pattern in site_level and pattern in site_roles)
            for pattern in group
        )
        if not satisfied:
            missing.append("|".join(group))
    return missing


def _mark_duplicates(results: list[PointResult]) -> None:
    """Two accepted points with the same canonical name can't both be right.

    Both are downgraded from auto to flagged so a person picks the real one.
    """
    by_name = defaultdict(list)
    for result in results:
        if result.accepted:
            by_name[result.canonical_name].append(result)
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        rows = ", ".join(str(r.record.row) for r in group)
        for result in group:
            result.flags.append(f"DUPLICATE: {name} is claimed by rows {rows}")
            if result.status == AUTO:
                result.status = FLAGGED
                result.evidence.append("downgraded auto -> flagged: duplicate canonical name")


def _reason_bucket(reason: str | None) -> str:
    """Group review reasons into a short table (the detail stays per point)."""
    if not reason:
        return "unspecified"
    if reason.startswith("low confidence"):
        return "low confidence"
    if reason.startswith("best guess"):
        return "metadata disagrees with the name"
    if reason.startswith("status point wired as an analog"):
        return "status wired as analog input"
    if reason.startswith("no point role matches"):
        return "no matching point role"
    if reason.startswith("no equipment in the name"):
        return "cannot attach to equipment"
    return reason
