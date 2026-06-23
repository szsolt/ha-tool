from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import click

from ha_tool import __version__
from ha_tool.client import HAWebSocketClient
from ha_tool.registry import EntityIndex


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
        click.echo("Missing required environment variables:", err=True)
        for m in missing:
            click.echo(f"  {m}", err=True)
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
    click.echo(json.dumps(data, indent=2, default=str))


def output_table(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        click.echo("No results found.")
        return

    col_widths: dict[str, int] = {}
    for col in columns:
        max_val = max((len(str(row.get(col, "") or "")) for row in rows), default=0)
        col_widths[col] = max(len(col), min(max_val, 60))

    header = "  ".join(col.upper().ljust(col_widths[col]) for col in columns)
    click.echo(header)
    click.echo("  ".join("─" * col_widths[col] for col in columns))

    for row in rows:
        vals: list[str] = []
        for col in columns:
            v = str(row.get(col, "") or "")
            if len(v) > 60:
                v = v[:57] + "..."
            vals.append(v.ljust(col_widths[col]))
        click.echo("  ".join(vals))

    click.echo(f"\n({len(rows)} results)")


def run_with_error_handling(coro: Any) -> Any:
    """Run an async coroutine with user-friendly error handling."""
    try:
        return asyncio.run(coro)
    except ConnectionError as e:
        click.echo(f"Connection error: {e}", err=True)
        sys.exit(1)
    except PermissionError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.group()
@click.version_option(__version__, prog_name="ha-tool")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["human", "json"]),
    default="human",
    help="Output format",
)
@click.option("--verbose", "-v", is_flag=True, help="Show debug output on stderr")
@click.pass_context
def cli(ctx: click.Context, output: str, verbose: bool) -> None:
    """Home Assistant entity discovery tool for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["output"] = output
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("text", required=False)
@click.option("--domain", "-d", help="Filter by domain (e.g. sensor, climate, light)")
@click.option(
    "--device-class", "-c", help="Filter by device_class (e.g. temperature, motion)"
)
@click.option("--area", "-a", help="Filter by area name (substring match)")
@click.option(
    "--integration",
    "-i",
    help="Filter by integration/platform (e.g. hue, zwave_js, mqtt)",
)
@click.option("--include-disabled", is_flag=True, help="Include disabled entities")
@click.pass_context
def search(
    ctx: click.Context,
    text: str | None,
    domain: str | None,
    device_class: str | None,
    area: str | None,
    integration: str | None,
    include_disabled: bool,
) -> None:
    """Search for entities by name, domain, device_class, area, or integration.

    TEXT supports substring, glob (* ?), and regex ([0-9], |, etc.) patterns.
    """
    index = run_with_error_handling(build_index(verbose=ctx.obj["verbose"]))
    results = index.search(
        text=text,
        domain=domain,
        device_class=device_class,
        area=area,
        integration=integration,
        include_disabled=include_disabled,
    )

    if ctx.obj["output"] == "json":
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


@cli.command()
@click.argument("entity_ids", nargs=-1, required=True)
@click.pass_context
def inspect(ctx: click.Context, entity_ids: tuple[str, ...]) -> None:
    """Get full details for one or more entities."""
    index = run_with_error_handling(build_index(verbose=ctx.obj["verbose"]))
    results = index.inspect(list(entity_ids))

    if ctx.obj["output"] == "json":
        output_json([r.model_dump(exclude_none=True) for r in results])
    else:
        for r in results:
            click.echo(f"{'─' * 60}")
            click.echo(f"Entity:       {r.entity_id}")
            click.echo(f"Name:         {r.friendly_name or '—'}")
            click.echo(f"Domain:       {r.domain}")
            click.echo(f"Platform:     {r.platform or '—'}")
            click.echo(f"Device Class: {r.device_class or '—'}")
            click.echo(f"Area:         {r.area or '—'}")
            click.echo(f"State:        {r.state or '—'}")
            click.echo(f"Last Changed: {r.last_changed or '—'}")
            click.echo(f"Device:       {r.device_name or '—'}")
            click.echo(f"Manufacturer: {r.device_manufacturer or '—'}")
            click.echo(f"Model:        {r.device_model or '—'}")
            click.echo(f"Category:     {r.entity_category or '—'}")
            click.echo(f"Labels:       {', '.join(r.labels) if r.labels else '—'}")
            if r.attributes:
                click.echo("Attributes:")
                for k, v in sorted(r.attributes.items()):
                    click.echo(f"  {k}: {v}")
        click.echo(f"{'─' * 60}")
        click.echo(f"({len(results)} entities)")


@cli.command()
@click.argument("entity_id")
@click.pass_context
def get(ctx: click.Context, entity_id: str) -> None:
    """Get current state of a single entity (minimal output)."""
    index = run_with_error_handling(build_index(verbose=ctx.obj["verbose"]))
    result = index.get_state(entity_id)

    if result is None:
        if ctx.obj["output"] == "json":
            output_json({"error": f"Entity '{entity_id}' not found"})
        else:
            click.echo(f"Entity '{entity_id}' not found.", err=True)
        sys.exit(1)

    if ctx.obj["output"] == "json":
        output_json(result)
    else:
        click.echo(
            f"{result['entity_id']}  {result['friendly_name'] or '—'}  {result['state']}"
        )


@cli.command()
@click.pass_context
def areas(ctx: click.Context) -> None:
    """List all configured areas."""
    index = run_with_error_handling(build_index(verbose=ctx.obj["verbose"]))
    result = index.list_areas()

    if ctx.obj["output"] == "json":
        output_json([a.model_dump(exclude_none=True) for a in result])
    else:
        rows = [a.model_dump() for a in result]
        output_table(rows, ["area_id", "name", "floor_id"])


@cli.command()
@click.pass_context
def domains(ctx: click.Context) -> None:
    """List all entity domains with entity counts."""
    index = run_with_error_handling(build_index(verbose=ctx.obj["verbose"]))
    result = index.list_domains()

    if ctx.obj["output"] == "json":
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


@cli.command()
@click.pass_context
def integrations(ctx: click.Context) -> None:
    """List all integrations with entity counts."""
    index = run_with_error_handling(build_index(verbose=ctx.obj["verbose"]))
    result = index.list_integrations()

    if ctx.obj["output"] == "json":
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


@cli.command()
@click.argument("text", required=False)
@click.option("--domain", "-d", help="Filter by service domain (e.g. light, climate)")
@click.pass_context
def services(ctx: click.Context, text: str | None, domain: str | None) -> None:
    """List or search available service actions."""
    index = run_with_error_handling(
        build_index(include_services=True, verbose=ctx.obj["verbose"])
    )
    results = index.search_services(text=text, domain=domain)

    if ctx.obj["output"] == "json":
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


@cli.command(name="call")
@click.argument("service_name")
@click.option("--data", "-d", "data_json", help="Service data as JSON object")
@click.option(
    "--target",
    "-t",
    "target_json",
    help="Target as JSON (entity_id, device_id, or area_id)",
)
@click.pass_context
def call_service(
    ctx: click.Context,
    service_name: str,
    data_json: str | None,
    target_json: str | None,
) -> None:
    """Call a Home Assistant service.

    SERVICE_NAME is in the format domain.service (e.g. light.turn_on, automation.reload).
    """
    if "." not in service_name:
        click.echo(
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
            click.echo(f"Invalid JSON for --data: {e}", err=True)
            sys.exit(1)

    if target_json:
        try:
            target = json.loads(target_json)
        except json.JSONDecodeError as e:
            click.echo(f"Invalid JSON for --target: {e}", err=True)
            sys.exit(1)

    result = run_with_error_handling(
        _call_service(domain, service, data, target, verbose=ctx.obj["verbose"])
    )

    if ctx.obj["output"] == "json":
        output_json({"success": True, "service": service_name, "result": result})
    else:
        click.echo(f"Called {service_name}")


@cli.command()
@click.argument("domain", required=False)
@click.pass_context
def reload(ctx: click.Context, domain: str | None) -> None:
    """Reload Home Assistant configuration.

    DOMAIN can be: automations, scripts, scenes, groups, all, or any reloadable domain.
    Without arguments, shows available reload options.
    """
    if domain is None:
        if ctx.obj["output"] == "json":
            output_json({"available_domains": ["all"] + RELOAD_DOMAINS})
        else:
            click.echo("Available reload domains:")
            click.echo("  all — Reload all configuration")
            for d in RELOAD_DOMAINS:
                click.echo(f"  {d}")
        return

    domain = domain.lower().rstrip("s")  # Allow "automations" -> "automation"

    if domain == "all":
        run_with_error_handling(
            _call_service("homeassistant", "reload_all", verbose=ctx.obj["verbose"])
        )
        if ctx.obj["output"] == "json":
            output_json({"success": True, "reloaded": "all"})
        else:
            click.echo("Reloaded all configuration")
    elif domain in RELOAD_DOMAINS:
        run_with_error_handling(
            _call_service(domain, "reload", verbose=ctx.obj["verbose"])
        )
        if ctx.obj["output"] == "json":
            output_json({"success": True, "reloaded": domain})
        else:
            click.echo(f"Reloaded {domain}")
    else:
        click.echo(
            f"Unknown reload domain '{domain}'. Use 'ha-tool reload' to see options.",
            err=True,
        )
        sys.exit(1)


@cli.command()
@click.option("--confirm", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def restart(ctx: click.Context, confirm: bool) -> None:
    """Restart Home Assistant."""
    if not confirm and ctx.obj["output"] != "json":
        if not click.confirm("Are you sure you want to restart Home Assistant?"):
            click.echo("Aborted.")
            return

    try:
        asyncio.run(
            _call_service("homeassistant", "restart", verbose=ctx.obj["verbose"])
        )
    except ConnectionError:
        pass
    except PermissionError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if ctx.obj["output"] == "json":
        output_json({"success": True, "action": "restart"})
    else:
        click.echo("Home Assistant is restarting...")


@cli.command()
@click.argument("template_str")
@click.pass_context
def template(ctx: click.Context, template_str: str) -> None:
    """Render a Jinja2 template.

    TEMPLATE_STR is a Jinja2 template string, e.g. '{{ states("sensor.temperature") }}'.
    """
    result = run_with_error_handling(
        _render_template(template_str, verbose=ctx.obj["verbose"])
    )

    if ctx.obj["output"] == "json":
        output_json({"template": template_str, "result": result})
    else:
        click.echo(result)


async def _get_core_config(verbose: bool = False) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_core_config()


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show Home Assistant core configuration (version, location, units)."""
    from ha_tool.models import CoreConfig

    raw = run_with_error_handling(_get_core_config(verbose=ctx.obj["verbose"]))
    cfg = CoreConfig.model_validate(raw)

    if ctx.obj["output"] == "json":
        output_json(cfg.model_dump(exclude_none=True))
    else:
        click.echo(f"Version:      {cfg.version or '—'}")
        click.echo(f"Location:     {cfg.location_name or '—'}")
        click.echo(f"Coordinates:  {cfg.latitude}, {cfg.longitude}")
        click.echo(f"Elevation:    {cfg.elevation}")
        click.echo(f"Time zone:    {cfg.time_zone or '—'}")
        click.echo(f"Currency:     {cfg.currency or '—'}")
        click.echo(f"Country:      {cfg.country or '—'}")
        click.echo(f"Language:     {cfg.language or '—'}")
        click.echo(f"Safe mode:    {cfg.safe_mode}")
        click.echo(f"State:        {cfg.state or '—'}")
        click.echo(f"Components:   {len(cfg.components)} loaded")


