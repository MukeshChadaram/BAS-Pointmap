"""tagged_points.csv (every point) and review_queue.csv (points a person must decide)."""

from __future__ import annotations

import csv
from pathlib import Path

from ..models import REVIEW, PointResult

TAGGED_COLUMNS = [
    "row", "site", "original_name", "device_instance", "object_type", "object_instance",
    "units", "equip_type", "equip_ref", "canonical_name", "canonical_point", "role_id",
    "haystack_tags", "brick_class", "confidence", "status", "flags", "review_reason", "evidence",
]

REVIEW_COLUMNS = [
    "row", "original_name", "device_instance", "object_type", "units", "equip_ref",
    "best_guess", "confidence", "review_reason", "flags",
]


def point_row(r: PointResult) -> dict:
    return {
        "row": r.record.row,
        "site": r.site,
        "original_name": r.record.point_name,
        "device_instance": r.record.device_instance or "",
        "object_type": r.record.object_type or "",
        "object_instance": r.record.object_instance or "",
        "units": r.record.units or r.parsed.name_unit or "",
        "equip_type": r.equipment.type if r.equipment else "",
        "equip_ref": r.equipment.ref if r.equipment else "",
        "canonical_name": r.canonical_name or "",
        "canonical_point": r.canonical_point or "",
        "role_id": r.role_id or "",
        "haystack_tags": " ".join(r.haystack_tags),
        "brick_class": r.brick_class or "",
        "confidence": f"{r.confidence:.2f}",
        "status": r.status,
        "flags": " | ".join(r.flags),
        "review_reason": r.review_reason or "",
        "evidence": " | ".join(r.evidence),
    }


def _write(path: Path, columns: list[str], rows: list[dict]) -> Path:
    # stdlib csv with fixed line endings: output is byte-identical across
    # platforms and library versions, which the reproducibility check relies on.
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_tables(results: list[PointResult], out_dir: Path) -> tuple[Path, Path]:
    rows = [point_row(r) for r in results]
    queue = [
        {**row, "best_guess": row["role_id"]}
        for row, result in zip(rows, results) if result.status == REVIEW
    ]
    return (_write(out_dir / "tagged_points.csv", TAGGED_COLUMNS, rows),
            _write(out_dir / "review_queue.csv", REVIEW_COLUMNS, queue))
