import pytest

from pointmap.tokens import parse_name


@pytest.mark.parametrize("name, equip, tokens, index, unit", [
    ("#pine_paper/rtu_1/da_temp", "RTU-01", ["DA", "TEMP"], None, None),                # ALC path
    ("OFFICE-A:NAE-01/FC-2.VMA-203.ZN-SP", "VAV-203", ["ZN", "SP"], None, None),        # Metasys
    ("/Drivers/BacnetNetwork/RTU_4/points/HtgStg2", "RTU-04", ["HTG", "STG"], 2, None), # Niagara
    ("vav2-03_ZN_TEMP_DegF", "VAV-2-03", ["ZN", "TEMP"], None, "°F"),                   # hand-typed
    ("Rtu #1 Disch Air Tmp", "RTU-01", ["DISCH", "AIR", "TMP"], None, None),
    ("EF-2 S/S", "EF-02", ["SS"], None, None),
    ("RaCO2", None, ["RA", "CO2"], None, None),                                         # CO2 re-joined
])
def test_vendor_styles(rules, name, equip, tokens, index, unit):
    parsed = parse_name(name, rules)
    assert (parsed.equipment.ref if parsed.equipment else None) == equip
    assert parsed.tokens == tokens
    assert parsed.index == index
    assert parsed.name_unit == unit


def test_equipment_id_is_normalized_not_invented(rules):
    # VMA-203 must not become VAV-2-03: nothing in the name says floor 2.
    assert parse_name("FC-2.VMA-203.ZN-T", rules).equipment.ref == "VAV-203"


def test_slash_abbreviation_does_not_cross_path_separators(rules):
    # Regression: "points/SpaceTemp" contains "s/S", which was once rewritten to "SS"
    # and injected a phantom status token into every Niagara point starting with S.
    parsed = parse_name("/Drivers/BacnetNetwork/RTU_1/points/SpaceTemp", rules)
    assert parsed.tokens == ["SPACE", "TEMP"]
