from __future__ import annotations

import pytest

from ha_tool.registry import EntityIndex


@pytest.fixture
def index() -> EntityIndex:
    """An EntityIndex populated with a small, deterministic fixture.

    Covers: a healthy entity, an unavailable one, an unknown one, a stale one,
    a restored one, an orphaned registry-only entity, a disabled one, a hidden
    one, plus two devices (one with multiple entities)."""
    states = [
        {
            "entity_id": "switch.office_fan_l1",
            "state": "on",
            "attributes": {"friendly_name": "Office Fan L1"},
            "last_changed": "2026-06-24T08:00:00+00:00",
            "last_updated": "2026-06-24T08:00:00+00:00",
        },
        {
            "entity_id": "switch.office_fan_l2",
            "state": "off",
            "attributes": {},
            "last_changed": "2026-06-24T08:00:00+00:00",
            "last_updated": "2026-06-24T08:00:00+00:00",
        },
        {
            "entity_id": "sensor.office_fan_rssi",
            "state": "unavailable",
            "attributes": {},
            "last_changed": "2026-06-24T08:00:00+00:00",
            "last_updated": "2026-06-24T08:00:00+00:00",
        },
        {
            "entity_id": "sensor.bedroom_temp",
            "state": "unknown",
            "attributes": {},
            "last_changed": "2026-06-24T08:00:00+00:00",
            "last_updated": "2026-06-24T08:00:00+00:00",
        },
        {
            "entity_id": "sensor.old_meter",
            "state": "5",
            "attributes": {"restored": True},
            "last_changed": "2026-01-01T00:00:00+00:00",
            "last_updated": "2026-01-01T00:00:00+00:00",
        },
    ]
    entity_entries = [
        {
            "entity_id": "switch.office_fan_l1",
            "platform": "mqtt",
            "device_id": "dev_fan",
        },
        {
            "entity_id": "switch.office_fan_l2",
            "platform": "mqtt",
            "device_id": "dev_fan",
        },
        {
            "entity_id": "sensor.office_fan_rssi",
            "platform": "mqtt",
            "device_id": "dev_fan",
        },
        {
            "entity_id": "sensor.bedroom_temp",
            "platform": "mqtt",
            "device_id": "dev_bed",
        },
        {"entity_id": "sensor.old_meter", "platform": "mqtt"},
        {
            "entity_id": "light.ghost",
            "platform": "hue",
        },  # registry-only, no state -> orphaned
        {"entity_id": "switch.disabled_one", "platform": "mqtt", "disabled_by": "user"},
        {"entity_id": "switch.hidden_one", "platform": "mqtt", "hidden_by": "user"},
    ]
    device_entries = [
        {
            "id": "dev_fan",
            "name": "Office Fan",
            "manufacturer": "Sonoff",
            "model": "ZBMINI",
            "area_id": "office",
            "config_entries": ["entry_mqtt"],
        },
        {"id": "dev_bed", "name": "Bedroom Sensor", "area_id": "bedroom"},
    ]
    area_entries = [
        {"area_id": "office", "name": "Office"},
        {"area_id": "bedroom", "name": "Bedroom"},
    ]
    return EntityIndex(states, entity_entries, device_entries, area_entries)
