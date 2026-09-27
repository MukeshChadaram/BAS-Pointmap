import json
from pathlib import Path

import pytest
import rdflib

from pointmap.export.brick import build_turtle
from pointmap.export.haystack import build_grid
from pointmap.export.report import build_report
from pointmap.export.tables import write_tables
from pointmap.pipeline import run

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
BRICK = rdflib.Namespace("https://brickschema.org/schema/Brick#")


@pytest.fixture(scope="module")
def office(rules):
    return run(DATA / "office_a_metasys.csv", site="OFFICE-A", rules=rules)


def test_brick_turtle_parses_and_every_point_has_an_owner(office, rules):
    graph = rdflib.Graph().parse(data=build_turtle("OFFICE-A", office.results, rules), format="turtle")
    subjects = set(graph.subjects())
    owners = set(graph.objects(None, BRICK.isPointOf))
    assert owners and owners <= subjects


def test_haystack_refs_resolve_and_review_points_are_excluded(office, rules):
    grid = build_grid("OFFICE-A", office.results, rules)
    ids = {row["id"]["val"] for row in grid["rows"]}
    for row in grid["rows"]:
        for key in ("siteRef", "equipRef"):
            if key in row:
                assert row[key]["val"] in ids
    exported = {row.get("pointmapSource") for row in grid["rows"]}
    assert not any(r.record.point_name in exported for r in office.results if not r.accepted)
    json.dumps(grid)  # serializable


def test_outputs_are_byte_identical_across_runs(rules, tmp_path):
    first = run(DATA / "store_01_niagara.csv", site="STORE-01", rules=rules)
    second = run(DATA / "store_01_niagara.csv", site="STORE-01", rules=rules)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    write_tables(first.results, tmp_path / "a")
    write_tables(second.results, tmp_path / "b")
    for name in ("tagged_points.csv", "review_queue.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert build_report(first) == build_report(second)
