from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import click

from ha_tool.client import HAWebSocketClient
from ha_tool.registry import EntityIndex


def get_config() -> tuple[str, str]:
    url = os.environ.get("HASS_SERVER") or os.environ.get("HASS_URL", "")
    token = os.environ.get("HASS_TOKEN", "")
    missing: list[str] = []
    if not url:
        missing.append("HASS_SERVER  (e.g. export HASS_SERVER=http://homeassistant.local:8123)")
    if not token:
        missing.append("HASS_TOKEN   (Profile → Security → Long-Lived Access Tokens)")
    if missing:
        click.echo("Missing required environment variables:", err=True)
        for m in missing:
            click.echo(f"  {m}", err=True)
        sys.exit(1)
    return url, token


async def build_index(include_services: bool = False, verbose: bool = False) -> EntityIndex:
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
@click.option("--output", "-o", type=click.Choice(["human", "json"]), default="human", help="Output format")
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
@click.option("--device-class", "-c", help="Filter by device_class (e.g. temperature, motion)")
@click.option("--area", "-a", help="Filter by area name (substring match)")
@click.option("--integration", "-i", help="Filter by integration/platform (e.g. hue, zwave_js, mqtt)")
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
        output_table(rows, ["entity_id", "friendly_name", "domain", "device_class", "area", "state", "platform"])


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
        click.echo(f"{result['entity_id']}  {result['friendly_name'] or '—'}  {result['state']}")


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
        rows = [{"domain": d.domain, "count": d.entity_count, "examples": ", ".join(d.sample_entities)} for d in result]
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
        rows = [{"integration": i.integration, "count": i.entity_count, "examples": ", ".join(i.sample_entities)} for i in result]
        output_table(rows, ["integration", "count", "examples"])


@cli.command()
@click.argument("text", required=False)
@click.option("--domain", "-d", help="Filter by service domain (e.g. light, climate)")
@click.pass_context
def services(ctx: click.Context, text: str | None, domain: str | None) -> None:
    """List or search available service actions."""
    index = run_with_error_handling(build_index(include_services=True, verbose=ctx.obj["verbose"]))
    results = index.search_services(text=text, domain=domain)

    if ctx.obj["output"] == "json":
        output_json([s.model_dump(exclude_none=True) for s in results])
    else:
        rows: list[dict] = []
        for s in results:
            rows.append({
                "service": f"{s.domain}.{s.service}",
                "name": s.name or "",
                "description": s.description or "",
                "fields": ", ".join(f.name for f in s.fields) if s.fields else "",
            })
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
@click.option("--target", "-t", "target_json", help="Target as JSON (entity_id, device_id, or area_id)")
@click.pass_context
def call_service(ctx: click.Context, service_name: str, data_json: str | None, target_json: str | None) -> None:
    """Call a Home Assistant service.

    SERVICE_NAME is in the format domain.service (e.g. light.turn_on, automation.reload).
    """
    if "." not in service_name:
        click.echo(f"Invalid service name '{service_name}'. Expected format: domain.service", err=True)
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

    result = run_with_error_handling(_call_service(domain, service, data, target, verbose=ctx.obj["verbose"]))

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
        run_with_error_handling(_call_service("homeassistant", "reload_all", verbose=ctx.obj["verbose"]))
        if ctx.obj["output"] == "json":
            output_json({"success": True, "reloaded": "all"})
        else:
            click.echo("Reloaded all configuration")
    elif domain in RELOAD_DOMAINS:
        run_with_error_handling(_call_service(domain, "reload", verbose=ctx.obj["verbose"]))
        if ctx.obj["output"] == "json":
            output_json({"success": True, "reloaded": domain})
        else:
            click.echo(f"Reloaded {domain}")
    else:
        click.echo(f"Unknown reload domain '{domain}'. Use 'ha-tool reload' to see options.", err=True)
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

    run_with_error_handling(_call_service("homeassistant", "restart", verbose=ctx.obj["verbose"]))

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
    result = run_with_error_handling(_render_template(template_str, verbose=ctx.obj["verbose"]))

    if ctx.obj["output"] == "json":
        output_json({"template": template_str, "result": result})
    else:
        click.echo(result)


def main() -> None:
    cli()


@cli.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--filter", "-f", "filter_mode", type=click.Choice(["all", "missing", "existing"]), default="all", help="Filter results")
@click.pass_context
def verify(ctx: click.Context, files: tuple[str, ...], filter_mode: str) -> None:
    """Verify entity references in files exist in Home Assistant.

    Extracts all entity patterns (e.g. sensor.pool_temp, light.kitchen)
    from the given files and checks each against the live HA instance.
    """
    index = run_with_error_handling(build_index(include_services=True, verbose=ctx.obj["verbose"]))

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
            click.echo(f"  {status} {ref['file']}:{ref['line']}  {ref['entity_id']}{name_str}")

        missing = sum(1 for r in all_refs if not r["exists"])
        found = sum(1 for r in all_refs if r["exists"])

        click.echo("")
        click.echo(f"{found} valid, {missing} missing ({found + missing} total)")
