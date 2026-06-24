import re

import pytest

from ha_tool.bulk import analyze_bulk_rename


def _ids():
    return [
        "switch.fan_master_low",
        "switch.fan_bed_high",
        "switch.keep_me",
        "light.already_there",
    ]


def test_backref_substitution():
    results = analyze_bulk_rename(
        _ids(), r"switch\.fan_(.*)", r"switch.light_\1_l1"
    )
    by_from = {r.from_id: r for r in results}
    assert by_from["switch.fan_master_low"].to_id == "switch.light_master_low_l1"
    assert by_from["switch.fan_master_low"].status == "ok"
    # non-matching ids are not returned at all
    assert "switch.keep_me" not in by_from


def test_collision_target_exists():
    results = analyze_bulk_rename(
        _ids(), r"switch\.fan_bed_high", "switch.keep_me"
    )
    assert results[0].status == "collision"


def test_collision_two_sources_one_target():
    results = analyze_bulk_rename(
        _ids(), r"switch\.fan_(.*)", "switch.fan_same"
    )
    assert all(r.status == "collision" for r in results)


def test_noop_when_replacement_equals_source():
    results = analyze_bulk_rename(
        _ids(), r"switch\.keep_me", "switch.keep_me"
    )
    assert results[0].status == "noop"


def test_cross_domain_flagged():
    results = analyze_bulk_rename(
        _ids(), r"switch\.fan_bed_high", "light.fan_bed_high"
    )
    assert results[0].status == "cross-domain"


def test_invalid_regex_raises():
    with pytest.raises(re.error):
        analyze_bulk_rename(_ids(), r"switch\.(", "x")


def test_whole_string_pattern_no_double_substitution():
    # bare .* matches the whole id AND an empty match at the end;
    # without count=1, re.sub would substitute twice.
    results = analyze_bulk_rename(["switch.fan"], r".*", "switch.new")
    assert results[0].to_id == "switch.new"
