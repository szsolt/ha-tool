def test_index_fixture_loads(index):
    ids = index.all_entity_ids
    assert "switch.office_fan_l1" in ids
    assert "light.ghost" in ids  # registry-only entity present
