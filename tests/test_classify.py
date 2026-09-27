from pointmap.models import AUTO, FLAGGED, REVIEW


def test_sp_means_static_pressure_when_units_say_pressure(classify):
    r = classify("OFFICE-A:NAE-01/FC-1.AHU-1.SA-SP", "AI", "in W.C.")
    assert (r.canonical_name, r.status) == ("AHU-01.DA-P", AUTO)


def test_sp_means_setpoint_when_units_say_temperature(classify):
    r = classify("OFFICE-A:NAE-01/FC-2.VMA-203.ZN-SP", "AV", "deg F")
    assert (r.canonical_name, r.status) == ("VAV-203.ZN-T-SP", AUTO)


def test_repeated_ambiguous_token_resolves_to_both_meanings(classify):
    # Regression: SA-SP-SP once tied "pressure + pressure" with the right reading.
    r = classify("OFFICE-A:NAE-01/FC-1.AHU-1.SA-SP-SP", "AV", "in W.C.")
    assert r.canonical_name == "AHU-01.DA-P-SP"


def test_sp_without_units_is_not_guessed(classify):
    assert classify("FC-2.VMA-205.ZN-SP", "AV", "").status == REVIEW


def test_status_reading_amps_is_refused_with_a_wiring_question(classify):
    r = classify("#pine_paper/rtu_1/sf_status", "AI", "A")
    assert r.status == REVIEW
    assert "current transducer" in r.review_reason
    assert any(f.startswith("STATUS_ON_ANALOG") for f in r.flags)


def test_non_telemetry_is_refused(classify):
    assert classify("SPARE_AI_3", "AI").review_reason == "spare / unused I/O"
    assert classify("AHU1 PID KP", "AV").status == REVIEW


def test_point_without_equipment_goes_to_review(classify):
    r = classify("ROOM 214 TEMP", "AI", "°F")
    assert r.status == REVIEW and r.role_id == "ZN-T"   # best guess kept for the reviewer


def test_site_level_point_needs_no_equipment(classify):
    r = classify("OAT", "AI", "°F", site="SITE-X")
    assert (r.canonical_name, r.status) == ("SITE-X.OA-T", AUTO)


def test_typo_is_mapped_but_never_auto_accepted(classify):
    r = classify("RTU1 ZN TEMPATURE", "AI", "°F")
    assert (r.role_id, r.status) == ("ZN-T", FLAGGED)


def test_unknown_words_block_auto_accept(classify):
    # Regression: a high-limit parameter once scored 0.80 as the DAT sensor.
    assert classify("RTU7 DAT HI LIMIT", "AV", "°F").status != AUTO


def test_equipment_context_fills_the_gap(classify):
    assert classify("EF-2 S/S", "BO").canonical_name == "EF-02.EF-C"


def test_stage_number_becomes_part_of_the_name(classify):
    r = classify("/Drivers/BacnetNetwork/RTU_4/points/HtgStg2", "binaryOutput")
    assert (r.canonical_name, r.stage) == ("RTU-04.HTG-STG2-C", 2)


def test_every_decision_carries_its_score_breakdown(classify):
    r = classify("RTU1-DAT", "AI", "°F")
    assert any(line.startswith("score:") for line in r.evidence)
