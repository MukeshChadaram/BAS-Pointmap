"""Data objects passed between pipeline stages.

Keeping these as plain dataclasses (no behaviour) makes the data flow easy to
follow: each stage takes the previous stage's objects and returns new ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Result statuses. The thresholds that assign them live in classify.py.
AUTO = "auto"          # confident: evidence agrees, safe to load
FLAGGED = "flagged"    # accepted, but a human should spot-check it
REVIEW = "review"      # not trusted: goes to the review queue, never exported


@dataclass(frozen=True)
class Equipment:
    """A piece of equipment found inside a point name."""

    type: str   # key into rules/equipment_templates.yaml, e.g. "rtu"
    ref: str    # canonical id, e.g. "RTU-01"
    raw: str    # the exact text that matched, e.g. "Rtu #1" (kept for the audit trail)


@dataclass
class PointRecord:
    """One row of the vendor export after ingest (stage 1)."""

    row: int                      # 1-based data row in the source file
    point_name: str
    object_type: str | None       # canonical BACnet type: AI, AO, AV, BI, BO, BV, MSV...
    object_instance: str | None
    units: str | None             # canonical unit, e.g. "°F"
    units_raw: str | None         # exactly as exported, e.g. "degrees-fahrenheit"
    units_family: str | None      # temp, pressure, flow, percent, state...
    description: str | None
    device_instance: str | None
    ingest_flags: list[str] = field(default_factory=list)


@dataclass
class ParsedName:
    """A point name broken into parts (stage 2)."""

    raw: str
    segments: list[str]            # vendor path pieces, e.g. ["OFFICE-A", "NAE-01", "FC-2", "VMA-203", "ZN-SP"]
    tokens: list[str]              # point tokens, upper-case, equipment removed, e.g. ["ZN", "SP"]
    equipment: Equipment | None
    index: int | None              # trailing number not part of the equipment id (stage 2, sensor 3...)
    name_unit: str | None          # canonical unit written inside the name ("_DegF"), if any
    name_unit_family: str | None


@dataclass
class PointResult:
    """The classified point (stage 3), later annotated by QA (stage 4)."""

    site: str
    record: PointRecord
    parsed: ParsedName
    role_id: str | None            # best role, even for review rows ("best guess")
    role_name: str | None
    canonical_point: str | None    # e.g. "HTG-STG2-C"
    canonical_name: str | None     # e.g. "RTU-04.HTG-STG2-C"
    haystack_tags: list[str]
    brick_class: str | None
    stage: int | None
    confidence: float
    status: str                    # AUTO | FLAGGED | REVIEW
    evidence: list[str]            # human-readable reasoning, in order
    flags: list[str]               # "CODE: message" strings; QA reads the codes
    review_reason: str | None = None

    @property
    def equipment(self) -> Equipment | None:
        return self.parsed.equipment

    @property
    def accepted(self) -> bool:
        """Auto and flagged points are loaded; review points are not."""
        return self.status in (AUTO, FLAGGED)