async def _get_panels(verbose: bool = False) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_panels()


@cli.command()
@click.pass_context
def panels(ctx: click.Context) -> None:
    """List registered UI panels."""
    from ha_tool.models import Panel

    raw = run_with_error_handling(_get_panels(verbose=ctx.obj["verbose"]))
    items = [Panel.model_validate(v) for v in (raw or {}).values()]

    if ctx.obj["output"] == "json":
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


@cli.command(name="config-entries")
@click.option("--domain", "-d", help="Filter by integration domain")
@click.pass_context
def config_entries(ctx: click.Context, domain: str | None) -> None:
    """List integration config entries."""
    from ha_tool.models import ConfigEntry

    raw = run_with_error_handling(_get_config_entries(verbose=ctx.obj["verbose"]))
    items = [ConfigEntry.model_validate(e) for e in (raw or [])]
    if domain:
        items = [e for e in items if e.domain == domain]

    if ctx.obj["output"] == "json":
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


@cli.command()
@click.pass_context
def labels(ctx: click.Context) -> None:
    """List configured labels."""
    from ha_tool.models import Label

    raw = run_with_error_handling(_get_labels(verbose=ctx.obj["verbose"]))
    items = [Label.model_validate(item) for item in (raw or [])]

    if ctx.obj["output"] == "json":
        output_json([item.model_dump(exclude_none=True) for item in items])
    else:
        rows = [item.model_dump() for item in items]
        output_table(rows, ["label_id", "name", "color", "icon", "description"])


