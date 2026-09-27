"""brick.ttl: the same model as a Brick Schema graph in Turtle.

    bldg:RTU-01          a brick:Rooftop_Unit ;  brick:hasLocation bldg:PINE-PAPER .
    bldg:RTU-01.DA-T     a brick:Supply_Air_Temperature_Sensor ;
                         brick:isPointOf bldg:RTU-01 ;  brick:hasUnit unit:DEG_C .

Written as plain text (no RDF library needed at runtime); the test suite parses
it with rdflib to prove it is valid Turtle. Only accepted points are exported.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import PointResult
from ..rules import RuleSet

PREFIXES = """@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix bldg: <urn:pointmap:{site}#> .
"""


def _local(name: str) -> str:
    """A safe Turtle local name: letters, digits, _ - . (never ending in '.')."""
    return re.sub(r"[^A-Za-z0-9_\-.]", "_", name).rstrip(".") or "_"


def _literal(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_turtle(site: str, results: list[PointResult], rules: RuleSet) -> str:
    accepted = [r for r in results if r.accepted]
    site_node = f"bldg:{_local(site)}"
    lines = [PREFIXES.format(site=_local(site)),
             f"{site_node} a brick:Building ;\n    rdfs:label {_literal(site)} .\n"]

    written = set()
    for r in accepted:
        eq = r.equipment
        if eq is None or (eq.type, eq.ref) in written:
            continue
        written.add((eq.type, eq.ref))
        lines.append(f"bldg:{_local(eq.ref)} a brick:{rules.equipment[eq.type].brick} ;\n"
                     f"    rdfs:label {_literal(eq.ref)} ;\n"
                     f"    brick:hasLocation {site_node} .\n")

    used = set()
    for r in accepted:
        node = _local(r.canonical_name)
        suffix = 2
        while node in used:  # duplicates were flagged by QA; keep nodes distinct
            node = _local(f"{r.canonical_name}_{suffix}")
            suffix += 1
        used.add(node)
        owner = f"bldg:{_local(r.equipment.ref)}" if r.equipment else site_node
        body = [f"bldg:{node} a brick:{r.brick_class}",
                f"    rdfs:label {_literal(r.record.point_name)}",
                f"    brick:isPointOf {owner}"]
        qudt = _qudt(r, rules)
        if qudt:
            body.append(f"    brick:hasUnit unit:{qudt}")
        lines.append(" ;\n".join(body) + " .\n")
    return "\n".join(lines)


def _qudt(r: PointResult, rules: RuleSet) -> str | None:
    canonical = r.record.units or r.parsed.name_unit
    unit = next((u for u in rules.units.values() if u.canonical == canonical), None) if canonical else None
    return unit.qudt if unit and rules.role(r.role_id).kind == "Number" else None


def write_brick(site: str, results: list[PointResult], rules: RuleSet, out_dir: Path) -> Path:
    path = out_dir / "brick.ttl"
    path.write_text(build_turtle(site, results, rules), encoding="utf-8")
    return path
