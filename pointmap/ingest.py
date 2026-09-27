"""Stage 1: read a vendor point export and normalize its metadata.

Real exports are inconsistent before they are messy: column headers differ by
vendor, object types are spelled five ways, units are free text, and files
arrive in Latin-1 as often as UTF-8. This stage absorbs all of that so later
stages only ever see canonical values.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .models import PointRecord
from .rules import RuleSet, object_type_key, unit_keys

# Accepted header spellings for each canonical column (compared after
# lower-casing and turning spaces/hyphens into underscores).
COLUMN_ALIASES = {
    "point_name": ["point_name", "name", "object_name", "point", "pointname", "reference",
                   "item_reference", "point_path", "slot_path"],
    "object_type": ["object_type", "type", "bacnet_type", "obj_type", "objecttype"],
    "object_instance": ["object_instance", "instance", "obj_instance", "objectinstance"],
    "units": ["units", "unit", "engineering_units", "eng_units"],
    "description": ["description", "desc", "point_description", "display_name"],
    "device_instance": ["device_instance", "device", "device_id", "deviceinstance"],
    "site": ["site", "site_name"],
}


class IngestError(ValueError):
    """The file cannot be read as a point export."""


def read_export(path: str | Path) -> pd.DataFrame:
    """Read the CSV as text only, trying UTF-8 first, then Latin-1.

    dtype=str and keep_default_na=False stop pandas from "helpfully" turning an
    object instance of 007 into 7, or a units value of "NA" into a null.
    """
    path = Path(path)
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 decodes any byte sequence
        raise IngestError(f"could not decode {path}")

    frame.columns = [_canonical_column(c) for c in frame.columns]
    if "point_name" not in frame.columns:
        raise IngestError(
            f"{path.name}: no point name column (looked for: {', '.join(COLUMN_ALIASES['point_name'])})"
        )
    return frame


def to_records(frame: pd.DataFrame, rules: RuleSet) -> list[PointRecord]:
    """Turn each row into a PointRecord with canonical object type and units."""
    records = []
    for position, row in enumerate(frame.to_dict("records"), start=1):
        flags: list[str] = []

        object_type, embedded_instance = _object_type(row.get("object_type", ""), rules)
        if row.get("object_type", "").strip() and object_type is None:
            flags.append(f"TYPE_UNKNOWN: object type {row['object_type']!r} not recognized")

        units_raw = row.get("units", "").strip() or None
        unit = None
        if units_raw and not any(k in rules.none_units for k in unit_keys(units_raw)):
            unit = _lookup_unit(units_raw, rules)
            if unit is None:
                flags.append(f"UNITS_UNKNOWN: units {units_raw!r} not recognized")

        records.append(PointRecord(
            row=position,
            point_name=row["point_name"].strip(),
            object_type=object_type,
            object_instance=(row.get("object_instance", "").strip() or embedded_instance),
            units=unit.canonical if unit else None,
            units_raw=units_raw,
            units_family=unit.family if unit else None,
            description=row.get("description", "").strip() or None,
            device_instance=row.get("device_instance", "").strip() or None,
            ingest_flags=flags,
        ))
    return records


def site_from_frame(frame: pd.DataFrame) -> str | None:
    """If the export carries a single site value, use it."""
    if "site" not in frame.columns:
        return None
    values = {v.strip() for v in frame["site"] if v.strip()}
    return values.pop() if len(values) == 1 else None


# ---------------------------------------------------------------------------
def _canonical_column(header: str) -> str:
    key = re.sub(r"[\s\-]+", "_", str(header).strip().lower())
    for canonical, aliases in COLUMN_ALIASES.items():
        if key in aliases:
            return canonical
    return key


def _object_type(raw: str, rules: RuleSet) -> tuple[str | None, str | None]:
    """'AI', 'analog-input', 'analogInput' -> 'AI'.  'AI:3' / 'AI3' -> ('AI', '3')."""
    text = str(raw).strip()
    if not text:
        return None, None
    match = re.match(r"^\s*([A-Za-z _\-]+?)[\s:_\-]*(\d+)?\s*$", text)
    letters = object_type_key(match.group(1) if match else text)
    instance = match.group(2) if match else None
    return rules.object_types.get(letters), instance


def _lookup_unit(raw: str, rules: RuleSet):
    for key in unit_keys(raw):
        if key in rules.units:
            return rules.units[key]
    return None
