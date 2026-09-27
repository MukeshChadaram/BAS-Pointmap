"""The benchmark as a regression suite: answer keys stay honest, results don't regress."""

import csv
from pathlib import Path

import pytest

from pointmap.evaluate import evaluate
from pointmap.export.tables import write_tables
from pointmap.ingest import read_export
from pointmap.pipeline import run

ROOT = Path(__file__).resolve().parent.parent
SITES = {"pine_paper_alc": "PINE-PAPER", "office_a_metasys": "OFFICE-A",
         "store_01_niagara": "STORE-01", "legacy_mix_chaos": "LEGACY-MIX"}


def _key(stem):
    with open(ROOT / "data/ground_truth" / f"{stem}.csv", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("stem", SITES)
def test_every_raw_point_has_an_answer(stem):
    raw = read_export(ROOT / "data/raw" / f"{stem}.csv")
    raw_keys = {(r["point_name"].strip(), r.get("device_instance", "").strip()) for r in raw.to_dict("records")}
    key_keys = {(r["point_name"], r["device_instance"]) for r in _key(stem)}
    assert raw_keys == key_keys


@pytest.mark.parametrize("stem", SITES)
def test_answer_key_columns_agree(stem, rules):
    role_ids = {r.id for r in rules.roles}
    for row in _key(stem):
        point = row["expected_point"]
        if point == "NONE":
            assert row["expected_outcome"] == "refuse" and not row["expected_canonical_name"]
            assert row["note"], "every refusal must say why"
        else:
            assert row["expected_outcome"] == "map"
            assert row["expected_role"] in role_ids
            owner = row["expected_equip"] or SITES[stem]
            assert row["expected_canonical_name"] == f"{owner}.{point}"


@pytest.fixture(scope="module")
def benchmark(rules, tmp_path_factory):
    results = []
    for stem, site in SITES.items():
        out = tmp_path_factory.mktemp(stem)
        write_tables(run(ROOT / "data/raw" / f"{stem}.csv", site=site, rules=rules).results, out)
        results.append(evaluate(out / "tagged_points.csv", ROOT / "data/ground_truth" / f"{stem}.csv"))
    total = results[0]
    for other in results[1:]:
        total = total + other
    return total


def test_no_silent_errors(benchmark):
    assert benchmark.silent_errors == []


def test_accepted_precision_does_not_regress(benchmark):
    assert benchmark.accepted_correct / benchmark.accepted >= 0.97


def test_every_point_was_scored(benchmark):
    assert benchmark.total == 243 and not benchmark.unmatched
