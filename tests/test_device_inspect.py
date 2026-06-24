import pytest

from ha_tool.models import DeviceCandidate, DeviceDetail


def test_resolve_by_exact_id(index):
    result = index.device_inspect("dev_fan")
    assert isinstance(result, DeviceDetail)
    assert result.name == "Office Fan"
    ids = {e.entity_id for e in result.entities}
    assert ids == {"switch.office_fan_l1", "switch.office_fan_l2", "sensor.office_fan_rssi"}


def test_resolve_by_name_substring(index):
    result = index.device_inspect("office")
    assert isinstance(result, DeviceDetail)
    assert result.device_id == "dev_fan"
    assert result.area == "Office"


def test_ambiguous_returns_candidates(index):
    result = index.device_inspect("e")
    assert isinstance(result, list)
    assert all(isinstance(c, DeviceCandidate) for c in result)
    assert len(result) >= 2


def test_none_returns_empty_list(index):
    result = index.device_inspect("nonexistent-device-xyz")
    assert result == []
