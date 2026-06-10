from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidURI


class HAWebSocketClient:
    def __init__(self, url: str, token: str, verbose: bool = False) -> None:
        self._url = self._normalize_url(url)
        self._http_base = self._http_base_url(url)
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

    @staticmethod
    def _http_base_url(url: str) -> str:
        url = url.rstrip("/")
        if url.startswith("ws://"):
            url = "http://" + url[len("ws://") :]
        elif url.startswith("wss://"):
            url = "https://" + url[len("wss://") :]
        elif not url.startswith("http"):
            url = "http://" + url
        for suffix in ("/api/websocket", "/api"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
                break
        return url

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(f"[ha-tool] {msg}", file=sys.stderr)

    async def __aenter__(self) -> HAWebSocketClient:
        self._log(f"Connecting to {self._url}")
        try:
            self._ws = await connect(self._url, max_size=2**24, open_timeout=10)
        except InvalidURI as e:
            raise ConnectionError(f"Invalid WebSocket URL: {self._url} ({e})") from e
        except (OSError, asyncio.TimeoutError, TimeoutError) as e:
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
                    pending.set_exception(
                        ConnectionError("WebSocket connection closed unexpectedly")
                    )

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

    async def get_core_config(self) -> dict:
        return await self.send_command("get_config")

    async def get_panels(self) -> dict:
        return await self.send_command("get_panels")

    async def get_config_entries(self) -> list[dict]:
        return await self.send_command("config_entries/get")

    async def get_label_registry(self) -> list[dict]:
        return await self.send_command("config/label_registry/list")

    async def get_floor_registry(self) -> list[dict]:
        return await self.send_command("config/floor_registry/list")

    async def get_category_registry(self, scope: str) -> list[dict]:
        return await self.send_command("config/category_registry/list", scope=scope)

    async def history_during_period(
        self,
        entity_ids: list[str],
        start_time: str,
        end_time: str | None = None,
        minimal_response: bool = False,
        no_attributes: bool = False,
    ) -> dict:
        payload: dict[str, Any] = {
            "entity_ids": entity_ids,
            "start_time": start_time,
            "minimal_response": minimal_response,
            "no_attributes": no_attributes,
        }
        if end_time:
            payload["end_time"] = end_time
        return await self.send_command("history/history_during_period", **payload)

    async def logbook(
        self,
        start_time: str,
        end_time: str | None = None,
        entity_ids: list[str] | None = None,
    ) -> list[dict]:
        payload: dict[str, Any] = {"start_time": start_time}
        if end_time:
            payload["end_time"] = end_time
        if entity_ids:
            payload["entity_ids"] = entity_ids
        return await self.send_command("logbook/get_events", **payload)

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

    async def remove_entity(self, entity_id: str) -> dict | None:
        return await self.send_command(
            "config/entity_registry/remove", entity_id=entity_id
        )

    async def remove_device(self, device_id: str, config_entry_id: str) -> dict | None:
        return await self.send_command(
            "config/device_registry/remove_config_entry",
            device_id=device_id,
            config_entry_id=config_entry_id,
        )

    async def remove_config_entry(self, entry_id: str) -> dict | None:
        return await self.send_command("config_entries/remove", entry_id=entry_id)

    async def check_config(self) -> dict:
        """Validate configuration.yaml via REST POST /api/config/core/check_config.

        Returns {"result": "valid"|"invalid", "errors": str|None, "warnings": str|None}.
        """
        url = f"{self._http_base}/api/config/core/check_config"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        self._log(f"POST {url}")
        req = urllib.request.Request(url, data=b"", headers=headers, method="POST")

        def _do() -> dict:
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 401:
                    raise PermissionError(
                        "Authentication failed (HTTP 401). Check HASS_TOKEN."
                    ) from e
                raise RuntimeError(f"check_config HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                raise ConnectionError(f"Cannot reach {url}: {e.reason}") from e

        return await asyncio.to_thread(_do)

    async def error_log(self) -> str:
        """Fetch full error log via REST GET /api/error_log (plaintext)."""
        url = f"{self._http_base}/api/error_log"
        headers = {"Authorization": f"Bearer {self._token}"}
        self._log(f"GET {url}")
        req = urllib.request.Request(url, headers=headers, method="GET")

        def _do() -> str:
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 401:
                    raise PermissionError(
                        "Authentication failed (HTTP 401). Check HASS_TOKEN."
                    ) from e
                raise RuntimeError(f"error_log HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                raise ConnectionError(f"Cannot reach {url}: {e.reason}") from e

        return await asyncio.to_thread(_do)

    async def list_calendars(self) -> list[dict]:
        """REST GET /api/calendars."""
        url = f"{self._http_base}/api/calendars"
        headers = {"Authorization": f"Bearer {self._token}"}
        self._log(f"GET {url}")
        req = urllib.request.Request(url, headers=headers, method="GET")

        def _do() -> list[dict]:
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 401:
                    raise PermissionError(
                        "Authentication failed (HTTP 401). Check HASS_TOKEN."
                    ) from e
                raise RuntimeError(f"calendars HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                raise ConnectionError(f"Cannot reach {url}: {e.reason}") from e

        return await asyncio.to_thread(_do)

    async def calendar_events(self, entity_id: str, start: str, end: str) -> list[dict]:
        """REST GET /api/calendars/<entity_id>?start=&end= (ISO8601)."""
        from urllib.parse import quote, urlencode

        qs = urlencode({"start": start, "end": end})
        url = f"{self._http_base}/api/calendars/{quote(entity_id, safe='')}?{qs}"
        headers = {"Authorization": f"Bearer {self._token}"}
        self._log(f"GET {url}")
        req = urllib.request.Request(url, headers=headers, method="GET")

        def _do() -> list[dict]:
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 401:
                    raise PermissionError(
                        "Authentication failed (HTTP 401). Check HASS_TOKEN."
                    ) from e
                if e.code == 404:
                    raise RuntimeError(f"Calendar entity not found: {entity_id}") from e
                raise RuntimeError(f"calendar HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                raise ConnectionError(f"Cannot reach {url}: {e.reason}") from e

        return await asyncio.to_thread(_do)

    async def system_health_info(
        self,
        timeout: float = 30.0,
        idle_timeout: float = 2.0,
    ) -> dict[str, dict]:
        """Collect system_health/info events.

        HA emits a `result` success ack first, then one `event` per integration.
        We wait for the ack, then drain events until `idle_timeout` seconds
        elapse without a new event.

        Returns mapping {domain: info_dict}.
        """
        msg_id = self._next_id()
        payload = {"id": msg_id, "type": "system_health/info"}

        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._pending[msg_id] = queue

        self._log(f"Sending id={msg_id} type=system_health/info")
        result: dict[str, dict] = {}
        ack_seen = False
        try:
            await self._ws.send(json.dumps(payload))
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout

            while not ack_seen:
                remaining = max(0.0, deadline - loop.time())
                msg = await asyncio.wait_for(queue.get(), timeout=remaining)
                if msg.get("type") == "result":
                    if not msg.get("success", False):
                        err = msg.get("error", {})
                        raise RuntimeError(
                            f"system_health/info failed: {err.get('code','?')} - {err.get('message','?')}"
                        )
                    ack_seen = True
                elif msg.get("type") == "event":
                    ev = msg.get("event", {})
                    domain = ev.get("domain")
                    info = ev.get("info") or {}
                    if domain:
                        result[domain] = info

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=idle_timeout)
                except asyncio.TimeoutError:
                    return result
                if msg.get("type") == "event":
                    ev = msg.get("event", {})
                    domain = ev.get("domain")
                    info = ev.get("info") or {}
                    if domain:
                        result[domain] = info
        finally:
            self._pending.pop(msg_id, None)

    async def list_repairs(self) -> dict:
        return await self.send_command("repairs/list_issues")

    async def stream_events(self, event_type: str | None = None):
        """Yield events from subscribe_events. Cancel to stop and unsubscribe."""
        msg_id = self._next_id()
        payload: dict[str, Any] = {"id": msg_id, "type": "subscribe_events"}
        if event_type:
            payload["event_type"] = event_type

        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._pending[msg_id] = queue

        self._log(f"Sending id={msg_id} type=subscribe_events event_type={event_type}")
        try:
            await self._ws.send(json.dumps(payload))

            ack = await queue.get()
            if not ack.get("success", False):
                err = ack.get("error", {})
                raise RuntimeError(
                    f"subscribe_events failed: {err.get('code','?')} - {err.get('message','?')}"
                )

            while True:
                msg = await queue.get()
                if msg.get("type") == "event":
                    yield msg.get("event") or {}
        finally:
            try:
                unsub_id = self._next_id()
                await self._ws.send(
                    json.dumps(
                        {
                            "id": unsub_id,
                            "type": "unsubscribe_events",
                            "subscription": msg_id,
                        }
                    )
                )
            except Exception:
                pass
            self._pending.pop(msg_id, None)

    async def get_notifications(self) -> list[dict]:
        return await self.send_command("persistent_notification/get")

    async def list_lovelace_dashboards(self) -> list[dict]:
        """List user-created Lovelace dashboards (lovelace/dashboards/list).

        Each entry includes `url_path`, `mode` ("yaml" or "storage"), `title`,
        etc. The built-in default dashboard is NOT included here.
        """
        return await self.send_command("lovelace/dashboards/list")

    async def reload_lovelace_config(self, url_path: str | None) -> dict:
        """Force Home Assistant to re-read a YAML-mode dashboard from disk.

        Sends lovelace/config with force=true. `url_path=None` targets the
        built-in default dashboard. Returns the freshly-parsed config dict on
        success; raises RuntimeError if HA reports failure.
        """
        return await self.send_command("lovelace/config", url_path=url_path, force=True)

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
