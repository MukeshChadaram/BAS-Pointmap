"""haystack.json: site -> equipment -> points, as a Haystack JSON (Hayson) grid.

Only accepted points (auto + flagged) are exported. Review-queue points are
deliberately left out: an untrusted point should never reach a live model.

Every tag is a standard Haystack 4 def except one: `pointmapSource` carries the
original vendor name for traceability. Haystack permits custom tags; strip it
if a target platform rejects them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import PointResult
from ..rules import RuleSet

MARKER = {"_kind": "marker"}


def _ref(value: str, dis: str) -> dict:
    # Haystack ref ids allow letters, digits and _ : - . ~ only.
    return {"_kind": "ref", "val": re.sub(r"[^A-Za-z0-9_:\-.~]", "_", value), "dis": dis}


def build_grid(site: str, results: list[PointResult], rules: RuleSet) -> dict:
    accepted = [r for r in results if r.accepted]
    site_ref = _ref(site, site)
    rows = [{"id": site_ref, "dis": site, "site": MARKER}]

    # One entity per equipment, in first-seen order.
    equip_refs, seen_ids = {}, set()
    for r in accepted:
        eq = r.equipment
        if eq is None or (eq.type, eq.ref) in equip_refs:
            continue
        template = rules.equipment[eq.type]
        ref = _ref(f"{site}.{eq.ref}", eq.ref)
        equip_refs[(eq.type, eq.ref)] = ref
        row = {"id": ref, "dis": eq.ref, "siteRef": site_ref}
        row.update({tag: MARKER for tag in template.haystack})
        rows.append(row)

    for r in accepted:
        role = rules.role(r.role_id)
        point_id = f"{site}.{r.canonical_name}"
        # Duplicates were flagged by QA; keep ids unique so the grid stays valid.
        suffix = 2
        while point_id in seen_ids:
            point_id = f"{site}.{r.canonical_name}~{suffix}"
            suffix += 1
        seen_ids.add(point_id)

        row = {"id": _ref(point_id, r.canonical_name), "dis": r.canonical_name,
               "pointmapSource": r.record.point_name, "kind": role.kind, "siteRef": site_ref}
        if r.equipment is not None:
            row["equipRef"] = equip_refs[(r.equipment.type, r.equipment.ref)]
        row.update({tag: MARKER for tag in r.haystack_tags})
        if r.stage is not None:
            row["stage"] = r.stage
        unit = _haystack_unit(r, rules)
        if unit and role.kind == "Number":
            row["unit"] = unit
        rows.append(row)

    # Columns in first-seen order: deterministic and readable.
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return {"_kind": "grid", "meta": {"ver": "3.0"},
            "cols": [{"name": c} for c in columns], "rows": rows}


def _haystack_unit(r: PointResult, rules: RuleSet) -> str | None:
    canonical = r.record.units or r.parsed.name_unit
    if not canonical:
        return None
    unit = next((u for u in rules.units.values() if u.canonical == canonical), None)
    return unit.haystack if unit else None


def write_haystack(site: str, results: list[PointResult], rules: RuleSet, out_dir: Path) -> Path:
    path = out_dir / "haystack.json"
    path.write_text(json.dumps(build_grid(site, results, rules), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path
