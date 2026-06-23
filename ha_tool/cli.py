from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from ha_tool import __version__
from ha_tool.client import HAWebSocketClient
from ha_tool.registry import EntityIndex


class OutputFormat(str, Enum):
    human = "human"
    json = "json"


class FilterMode(str, Enum):
    all = "all"
    missing = "missing"
    existing = "existing"


@dataclass
class State:
    output: OutputFormat = OutputFormat.human
    verbose: bool = False


state = State()

app = typer.Typer(
    name="ha-tool",
    help="Home Assistant entity discovery tool for AI agents.",
    rich_markup_mode=None,
    add_completion=False,
    no_args_is_help=True,
)


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(f"ha-tool, version {__version__}")
        raise typer.Exit()


def get_config() -> tuple[str, str]:
    url = os.environ.get("HASS_SERVER") or os.environ.get("HASS_URL", "")
    token = os.environ.get("HASS_TOKEN", "")
    missing: list[str] = []
    if not url:
        missing.append(
            "HASS_SERVER  (e.g. export HASS_SERVER=http://homeassistant.local:8123)"
        )
    if not token:
        missing.append("HASS_TOKEN   (Profile → Security → Long-Lived Access Tokens)")
    if missing:
        typer.echo("Missing required environment variables:", err=True)
        for m in missing:
            typer.echo(f"  {m}", err=True)
        sys.exit(1)
    return url, token


async def build_index(
    include_services: bool = False, verbose: bool = False
) -> EntityIndex:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        states, entities, devices, areas, services = await client.fetch_all(
            include_services=include_services,
        )
    return EntityIndex(states, entities, devices, areas, services)


def output_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


