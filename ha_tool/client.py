from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidURI


class HAWebSocketClient:
    def __init__(self, url: str, token: str, verbose: bool = False) -> None:
        self._url = self._normalize_url(url)
        self._token = token
        self._verbose = verbose
        self._ws: Any = None
        self._msg_id = 0
        self._pending: dict[int, asyncio.Future[Any] | asyncio.Queue[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.rstrip("/")

        if url.startswith("http"):
            url = url.replace("https://", "wss://").replace("http://", "ws://")
        elif not url.startswith("ws"):
            url = f"ws://{url}"

        if url.endswith("/api/websocket"):
            return url
        if url.endswith("/api"):
            return url + "/websocket"
        return url + "/api/websocket"

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(f"[ha-tool] {msg}", file=sys.stderr)

    async def __aenter__(self) -> HAWebSocketClient:
        self._log(f"Connecting to {self._url}")
        try:
            self._ws = await connect(self._url, max_size=2**24)
        except InvalidURI as e:
            raise ConnectionError(f"Invalid WebSocket URL: {self._url} ({e})") from e
        except OSError as e:
            raise ConnectionError(
                f"Cannot connect to {self._url}: {e}\n"
                f"Check that HASS_URL is correct and Home Assistant is reachable."
            ) from e

        await self._authenticate()
        self._reader_task = asyncio.create_task(self._reader_loop())
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

    async def _authenticate(self) -> None:
        self._log("Authenticating...")
        raw = await self._ws.recv()
        msg = json.loads(raw)
        self._log(f"Received: {msg.get('type', '?')}")

        if msg["type"] != "auth_required":
            raise ConnectionError(f"Expected auth_required, got: {msg}")

        await self._ws.send(json.dumps({"type": "auth", "access_token": self._token}))

        raw = await self._ws.recv()
        msg = json.loads(raw)
        self._log(f"Auth response: {msg.get('type', '?')}")

        if msg["type"] == "auth_invalid":
            raise PermissionError(
                f"Authentication failed: {msg.get('message', 'invalid token')}\n"
                f"Check that HASS_TOKEN is a valid long-lived access token."
            )
        if msg["type"] != "auth_ok":
            raise ConnectionError(f"Unexpected auth response: {msg}")

        self._log(f"Authenticated (HA {msg.get('ha_version', '?')})")

    async def _reader_loop(self) -> None:
        """Dispatch incoming messages to the correct pending future/queue by id."""
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_id = msg.get("id")
                self._log(f"Received msg id={msg_id} type={msg.get('type', '?')}")
                if msg_id is not None and msg_id in self._pending:
                    pending = self._pending[msg_id]
                    if isinstance(pending, asyncio.Queue):
                        await pending.put(msg)
                    else:
                        pending.set_result(msg)
        except ConnectionClosed as e:
            self._log(f"Connection closed: {e}")
        except asyncio.CancelledError:
            raise
        finally:
            for pending in self._pending.values():
                if isinstance(pending, asyncio.Future) and not pending.done():
                    pending.set_exception(ConnectionError("WebSocket connection closed unexpectedly"))

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def send_command(self, command_type: str, **kwargs: Any) -> Any:
        msg_id = self._next_id()
        payload = {"id": msg_id, "type": command_type, **kwargs}

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[msg_id] = future

        self._log(f"Sending id={msg_id} type={command_type}")
        try:
            await self._ws.send(json.dumps(payload))
            msg = await future
        finally:
            self._pending.pop(msg_id, None)

        if not msg.get("success", False):
            error = msg.get("error", {})
            raise RuntimeError(
                f"Command '{command_type}' failed: "
                f"{error.get('code', '?')} - {error.get('message', '?')}"
            )
        return msg.get("result")

    async def get_states(self) -> list[dict]:
        return await self.send_command("get_states")

    async def get_entity_registry(self) -> list[dict]:
        return await self.send_command("config/entity_registry/list")

    async def get_device_registry(self) -> list[dict]:
        return await self.send_command("config/device_registry/list")

    async def get_area_registry(self) -> list[dict]:
        return await self.send_command("config/area_registry/list")

    async def get_services(self) -> dict:
        return await self.send_command("get_services")

    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict | None = None,
        target: dict | None = None,
    ) -> dict | None:
        """Call a Home Assistant service."""
        kwargs: dict[str, Any] = {"domain": domain, "service": service}
        if data:
            kwargs["service_data"] = data
        if target:
            kwargs["target"] = target
        return await self.send_command("call_service", **kwargs)

    async def render_template(self, template: str) -> str:
        """Render a Jinja2 template and return the result.
        
        The render_template API is subscription-based: first we get a success ack,
        then an event message with the rendered result.
        """
        msg_id = self._next_id()
        payload = {"id": msg_id, "type": "render_template", "template": template}

        # Use a queue to receive multiple messages for this ID
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._pending[msg_id] = queue

        self._log(f"Sending id={msg_id} type=render_template")
        try:
            await self._ws.send(json.dumps(payload))
            
            # Wait for the success acknowledgment (type=result)
            ack_msg = await queue.get()
            
            if not ack_msg.get("success", False):
                error = ack_msg.get("error", {})
                raise RuntimeError(
                    f"Command 'render_template' failed: "
                    f"{error.get('code', '?')} - {error.get('message', '?')}"
                )
            
            # Wait for the event message with the result (type=event)
            event_msg = await queue.get()
            
            # Extract the result from the event
            event = event_msg.get("event", {})
            return event.get("result", "")
        finally:
            self._pending.pop(msg_id, None)

    async def fetch_all(
        self,
        include_services: bool = False,
    ) -> tuple[list[dict], list[dict], list[dict], list[dict], dict | None]:
        """Fetch registries concurrently over a single WebSocket connection."""
        coros: list[Any] = [
            self.get_states(),
            self.get_entity_registry(),
            self.get_device_registry(),
            self.get_area_registry(),
        ]
        if include_services:
            coros.append(self.get_services())

        results = await asyncio.gather(*coros)

        return (
            results[0],
            results[1],
            results[2],
            results[3],
            results[4] if include_services else None,
        )
