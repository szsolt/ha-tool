import asyncio

import pytest

from ha_tool.client import HAWebSocketClient


def _client(reply):
    client = HAWebSocketClient("http://ha.test:8123", "token")
    calls = []

    def fake(method, path, body=None):
        calls.append((method, path))
        return reply

    client._rest_json = fake  # type: ignore[method-assign]
    return client, calls


def test_removes_over_rest():
    client, calls = _client((200, {"require_restart": False}))
    assert asyncio.run(client.remove_config_entry("abc")) == {"require_restart": False}
    assert calls == [("DELETE", "/api/config/config_entries/entry/abc")]


def test_missing_entry_raises():
    client, _ = _client((404, {"message": "Invalid entry specified"}))
    with pytest.raises(RuntimeError, match="HTTP 404"):
        asyncio.run(client.remove_config_entry("nope"))
