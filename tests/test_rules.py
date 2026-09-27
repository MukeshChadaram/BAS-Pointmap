import shutil

import pytest
import yaml

from pointmap.rules import DEFAULT_RULES_DIR, RuleError, load_rules


def test_rules_load_and_validate(rules):
    assert len(rules.roles) == 33
    assert len(rules.equipment) == 9
    assert rules.role("HTG-STG-C").canonical.format(n=2) == "HTG-STG2-C"


def _broken_copy(tmp_path, filename, mutate):
    target = tmp_path / "rules"
    shutil.copytree(DEFAULT_RULES_DIR, target)
    path = target / filename
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return target


def test_unknown_dimension_fails_at_load(tmp_path):
    rules_dir = _broken_copy(tmp_path, "abbreviations.yaml",
                             lambda d: d["tokens"].update({"XYZ": {"colour": "blue"}}))
    with pytest.raises(RuleError, match="unknown dimension"):
        load_rules(rules_dir)


def test_template_entry_matching_no_role_fails_at_load(tmp_path):
    rules_dir = _broken_copy(tmp_path, "equipment_templates.yaml",
                             lambda d: d["equipment"]["rtu"]["required"].append("NOT-A-ROLE"))
    with pytest.raises(RuleError, match="matches no role"):
        load_rules(rules_dir)
