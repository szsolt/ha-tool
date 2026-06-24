import pytest

from ha_tool.cli import _build_entity_fields, EntityCategory


def test_basic_fields_assembled():
    fields = _build_entity_fields(
        name="Foo", new_id="switch.bar", area_id="kitchen",
        labels=["a", "b"], icon="mdi:fan", device_class="temperature",
        disabled=None, hidden=None, category=None,
    )
    assert fields == {
        "name": "Foo",
        "new_entity_id": "switch.bar",
        "area_id": "kitchen",
        "labels": ["a", "b"],
        "icon": "mdi:fan",
        "device_class": "temperature",
    }


def test_enable_unhide_clear_to_null():
    fields = _build_entity_fields(
        name=None, new_id=None, area_id=None, labels=None, icon=None,
        device_class=None, disabled=False, hidden=False,
        category=EntityCategory.none,
    )
    assert fields == {"disabled_by": None, "hidden_by": None, "entity_category": None}


def test_disable_hide_set_user():
    fields = _build_entity_fields(
        name=None, new_id=None, area_id=None, labels=None, icon=None,
        device_class=None, disabled=True, hidden=True, category=None,
    )
    assert fields == {"disabled_by": "user", "hidden_by": "user"}


def test_no_fields_raises():
    with pytest.raises(ValueError):
        _build_entity_fields(
            name=None, new_id=None, area_id=None, labels=None, icon=None,
            device_class=None, disabled=None, hidden=None, category=None,
        )
