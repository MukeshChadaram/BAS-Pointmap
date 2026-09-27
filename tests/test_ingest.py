from pathlib import Path

import pandas as pd

from pointmap.ingest import read_export, to_records

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"


def test_latin1_export_is_read(rules):
    records = to_records(read_export(DATA / "legacy_mix_chaos.csv"), rules)
    assert any(r.units == "°F" for r in records)


def test_vendor_headers_are_recognized():
    for name in ("pine_paper_alc", "office_a_metasys", "store_01_niagara", "legacy_mix_chaos"):
        assert "point_name" in read_export(DATA / f"{name}.csv").columns


def test_object_type_and_units_spellings_normalize(rules):
    frame = pd.DataFrame([
        {"point_name": "a", "object_type": "analog-input", "units": "degrees-fahrenheit"},
        {"point_name": "b", "object_type": "analogInput", "units": "in W.C."},
        {"point_name": "c", "object_type": "AI:3", "units": "no-units"},
        {"point_name": "d", "object_type": "Binary Output", "units": "furlongs"},
    ])
    a, b, c, d = to_records(frame, rules)
    assert (a.object_type, a.units) == ("AI", "°F")
    assert (b.object_type, b.units) == ("AI", "inH₂O")
    assert (c.object_type, c.object_instance, c.units) == ("AI", "3", None)
    assert d.object_type == "BO" and any(f.startswith("UNITS_UNKNOWN") for f in d.ingest_flags)
