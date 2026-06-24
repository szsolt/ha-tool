def _flags_for(report, entity_id):
    for r in report:
        if r.entity_id == entity_id:
            return set(r.flags)
    return None


def test_unavailable_and_unknown(index):
    report = index.stale_report(stale_seconds=10**9, now_iso="2026-06-24T09:00:00+00:00")
    assert "unavailable" in _flags_for(report, "sensor.office_fan_rssi")
    assert "unknown" in _flags_for(report, "sensor.bedroom_temp")


def test_restored_flag(index):
    report = index.stale_report(stale_seconds=10**9, now_iso="2026-06-24T09:00:00+00:00")
    assert "restored" in _flags_for(report, "sensor.old_meter")


def test_orphaned_registry_only(index):
    report = index.stale_report(stale_seconds=10**9, now_iso="2026-06-24T09:00:00+00:00")
    assert "orphaned" in _flags_for(report, "light.ghost")


def test_disabled_and_hidden(index):
    report = index.stale_report(stale_seconds=10**9, now_iso="2026-06-24T09:00:00+00:00")
    assert "disabled" in _flags_for(report, "switch.disabled_one")
    assert "hidden" in _flags_for(report, "switch.hidden_one")


def test_stale_by_age(index):
    report = index.stale_report(stale_seconds=3600, now_iso="2026-06-24T09:00:00+00:00")
    assert "stale" in _flags_for(report, "sensor.old_meter")
    assert _flags_for(report, "switch.office_fan_l1") is None


def test_healthy_entities_excluded(index):
    report = index.stale_report(stale_seconds=10**9, now_iso="2026-06-24T09:00:00+00:00")
    assert _flags_for(report, "switch.office_fan_l1") is None
    assert _flags_for(report, "switch.office_fan_l2") is None