def output_table(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        typer.echo("No results found.")
        return

    col_widths: dict[str, int] = {}
    for col in columns:
        max_val = max((len(str(row.get(col, "") or "")) for row in rows), default=0)
        col_widths[col] = max(len(col), min(max_val, 60))

    header = "  ".join(col.upper().ljust(col_widths[col]) for col in columns)
    typer.echo(header)
    typer.echo("  ".join("─" * col_widths[col] for col in columns))

    for row in rows:
        vals: list[str] = []
        for col in columns:
            v = str(row.get(col, "") or "")
            if len(v) > 60:
                v = v[:57] + "..."
            vals.append(v.ljust(col_widths[col]))
        typer.echo("  ".join(vals))

    typer.echo(f"\n({len(rows)} results)")


def run_with_error_handling(coro: Any) -> Any:
    """Run an async coroutine with user-friendly error handling."""
    try:
        return asyncio.run(coro)
    except ConnectionError as e:
        typer.echo(f"Connection error: {e}", err=True)
        sys.exit(1)
    except PermissionError as e:
        typer.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.callback()
def main_callback(
    output: Annotated[
        OutputFormat, typer.Option("--output", "-o", help="Output format")
    ] = OutputFormat.human,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show debug output on stderr")
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_cb,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Home Assistant entity discovery tool for AI agents."""
    state.output = output
    state.verbose = verbose


@app.command()
def search(
    text: Annotated[Optional[str], typer.Argument()] = None,
    domain: Annotated[
        Optional[str],
        typer.Option(
            "--domain", "-d", help="Filter by domain (e.g. sensor, climate, light)"
        ),
    ] = None,
    device_class: Annotated[
        Optional[str],
        typer.Option(
            "--device-class",
            "-c",
            help="Filter by device_class (e.g. temperature, motion)",
        ),
    ] = None,
    area: Annotated[
        Optional[str],
        typer.Option("--area", "-a", help="Filter by area name (substring match)"),
    ] = None,
    integration: Annotated[
        Optional[str],
        typer.Option(
            "--integration",
            "-i",
            help="Filter by integration/platform (e.g. hue, zwave_js, mqtt)",
        ),
    ] = None,
    include_disabled: Annotated[
        bool, typer.Option("--include-disabled", help="Include disabled entities")
    ] = False,
) -> None:
    """Search for entities by name, domain, device_class, area, or integration.

    TEXT supports substring, glob (* ?), and regex ([0-9], |, etc.) patterns.
    """
    index = run_with_error_handling(build_index(verbose=state.verbose))
    results = index.search(
        text=text,
        domain=domain,
        device_class=device_class,
        area=area,
        integration=integration,
        include_disabled=include_disabled,
    )

    if state.output == OutputFormat.json:
        output_json([r.model_dump(exclude_none=True) for r in results])
    else:
        rows = [r.model_dump() for r in results]
        output_table(
            rows,
            [
                "entity_id",
                "friendly_name",
                "domain",
                "device_class",
                "area",
                "state",
                "platform",
            ],
        )


@app.command()
def inspect(entity_ids: Annotated[list[str], typer.Argument()]) -> None:
    """Get full details for one or more entities."""
    index = run_with_error_handling(build_index(verbose=state.verbose))
    results = index.inspect(list(entity_ids))

    if state.output == OutputFormat.json:
        output_json([r.model_dump(exclude_none=True) for r in results])
    else:
        for r in results:
            typer.echo(f"{'─' * 60}")
            typer.echo(f"Entity:       {r.entity_id}")
            typer.echo(f"Name:         {r.friendly_name or '—'}")
            typer.echo(f"Domain:       {r.domain}")
            typer.echo(f"Platform:     {r.platform or '—'}")
            typer.echo(f"Device Class: {r.device_class or '—'}")
            typer.echo(f"Area:         {r.area or '—'}")
            typer.echo(f"State:        {r.state or '—'}")
            typer.echo(f"Last Changed: {r.last_changed or '—'}")
            typer.echo(f"Device:       {r.device_name or '—'}")
            typer.echo(f"Manufacturer: {r.device_manufacturer or '—'}")
            typer.echo(f"Model:        {r.device_model or '—'}")
            typer.echo(f"Category:     {r.entity_category or '—'}")
            typer.echo(f"Labels:       {', '.join(r.labels) if r.labels else '—'}")
            if r.attributes:
                typer.echo("Attributes:")
                for k, v in sorted(r.attributes.items()):
                    typer.echo(f"  {k}: {v}")
        typer.echo(f"{'─' * 60}")
        typer.echo(f"({len(results)} entities)")


@app.command()
def get(entity_id: str) -> None:
    """Get current state of a single entity (minimal output)."""
    index = run_with_error_handling(build_index(verbose=state.verbose))
    result = index.get_state(entity_id)

    if result is None:
        if state.output == OutputFormat.json:
            output_json({"error": f"Entity '{entity_id}' not found"})
        else:
            typer.echo(f"Entity '{entity_id}' not found.", err=True)
        sys.exit(1)

    if state.output == OutputFormat.json:
        output_json(result)
    else:
        typer.echo(
            f"{result['entity_id']}  {result['friendly_name'] or '—'}  {result['state']}"
        )


@app.command()
def areas() -> None:
    """List all configured areas."""
    index = run_with_error_handling(build_index(verbose=state.verbose))
    result = index.list_areas()

    if state.output == OutputFormat.json:
        output_json([a.model_dump(exclude_none=True) for a in result])
    else:
        rows = [a.model_dump() for a in result]
        output_table(rows, ["area_id", "name", "floor_id"])


@app.command()
def domains() -> None:
    """List all entity domains with entity counts."""
    index = run_with_error_handling(build_index(verbose=state.verbose))
    result = index.list_domains()

    if state.output == OutputFormat.json:
        output_json([d.model_dump() for d in result])
    else:
        rows = [
            {
                "domain": d.domain,
                "count": d.entity_count,
                "examples": ", ".join(d.sample_entities),
            }
            for d in result
        ]
        output_table(rows, ["domain", "count", "examples"])


@app.command()
def integrations() -> None:
    """List all integrations with entity counts."""
    index = run_with_error_handling(build_index(verbose=state.verbose))
    result = index.list_integrations()

    if state.output == OutputFormat.json:
        output_json([i.model_dump() for i in result])
    else:
        rows = [
            {
                "integration": i.integration,
                "count": i.entity_count,
                "examples": ", ".join(i.sample_entities),
            }
            for i in result
        ]
        output_table(rows, ["integration", "count", "examples"])


@app.command()
def services(
    text: Annotated[Optional[str], typer.Argument()] = None,
    domain: Annotated[
        Optional[str],
        typer.Option(
            "--domain", "-d", help="Filter by service domain (e.g. light, climate)"
        ),
    ] = None,
) -> None:
    """List or search available service actions."""
    index = run_with_error_handling(
        build_index(include_services=True, verbose=state.verbose)
    )
    results = index.search_services(text=text, domain=domain)

    if state.output == OutputFormat.json:
        output_json([s.model_dump(exclude_none=True) for s in results])
    else:
        rows: list[dict] = []
        for s in results:
            rows.append(
                {
                    "service": f"{s.domain}.{s.service}",
                    "name": s.name or "",
                    "description": s.description or "",
                    "fields": ", ".join(f.name for f in s.fields) if s.fields else "",
                }
            )
        output_table(rows, ["service", "name", "description"])


RELOAD_DOMAINS = [
    "automation",
    "script",
    "scene",
    "group",
    "input_boolean",
    "input_number",
    "input_select",
    "input_text",
    "input_datetime",
    "input_button",
    "timer",
    "counter",
    "schedule",
    "template",
    "person",
    "zone",
]


async def _call_service(
    domain: str,
    service: str,
    data: dict | None = None,
    target: dict | None = None,
    verbose: bool = False,
) -> dict | None:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.call_service(domain, service, data, target)


async def _render_template(template: str, verbose: bool = False) -> str:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.render_template(template)


@app.command(name="call")
def call_service(
    service_name: str,
    data_json: Annotated[
        Optional[str],
        typer.Option("--data", "-d", help="Service data as JSON object"),
    ] = None,
    target_json: Annotated[
        Optional[str],
        typer.Option(
            "--target",
            "-t",
            help="Target as JSON (entity_id, device_id, or area_id)",
        ),
    ] = None,
) -> None:
    """Call a Home Assistant service.

    SERVICE_NAME is in the format domain.service (e.g. light.turn_on, automation.reload).
    """
    if "." not in service_name:
        typer.echo(
            f"Invalid service name '{service_name}'. Expected format: domain.service",
            err=True,
        )
        sys.exit(1)

    domain, service = service_name.split(".", 1)

    data: dict | None = None
    target: dict | None = None

    if data_json:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            typer.echo(f"Invalid JSON for --data: {e}", err=True)
            sys.exit(1)

    if target_json:
        try:
            target = json.loads(target_json)
        except json.JSONDecodeError as e:
            typer.echo(f"Invalid JSON for --target: {e}", err=True)
            sys.exit(1)

    result = run_with_error_handling(
        _call_service(domain, service, data, target, verbose=state.verbose)
    )

    if state.output == OutputFormat.json:
        output_json({"success": True, "service": service_name, "result": result})
    else:
        typer.echo(f"Called {service_name}")


@app.command()
def reload(domain: Annotated[Optional[str], typer.Argument()] = None) -> None:
    """Reload Home Assistant configuration.

    DOMAIN can be: automations, scripts, scenes, groups, all, or any reloadable domain.
    Without arguments, shows available reload options.
    """
    if domain is None:
        if state.output == OutputFormat.json:
            output_json({"available_domains": ["all"] + RELOAD_DOMAINS})
        else:
            typer.echo("Available reload domains:")
            typer.echo("  all — Reload all configuration")
            for d in RELOAD_DOMAINS:
                typer.echo(f"  {d}")
        return

    domain = domain.lower().rstrip("s")  # Allow "automations" -> "automation"

    if domain == "all":
        run_with_error_handling(
            _call_service("homeassistant", "reload_all", verbose=state.verbose)
        )
        if state.output == OutputFormat.json:
            output_json({"success": True, "reloaded": "all"})
        else:
            typer.echo("Reloaded all configuration")
    elif domain in RELOAD_DOMAINS:
        run_with_error_handling(_call_service(domain, "reload", verbose=state.verbose))
        if state.output == OutputFormat.json:
            output_json({"success": True, "reloaded": domain})
        else:
            typer.echo(f"Reloaded {domain}")
    else:
        typer.echo(
            f"Unknown reload domain '{domain}'. Use 'ha-tool reload' to see options.",
            err=True,
        )
        sys.exit(1)


@app.command()
def restart(
    confirm: Annotated[
        bool, typer.Option("--confirm", "-y", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Restart Home Assistant."""
    if not confirm and state.output != OutputFormat.json:
        if not typer.confirm("Are you sure you want to restart Home Assistant?"):
            typer.echo("Aborted.")
            return

    try:
        asyncio.run(_call_service("homeassistant", "restart", verbose=state.verbose))
    except ConnectionError:
        pass
    except PermissionError as e:
        typer.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if state.output == OutputFormat.json:
        output_json({"success": True, "action": "restart"})
    else:
        typer.echo("Home Assistant is restarting...")


@app.command()
def template(template_str: str) -> None:
    """Render a Jinja2 template.

    TEMPLATE_STR is a Jinja2 template string, e.g. '{{ states("sensor.temperature") }}'.
    """
    result = run_with_error_handling(
        _render_template(template_str, verbose=state.verbose)
    )

    if state.output == OutputFormat.json:
        output_json({"template": template_str, "result": result})
    else:
        typer.echo(result)


async def _get_core_config(verbose: bool = False) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_core_config()


@app.command()
def info() -> None:
    """Show Home Assistant core configuration (version, location, units)."""
    from ha_tool.models import CoreConfig

    raw = run_with_error_handling(_get_core_config(verbose=state.verbose))
    cfg = CoreConfig.model_validate(raw)

    if state.output == OutputFormat.json:
        output_json(cfg.model_dump(exclude_none=True))
    else:
        typer.echo(f"Version:      {cfg.version or '—'}")
        typer.echo(f"Location:     {cfg.location_name or '—'}")
        typer.echo(f"Coordinates:  {cfg.latitude}, {cfg.longitude}")
        typer.echo(f"Elevation:    {cfg.elevation}")
        typer.echo(f"Time zone:    {cfg.time_zone or '—'}")
        typer.echo(f"Currency:     {cfg.currency or '—'}")
        typer.echo(f"Country:      {cfg.country or '—'}")
        typer.echo(f"Language:     {cfg.language or '—'}")
        typer.echo(f"Safe mode:    {cfg.safe_mode}")
        typer.echo(f"State:        {cfg.state or '—'}")
        typer.echo(f"Components:   {len(cfg.components)} loaded")


async def _get_panels(verbose: bool = False) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_panels()


@app.command()
def panels() -> None:
    """List registered UI panels."""
    from ha_tool.models import Panel

    raw = run_with_error_handling(_get_panels(verbose=state.verbose))
    items = [Panel.model_validate(v) for v in (raw or {}).values()]

    if state.output == OutputFormat.json:
        output_json([p.model_dump(exclude_none=True) for p in items])
    else:
        rows = [p.model_dump() for p in items]
        output_table(
            rows, ["url_path", "title", "component_name", "icon", "require_admin"]
        )


async def _get_config_entries(verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_config_entries()


@app.command(name="config-entries")
def config_entries(
    domain: Annotated[
        Optional[str],
        typer.Option("--domain", "-d", help="Filter by integration domain"),
    ] = None,
) -> None:
    """List integration config entries."""
    from ha_tool.models import ConfigEntry

    raw = run_with_error_handling(_get_config_entries(verbose=state.verbose))
    items = [ConfigEntry.model_validate(e) for e in (raw or [])]
    if domain:
        items = [e for e in items if e.domain == domain]

    if state.output == OutputFormat.json:
        output_json([e.model_dump(exclude_none=True) for e in items])
    else:
        rows = [e.model_dump() for e in items]
        output_table(
            rows, ["entry_id", "domain", "title", "state", "source", "disabled_by"]
        )


async def _get_labels(verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_label_registry()


@app.command()
def labels() -> None:
    """List configured labels."""
    from ha_tool.models import Label

    raw = run_with_error_handling(_get_labels(verbose=state.verbose))
    items = [Label.model_validate(item) for item in (raw or [])]

    if state.output == OutputFormat.json:
        output_json([item.model_dump(exclude_none=True) for item in items])
    else:
        rows = [item.model_dump() for item in items]
        output_table(rows, ["label_id", "name", "color", "icon", "description"])


async def _get_floors(verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_floor_registry()


@app.command()
def floors() -> None:
    """List configured floors."""
    from ha_tool.models import Floor

    raw = run_with_error_handling(_get_floors(verbose=state.verbose))
    items = [Floor.model_validate(f) for f in (raw or [])]

    if state.output == OutputFormat.json:
        output_json([f.model_dump(exclude_none=True) for f in items])
    else:
        rows = [f.model_dump() for f in items]
        output_table(rows, ["floor_id", "name", "level", "icon"])


async def _get_categories(scope: str, verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_category_registry(scope)


@app.command()
def categories(
    scope: Annotated[str, typer.Argument()] = "automation",
) -> None:
    """List categories for a scope (e.g. automation, script, scene)."""
    from ha_tool.models import Category

    raw = run_with_error_handling(_get_categories(scope, verbose=state.verbose))
    items = [Category.model_validate({**c, "scope": scope}) for c in (raw or [])]

    if state.output == OutputFormat.json:
        output_json([c.model_dump(exclude_none=True) for c in items])
    else:
        rows = [c.model_dump() for c in items]
        output_table(rows, ["category_id", "scope", "name", "icon"])


async def _history(
    entity_id: str,
    start: str,
    end: str | None,
    minimal: bool,
    verbose: bool = False,
) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.history_during_period(
            [entity_id],
            start,
            end,
            minimal_response=minimal,
            no_attributes=minimal,
        )


@app.command()
def history(
    entity_id: str,
    since: Annotated[
        str, typer.Option("--since", help="Start time (1h, 30m, 2d, ISO, today)")
    ] = "1h",
    until: Annotated[str, typer.Option("--until", help="End time (now, ISO)")] = "now",
    minimal: Annotated[
        bool, typer.Option("--minimal", help="Strip attributes for smaller payload")
    ] = False,
) -> None:
    """Show state history of an entity over a time window."""
    from ha_tool.timeparse import parse_time
    from ha_tool.models import HistoryPoint

    try:
        start_dt = parse_time(since)
        end_dt = parse_time(until)
    except ValueError as e:
        typer.echo(f"Invalid time: {e}", err=True)
        sys.exit(1)

    raw = run_with_error_handling(
        _history(
            entity_id,
            start_dt.isoformat(),
            end_dt.isoformat(),
            minimal,
            verbose=state.verbose,
        )
    )

    series = (raw or {}).get(entity_id, [])
    from datetime import datetime, timezone

    def _expand(p: dict) -> dict:
        lu = p.get("lu") or p.get("last_updated")
        lc = p.get("lc") or p.get("last_changed") or lu
        out: dict = {"entity_id": entity_id}
        if "s" in p or "state" in p:
            out["state"] = p.get("s") if "s" in p else p.get("state")
        if "a" in p or "attributes" in p:
            out["attributes"] = p.get("a") if "a" in p else p.get("attributes")
        if lu is not None:
            out["last_updated"] = (
                datetime.fromtimestamp(lu, tz=timezone.utc).isoformat()
                if isinstance(lu, (int, float))
                else lu
            )
        if lc is not None:
            out["last_changed"] = (
                datetime.fromtimestamp(lc, tz=timezone.utc).isoformat()
                if isinstance(lc, (int, float))
                else lc
            )
        return out

    points = [HistoryPoint.model_validate(_expand(p)) for p in series]

    if state.output == OutputFormat.json:
        output_json([p.model_dump(exclude_none=True) for p in points])
    else:
        rows = [
            {"when": p.last_changed or p.last_updated or "", "state": p.state or ""}
            for p in points
        ]
        output_table(rows, ["when", "state"])


async def _logbook(
    start: str,
    end: str | None,
    entity_ids: list[str] | None,
    verbose: bool = False,
) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.logbook(start, end, entity_ids)


@app.command()
def logbook(
    since: Annotated[
        str, typer.Option("--since", help="Start time (1h, 30m, 2d, ISO, today)")
    ] = "1h",
    until: Annotated[str, typer.Option("--until", help="End time")] = "now",
    entity_ids: Annotated[
        Optional[list[str]],
        typer.Option("--entity", "-e", help="Filter by entity_id (repeatable)"),
    ] = None,
) -> None:
    """Show human-readable activity log."""
    from ha_tool.timeparse import parse_time
    from ha_tool.models import LogbookEntry

    try:
        start_dt = parse_time(since)
        end_dt = parse_time(until)
    except ValueError as e:
        typer.echo(f"Invalid time: {e}", err=True)
        sys.exit(1)

    raw = run_with_error_handling(
        _logbook(
            start_dt.isoformat(),
            end_dt.isoformat(),
            list(entity_ids) if entity_ids else None,
            verbose=state.verbose,
        )
    )
    entries = [LogbookEntry.model_validate(e) for e in (raw or [])]

    if state.output == OutputFormat.json:
        output_json([e.model_dump(exclude_none=True) for e in entries])
    else:
        rows = [
            {
                "when": str(e.when or ""),
                "name": e.name or "",
                "message": e.message or "",
                "entity_id": e.entity_id or "",
            }
            for e in entries
        ]
        output_table(rows, ["when", "name", "message", "entity_id"])


async def _error_log(verbose: bool = False) -> str:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.error_log()


@app.command(name="error-log")
def error_log(
    lines: Annotated[
        Optional[int], typer.Option("--lines", "-n", help="Show only last N lines")
    ] = None,
) -> None:
    """Fetch the Home Assistant error log."""
    text = run_with_error_handling(_error_log(verbose=state.verbose))
    if lines:
        text = "\n".join(text.splitlines()[-lines:])

    if state.output == OutputFormat.json:
        output_json({"log": text})
    else:
        typer.echo(text)


async def _health(verbose: bool = False) -> dict[str, dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.system_health_info()


@app.command()
def health() -> None:
    """Show system health snapshot per integration."""
    raw = run_with_error_handling(_health(verbose=state.verbose))

    if state.output == OutputFormat.json:
        output_json(raw)
    else:
        if not raw:
            typer.echo("No system health info available.")
            return
        for domain, info in sorted(raw.items()):
            typer.echo(f"─ {domain}")
            for k, v in (info or {}).items():
                typer.echo(f"  {k}: {v}")


async def _repairs(verbose: bool = False) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.list_repairs()


@app.command()
def repairs(
    include_ignored: Annotated[
        bool, typer.Option("--include-ignored", help="Include ignored issues")
    ] = False,
) -> None:
    """List active repair issues."""
    from ha_tool.models import Repair

    raw = run_with_error_handling(_repairs(verbose=state.verbose))
    items = [Repair.model_validate(i) for i in (raw or {}).get("issues", [])]
    if not include_ignored:
        items = [i for i in items if not i.ignored]

    if state.output == OutputFormat.json:
        output_json([i.model_dump(exclude_none=True) for i in items])
    else:
        rows = [i.model_dump() for i in items]
        output_table(
            rows,
            ["issue_id", "domain", "severity", "breaks_in_ha_version", "is_fixable"],
        )


async def _get_notifications(verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_notifications()


notifications_app = typer.Typer(
    help="List and dismiss persistent notifications.", no_args_is_help=True
)
app.add_typer(notifications_app, name="notifications")


@notifications_app.command(name="list")
def notifications_list() -> None:
    """List persistent notifications."""
    from ha_tool.models import Notification

    raw = run_with_error_handling(_get_notifications(verbose=state.verbose))
    raw_list = raw if isinstance(raw, list) else list((raw or {}).values())
    items = [Notification.model_validate(n) for n in raw_list]

    if state.output == OutputFormat.json:
        output_json([n.model_dump(exclude_none=True) for n in items])
    else:
        rows = [n.model_dump() for n in items]
        output_table(rows, ["notification_id", "title", "created_at"])


@notifications_app.command(name="dismiss")
def notifications_dismiss(notification_id: str) -> None:
    """Dismiss a persistent notification."""
    run_with_error_handling(
        _call_service(
            "persistent_notification",
            "dismiss",
            data={"notification_id": notification_id},
            verbose=state.verbose,
        )
    )
    if state.output == OutputFormat.json:
        output_json({"success": True, "dismissed": notification_id})
    else:
        typer.echo(f"Dismissed notification {notification_id}")


async def _watch(
    event_type: str | None,
    entity_id: str | None,
    verbose: bool = False,
) -> None:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        async for event in client.stream_events(event_type=event_type):
            data = event.get("data") or {}
            if entity_id:
                ent = data.get("entity_id")
                if isinstance(ent, str) and ent != entity_id:
                    continue
                if isinstance(ent, list) and entity_id not in ent:
                    continue
            typer.echo(
                json.dumps(
                    {
                        "event_type": event.get("event_type"),
                        "time_fired": event.get("time_fired"),
                        "origin": event.get("origin"),
                        "data": data,
                    },
                    default=str,
                )
            )


@app.command()
def watch(
    event_type: Annotated[
        Optional[str],
        typer.Option(
            "--event-type", "-t", help="Filter by event_type (e.g. state_changed)"
        ),
    ] = None,
    entity_id: Annotated[
        Optional[str],
        typer.Option("--entity", "-e", help="Filter by entity_id (client-side)"),
    ] = None,
) -> None:
    """Stream Home Assistant events as NDJSON until Ctrl-C."""
    try:
        asyncio.run(_watch(event_type, entity_id, verbose=state.verbose))
    except KeyboardInterrupt:
        sys.exit(0)
    except ConnectionError as e:
        typer.echo(f"Connection error: {e}", err=True)
        sys.exit(1)
    except PermissionError as e:
        typer.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def _list_calendars(verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.list_calendars()


async def _calendar_events(
    entity_id: str,
    start: str,
    end: str,
    verbose: bool = False,
) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.calendar_events(entity_id, start, end)


@app.command()
def calendars() -> None:
    """List available calendar entities."""
    raw = run_with_error_handling(_list_calendars(verbose=state.verbose))
    if state.output == OutputFormat.json:
        output_json(raw)
    else:
        output_table(list(raw or []), ["entity_id", "name"])


@app.command()
def calendar(
    entity_id: str,
    start: Annotated[
        str, typer.Option("--start", help="Start time (now, ISO, today)")
    ] = "now",
    end: Annotated[
        str,
        typer.Option(
            "--end", help="End time (relative offset from start, ISO, or keyword)"
        ),
    ] = "7d",
) -> None:
    """Show calendar events for a calendar entity over a window."""
    from datetime import timedelta
    from ha_tool.timeparse import parse_time, parse_duration_seconds
    from ha_tool.models import CalendarEvent

    try:
        start_dt = parse_time(start)
        offset = parse_duration_seconds(end)
        if offset is not None:
            end_dt = start_dt + timedelta(seconds=offset)
        else:
            end_dt = parse_time(end)
    except ValueError as e:
        typer.echo(f"Invalid time: {e}", err=True)
        sys.exit(1)

    raw = run_with_error_handling(
        _calendar_events(
            entity_id,
            start_dt.isoformat(),
            end_dt.isoformat(),
            verbose=state.verbose,
        )
    )
    items = [CalendarEvent.model_validate(e) for e in (raw or [])]

    if state.output == OutputFormat.json:
        output_json([e.model_dump(exclude_none=True) for e in items])
    else:

        def _fmt(v: dict | str | None) -> str:
            if isinstance(v, dict):
                return str(v.get("dateTime") or v.get("date") or "")
            return str(v or "")

        rows = [
            {
                "start": _fmt(e.start),
                "end": _fmt(e.end),
                "summary": e.summary or "",
                "location": e.location or "",
            }
            for e in items
        ]
        output_table(rows, ["start", "end", "summary", "location"])


async def _check_config(verbose: bool = False) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.check_config()


@app.command(name="check-config")
def check_config() -> None:
    """Validate Home Assistant configuration.yaml.

    Calls the REST endpoint /api/config/core/check_config. Returns
    {"result": "valid"|"invalid", "errors": ..., "warnings": ...}.
    Exits with code 1 if invalid.
    """
    result = run_with_error_handling(_check_config(verbose=state.verbose))
    valid = isinstance(result, dict) and result.get("result") == "valid"

    if state.output == OutputFormat.json:
        output_json(result)
    else:
        if valid:
            typer.echo("Configuration valid.")
        else:
            typer.echo("Configuration INVALID.", err=True)
            errors = result.get("errors") if isinstance(result, dict) else None
            warnings = result.get("warnings") if isinstance(result, dict) else None
            if errors:
                typer.echo(f"Errors:\n{errors}", err=True)
            if warnings:
                typer.echo(f"Warnings:\n{warnings}", err=True)

    if not valid:
        sys.exit(1)


async def _lovelace_refresh(
    url_paths: tuple[str, ...],
    verbose: bool = False,
) -> list[dict]:
    """Refresh YAML-mode Lovelace dashboards by forcing a re-read from disk.

    With no explicit url_paths, discovers all yaml-mode dashboards via
    lovelace/dashboards/list and also refreshes the built-in default
    dashboard. The literal "default" refers to that null-path dashboard.

    Returns a list of per-dashboard result dicts:
    {"url_path": "default"|<path>, "success": bool, "error": str|None}.
    """
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        # Build the list of (label, ws_path) targets.
        targets: list[tuple[str, str | None]] = []
        if url_paths:
            for p in url_paths:
                targets.append(("default", None) if p == "default" else (p, p))
        else:
            dashboards = await client.list_lovelace_dashboards()
            for d in dashboards:
                if d.get("mode") == "yaml" and d.get("url_path"):
                    path = d["url_path"]
                    targets.append((path, path))
            # Always include the built-in default dashboard.
            targets.append(("default", None))

        results: list[dict] = []
        for label, ws_path in targets:
            try:
                await client.reload_lovelace_config(ws_path)
                results.append({"url_path": label, "success": True, "error": None})
            except RuntimeError as e:
                results.append({"url_path": label, "success": False, "error": str(e)})
        return results


@app.command(name="lovelace-refresh")
def lovelace_refresh(
    url_paths: Annotated[Optional[list[str]], typer.Argument()] = None,
) -> None:
    """Reload YAML-mode Lovelace dashboards from disk into the server cache.

    Home Assistant caches parsed YAML dashboards in memory; replacing the
    file on disk is invisible to clients until the cache is refreshed. This
    sends lovelace/config with force=true to re-read each dashboard.

    With no arguments, discovers all yaml-mode dashboards and also refreshes
    the built-in default dashboard. Pass explicit URL_PATHS to refresh
    specific dashboards; use the literal "default" for the default dashboard.

    Exits 1 if any dashboard fails to refresh.
    """
    results = run_with_error_handling(
        _lovelace_refresh(tuple(url_paths or ()), verbose=state.verbose)
    )

    if state.output == OutputFormat.json:
        output_json(results)
    else:
        for r in results:
            mark = "✓" if r["success"] else "✗"
            line = f"  {mark} {r['url_path']}"
            if not r["success"] and r.get("error"):
                line += f"  ({r['error']})"
            typer.echo(line)
        ok = sum(1 for r in results if r["success"])
        failed = len(results) - ok
        typer.echo("")
        typer.echo(f"Refreshed {ok} dashboard(s), {failed} failed.")

    if any(not r["success"] for r in results):
        sys.exit(1)


async def _remove_entity(entity_id: str, verbose: bool = False) -> dict | None:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.remove_entity(entity_id)


async def _rename_entity(
    entity_id: str, new_entity_id: str, verbose: bool = False
) -> dict | None:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.rename_entity(entity_id, new_entity_id)


async def _remove_device(
    device_id: str, config_entry_id: str, verbose: bool = False
) -> dict | None:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.remove_device(device_id, config_entry_id)


async def _remove_config_entry(entry_id: str, verbose: bool = False) -> dict | None:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.remove_config_entry(entry_id)


@app.command(name="remove-entity")
def remove_entity(
    entity_id: str,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Remove an entity from the entity registry.

    Only works for entities without a unique_id constraint (e.g. helpers,
    manually-added entities). Integration-provided entities must be removed
    via their device or config entry.
    """
    if not yes and state.output != OutputFormat.json:
        if not typer.confirm(f"Remove entity '{entity_id}'? This cannot be undone."):
            typer.echo("Aborted.")
            return

    run_with_error_handling(_remove_entity(entity_id, verbose=state.verbose))

    if state.output == OutputFormat.json:
        output_json({"success": True, "removed": entity_id})
    else:
        typer.echo(f"Removed entity {entity_id}")


@app.command(name="rename-entity")
def rename_entity(entity_id: str, new_entity_id: str) -> None:
    """Change an entity's entity_id in the entity registry.

    Works for any registered entity regardless of integration; the registry
    keeps the override keyed by unique_id. NEW_ENTITY_ID must be in the same
    domain (e.g. switch.foo -> switch.bar) and not already in use.
    """
    result = run_with_error_handling(
        _rename_entity(entity_id, new_entity_id, verbose=state.verbose)
    )

    effective = new_entity_id
    if isinstance(result, dict):
        entry = result.get("entity_entry", result)
        if isinstance(entry, dict):
            effective = entry.get("entity_id", new_entity_id)

    if state.output == OutputFormat.json:
        output_json(
            {
                "success": True,
                "from": entity_id,
                "to": effective,
            }
        )
    else:
        typer.echo(f"Renamed {entity_id} -> {effective}")


@app.command(name="remove-device")
def remove_device(
    device_id: str,
    config_entry_id: str,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Disassociate a device from a config entry.

    Device is removed when its last config entry association is removed.
    DEVICE_ID and CONFIG_ENTRY_ID come from the device/config entry registries.
    """
    if not yes and state.output != OutputFormat.json:
        if not typer.confirm(
            f"Remove device '{device_id}' from config entry '{config_entry_id}'? This cannot be undone."
        ):
            typer.echo("Aborted.")
            return

    run_with_error_handling(
        _remove_device(device_id, config_entry_id, verbose=state.verbose)
    )

    if state.output == OutputFormat.json:
        output_json(
            {
                "success": True,
                "removed_device": device_id,
                "config_entry_id": config_entry_id,
            }
        )
    else:
        typer.echo(f"Removed device {device_id} from config entry {config_entry_id}")


@app.command(name="remove-config-entry")
def remove_config_entry(
    entry_id: str,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Remove an integration config entry.

    Removes the integration entry along with its associated devices and
    entities. ENTRY_ID is the config entry's internal id.
    """
    if not yes and state.output != OutputFormat.json:
        if not typer.confirm(
            f"Remove config entry '{entry_id}'? This will delete the integration and its entities. This cannot be undone."
        ):
            typer.echo("Aborted.")
            return

    result = run_with_error_handling(
        _remove_config_entry(entry_id, verbose=state.verbose)
    )

    if state.output == OutputFormat.json:
        output_json({"success": True, "removed_entry": entry_id, "result": result})
    else:
        typer.echo(f"Removed config entry {entry_id}")
        if result and isinstance(result, dict) and result.get("require_restart"):
            typer.echo("Restart required to complete removal.")


def main() -> None:
    app()


@app.command()
def verify(
    files: Annotated[list[Path], typer.Argument(exists=True)],
    filter_mode: Annotated[
        FilterMode, typer.Option("--filter", "-f", help="Filter results")
    ] = FilterMode.all,
) -> None:
    """Verify entity references in files exist in Home Assistant.

    Extracts all entity patterns (e.g. sensor.pool_temp, light.kitchen)
    from the given files and checks each against the live HA instance.
    """
    index = run_with_error_handling(
        build_index(include_services=True, verbose=state.verbose)
    )

    all_refs: list[dict] = []
    for filepath in files:
        with open(filepath) as f:
            content = f.read()
        refs = index.extract_and_verify(str(filepath), content)
        for r in refs:
            if filter_mode == FilterMode.missing and r.exists:
                continue
            if filter_mode == FilterMode.existing and not r.exists:
                continue
            all_refs.append(r.model_dump(exclude_none=True))

    if state.output == OutputFormat.json:
        output_json(all_refs)
    else:
        if not all_refs:
            if filter_mode == FilterMode.missing:
                typer.echo("All entity references are valid.")
            elif filter_mode == FilterMode.existing:
                typer.echo("No existing entity references found.")
            else:
                typer.echo("No entity references found.")
            return

        for ref in all_refs:
            status = "✓" if ref["exists"] else "✗"
            name = ref.get("friendly_name", "")
            name_str = f"  ({name})" if name else ""
            typer.echo(
                f"  {status} {ref['file']}:{ref['line']}  {ref['entity_id']}{name_str}"
            )

        missing = sum(1 for r in all_refs if not r["exists"])
        found = sum(1 for r in all_refs if r["exists"])

        typer.echo("")
        typer.echo(f"{found} valid, {missing} missing ({found + missing} total)")