async def _get_floors(verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_floor_registry()


@cli.command()
@click.pass_context
def floors(ctx: click.Context) -> None:
    """List configured floors."""
    from ha_tool.models import Floor

    raw = run_with_error_handling(_get_floors(verbose=ctx.obj["verbose"]))
    items = [Floor.model_validate(f) for f in (raw or [])]

    if ctx.obj["output"] == "json":
        output_json([f.model_dump(exclude_none=True) for f in items])
    else:
        rows = [f.model_dump() for f in items]
        output_table(rows, ["floor_id", "name", "level", "icon"])


async def _get_categories(scope: str, verbose: bool = False) -> list[dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.get_category_registry(scope)


@cli.command()
@click.argument("scope", default="automation")
@click.pass_context
def categories(ctx: click.Context, scope: str) -> None:
    """List categories for a scope (e.g. automation, script, scene)."""
    from ha_tool.models import Category

    raw = run_with_error_handling(_get_categories(scope, verbose=ctx.obj["verbose"]))
    items = [Category.model_validate({**c, "scope": scope}) for c in (raw or [])]

    if ctx.obj["output"] == "json":
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


@cli.command()
@click.argument("entity_id")
@click.option("--since", default="1h", help="Start time (1h, 30m, 2d, ISO, today)")
@click.option("--until", default="now", help="End time (now, ISO)")
@click.option("--minimal", is_flag=True, help="Strip attributes for smaller payload")
@click.pass_context
def history(
    ctx: click.Context, entity_id: str, since: str, until: str, minimal: bool
) -> None:
    """Show state history of an entity over a time window."""
    from ha_tool.timeparse import parse_time
    from ha_tool.models import HistoryPoint

    try:
        start_dt = parse_time(since)
        end_dt = parse_time(until)
    except ValueError as e:
        click.echo(f"Invalid time: {e}", err=True)
        sys.exit(1)

    raw = run_with_error_handling(
        _history(
            entity_id,
            start_dt.isoformat(),
            end_dt.isoformat(),
            minimal,
            verbose=ctx.obj["verbose"],
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

    if ctx.obj["output"] == "json":
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


@cli.command()
@click.option("--since", default="1h", help="Start time (1h, 30m, 2d, ISO, today)")
@click.option("--until", default="now", help="End time")
@click.option(
    "--entity",
    "-e",
    "entity_ids",
    multiple=True,
    help="Filter by entity_id (repeatable)",
)
@click.pass_context
def logbook(
    ctx: click.Context, since: str, until: str, entity_ids: tuple[str, ...]
) -> None:
    """Show human-readable activity log."""
    from ha_tool.timeparse import parse_time
    from ha_tool.models import LogbookEntry

    try:
        start_dt = parse_time(since)
        end_dt = parse_time(until)
    except ValueError as e:
        click.echo(f"Invalid time: {e}", err=True)
        sys.exit(1)

    raw = run_with_error_handling(
        _logbook(
            start_dt.isoformat(),
            end_dt.isoformat(),
            list(entity_ids) if entity_ids else None,
            verbose=ctx.obj["verbose"],
        )
    )
    entries = [LogbookEntry.model_validate(e) for e in (raw or [])]

    if ctx.obj["output"] == "json":
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


@cli.command(name="error-log")
@click.option("--lines", "-n", type=int, help="Show only last N lines")
@click.pass_context
def error_log(ctx: click.Context, lines: int | None) -> None:
    """Fetch the Home Assistant error log."""
    text = run_with_error_handling(_error_log(verbose=ctx.obj["verbose"]))
    if lines:
        text = "\n".join(text.splitlines()[-lines:])

    if ctx.obj["output"] == "json":
        output_json({"log": text})
    else:
        click.echo(text)


async def _health(verbose: bool = False) -> dict[str, dict]:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.system_health_info()


@cli.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Show system health snapshot per integration."""
    raw = run_with_error_handling(_health(verbose=ctx.obj["verbose"]))

    if ctx.obj["output"] == "json":
        output_json(raw)
    else:
        if not raw:
            click.echo("No system health info available.")
            return
        for domain, info in sorted(raw.items()):
            click.echo(f"─ {domain}")
            for k, v in (info or {}).items():
                click.echo(f"  {k}: {v}")


async def _repairs(verbose: bool = False) -> dict:
    url, token = get_config()
    async with HAWebSocketClient(url, token, verbose=verbose) as client:
        return await client.list_repairs()


@cli.command()
@click.option("--include-ignored", is_flag=True, help="Include ignored issues")
@click.pass_context
def repairs(ctx: click.Context, include_ignored: bool) -> None:
    """List active repair issues."""
    from ha_tool.models import Repair

    raw = run_with_error_handling(_repairs(verbose=ctx.obj["verbose"]))
    items = [Repair.model_validate(i) for i in (raw or {}).get("issues", [])]
    if not include_ignored:
        items = [i for i in items if not i.ignored]

    if ctx.obj["output"] == "json":
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


@cli.group()
def notifications() -> None:
    """List and dismiss persistent notifications."""


@notifications.command(name="list")
@click.pass_context
def notifications_list(ctx: click.Context) -> None:
    """List persistent notifications."""
    from ha_tool.models import Notification

    raw = run_with_error_handling(_get_notifications(verbose=ctx.obj["verbose"]))
    raw_list = raw if isinstance(raw, list) else list((raw or {}).values())
    items = [Notification.model_validate(n) for n in raw_list]

    if ctx.obj["output"] == "json":
        output_json([n.model_dump(exclude_none=True) for n in items])
    else:
        rows = [n.model_dump() for n in items]
        output_table(rows, ["notification_id", "title", "created_at"])


@notifications.command(name="dismiss")
@click.argument("notification_id")
@click.pass_context
def notifications_dismiss(ctx: click.Context, notification_id: str) -> None:
    """Dismiss a persistent notification."""
    run_with_error_handling(
        _call_service(
            "persistent_notification",
            "dismiss",
            data={"notification_id": notification_id},
            verbose=ctx.obj["verbose"],
        )
    )
    if ctx.obj["output"] == "json":
        output_json({"success": True, "dismissed": notification_id})
    else:
        click.echo(f"Dismissed notification {notification_id}")


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
            click.echo(
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


@cli.command()
@click.option("--event-type", "-t", help="Filter by event_type (e.g. state_changed)")
@click.option("--entity", "-e", "entity_id", help="Filter by entity_id (client-side)")
@click.pass_context
def watch(ctx: click.Context, event_type: str | None, entity_id: str | None) -> None:
    """Stream Home Assistant events as NDJSON until Ctrl-C."""
    try:
        asyncio.run(_watch(event_type, entity_id, verbose=ctx.obj["verbose"]))
    except KeyboardInterrupt:
        sys.exit(0)
    except ConnectionError as e:
        click.echo(f"Connection error: {e}", err=True)
        sys.exit(1)
    except PermissionError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
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


@cli.command()
@click.pass_context
def calendars(ctx: click.Context) -> None:
    """List available calendar entities."""
    raw = run_with_error_handling(_list_calendars(verbose=ctx.obj["verbose"]))
    if ctx.obj["output"] == "json":
        output_json(raw)
    else:
        output_table(list(raw or []), ["entity_id", "name"])


@cli.command()
@click.argument("entity_id")
@click.option("--start", default="now", help="Start time (now, ISO, today)")
@click.option(
    "--end", default="7d", help="End time (relative offset from start, ISO, or keyword)"
)
@click.pass_context
def calendar(ctx: click.Context, entity_id: str, start: str, end: str) -> None:
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
        click.echo(f"Invalid time: {e}", err=True)
        sys.exit(1)

    raw = run_with_error_handling(
        _calendar_events(
            entity_id,
            start_dt.isoformat(),
            end_dt.isoformat(),
            verbose=ctx.obj["verbose"],
        )
    )
    items = [CalendarEvent.model_validate(e) for e in (raw or [])]

    if ctx.obj["output"] == "json":
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


@cli.command(name="check-config")
@click.pass_context
def check_config(ctx: click.Context) -> None:
    """Validate Home Assistant configuration.yaml.

    Calls the REST endpoint /api/config/core/check_config. Returns
    {"result": "valid"|"invalid", "errors": ..., "warnings": ...}.
    Exits with code 1 if invalid.
    """
    result = run_with_error_handling(_check_config(verbose=ctx.obj["verbose"]))
    valid = isinstance(result, dict) and result.get("result") == "valid"

    if ctx.obj["output"] == "json":
        output_json(result)
    else:
        if valid:
            click.echo("Configuration valid.")
        else:
            click.echo("Configuration INVALID.", err=True)
            errors = result.get("errors") if isinstance(result, dict) else None
            warnings = result.get("warnings") if isinstance(result, dict) else None
            if errors:
                click.echo(f"Errors:\n{errors}", err=True)
            if warnings:
                click.echo(f"Warnings:\n{warnings}", err=True)

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


@cli.command(name="lovelace-refresh")
@click.argument("url_paths", nargs=-1, required=False)
@click.pass_context
def lovelace_refresh(ctx: click.Context, url_paths: tuple[str, ...]) -> None:
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
        _lovelace_refresh(url_paths, verbose=ctx.obj["verbose"])
    )

    if ctx.obj["output"] == "json":
        output_json(results)
    else:
        for r in results:
            mark = "✓" if r["success"] else "✗"
            line = f"  {mark} {r['url_path']}"
            if not r["success"] and r.get("error"):
                line += f"  ({r['error']})"
            click.echo(line)
        ok = sum(1 for r in results if r["success"])
        failed = len(results) - ok
        click.echo("")
        click.echo(f"Refreshed {ok} dashboard(s), {failed} failed.")

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


@cli.command(name="remove-entity")
@click.argument("entity_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def remove_entity(ctx: click.Context, entity_id: str, yes: bool) -> None:
    """Remove an entity from the entity registry.

    Only works for entities without a unique_id constraint (e.g. helpers,
    manually-added entities). Integration-provided entities must be removed
    via their device or config entry.
    """
    if not yes and ctx.obj["output"] != "json":
        if not click.confirm(f"Remove entity '{entity_id}'? This cannot be undone."):
            click.echo("Aborted.")
            return

    run_with_error_handling(_remove_entity(entity_id, verbose=ctx.obj["verbose"]))

    if ctx.obj["output"] == "json":
        output_json({"success": True, "removed": entity_id})
    else:
        click.echo(f"Removed entity {entity_id}")


@cli.command(name="rename-entity")
@click.argument("entity_id")
@click.argument("new_entity_id")
@click.pass_context
def rename_entity(ctx: click.Context, entity_id: str, new_entity_id: str) -> None:
    """Change an entity's entity_id in the entity registry.

    Works for any registered entity regardless of integration; the registry
    keeps the override keyed by unique_id. NEW_ENTITY_ID must be in the same
    domain (e.g. switch.foo -> switch.bar) and not already in use.
    """
    result = run_with_error_handling(
        _rename_entity(entity_id, new_entity_id, verbose=ctx.obj["verbose"])
    )

    effective = new_entity_id
    if isinstance(result, dict):
        entry = result.get("entity_entry", result)
        if isinstance(entry, dict):
            effective = entry.get("entity_id", new_entity_id)

    if ctx.obj["output"] == "json":
        output_json(
            {
                "success": True,
                "from": entity_id,
                "to": effective,
            }
        )
    else:
        click.echo(f"Renamed {entity_id} -> {effective}")


@cli.command(name="remove-device")
@click.argument("device_id")
@click.argument("config_entry_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def remove_device(
    ctx: click.Context, device_id: str, config_entry_id: str, yes: bool
) -> None:
    """Disassociate a device from a config entry.

    Device is removed when its last config entry association is removed.
    DEVICE_ID and CONFIG_ENTRY_ID come from the device/config entry registries.
    """
    if not yes and ctx.obj["output"] != "json":
        if not click.confirm(
            f"Remove device '{device_id}' from config entry '{config_entry_id}'? This cannot be undone."
        ):
            click.echo("Aborted.")
            return

    run_with_error_handling(
        _remove_device(device_id, config_entry_id, verbose=ctx.obj["verbose"])
    )

    if ctx.obj["output"] == "json":
        output_json(
            {
                "success": True,
                "removed_device": device_id,
                "config_entry_id": config_entry_id,
            }
        )
    else:
        click.echo(f"Removed device {device_id} from config entry {config_entry_id}")


@cli.command(name="remove-config-entry")
@click.argument("entry_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def remove_config_entry(ctx: click.Context, entry_id: str, yes: bool) -> None:
    """Remove an integration config entry.

    Removes the integration entry along with its associated devices and
    entities. ENTRY_ID is the config entry's internal id.
    """
    if not yes and ctx.obj["output"] != "json":
        if not click.confirm(
            f"Remove config entry '{entry_id}'? This will delete the integration and its entities. This cannot be undone."
        ):
            click.echo("Aborted.")
            return

    result = run_with_error_handling(
        _remove_config_entry(entry_id, verbose=ctx.obj["verbose"])
    )

    if ctx.obj["output"] == "json":
        output_json({"success": True, "removed_entry": entry_id, "result": result})
    else:
        click.echo(f"Removed config entry {entry_id}")
        if result and isinstance(result, dict) and result.get("require_restart"):
            click.echo("Restart required to complete removal.")


def main() -> None:
    cli()


@cli.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--filter",
    "-f",
    "filter_mode",
    type=click.Choice(["all", "missing", "existing"]),
    default="all",
    help="Filter results",
)
@click.pass_context
def verify(ctx: click.Context, files: tuple[str, ...], filter_mode: str) -> None:
    """Verify entity references in files exist in Home Assistant.

    Extracts all entity patterns (e.g. sensor.pool_temp, light.kitchen)
    from the given files and checks each against the live HA instance.
    """
    index = run_with_error_handling(
        build_index(include_services=True, verbose=ctx.obj["verbose"])
    )

    all_refs: list[dict] = []
    for filepath in files:
        with open(filepath) as f:
            content = f.read()
        refs = index.extract_and_verify(filepath, content)
        for r in refs:
            if filter_mode == "missing" and r.exists:
                continue
            if filter_mode == "existing" and not r.exists:
                continue
            all_refs.append(r.model_dump(exclude_none=True))

    if ctx.obj["output"] == "json":
        output_json(all_refs)
    else:
        if not all_refs:
            if filter_mode == "missing":
                click.echo("All entity references are valid.")
            elif filter_mode == "existing":
                click.echo("No existing entity references found.")
            else:
                click.echo("No entity references found.")
            return

        for ref in all_refs:
            status = "✓" if ref["exists"] else "✗"
            name = ref.get("friendly_name", "")
            name_str = f"  ({name})" if name else ""
            click.echo(
                f"  {status} {ref['file']}:{ref['line']}  {ref['entity_id']}{name_str}"
            )

        missing = sum(1 for r in all_refs if not r["exists"])
        found = sum(1 for r in all_refs if r["exists"])

        click.echo("")
        click.echo(f"{found} valid, {missing} missing ({found + missing} total)")
