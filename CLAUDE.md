# CLAUDE.md — ha-tool for Claude Code

## Project Overview

`ha-tool` is a CLI for discovering, querying, and controlling Home Assistant over WebSocket. Stateless design — each invocation opens a connection, performs the action, and exits.

## Build & Run

```bash
# Install
pip install -e .
# or
uv tool install .

# Run (requires HASS_SERVER and HASS_TOKEN env vars)
ha-tool --help
ha-tool -o json search "kitchen"
```

## Code Structure

- `ha_tool/cli.py` — Typer CLI commands, entry point is `main()`
- `ha_tool/client.py` — `HAWebSocketClient` async context manager for HA WebSocket API
- `ha_tool/models.py` — Pydantic models for entities, areas, devices, services
- `ha_tool/registry.py` — `EntityIndex` class for searching/filtering entities

## Key Patterns

### Adding a new command

1. Add client method to `client.py` if it needs new WebSocket calls
2. Add CLI command in `cli.py` using the `@app.command()` decorator, with options declared as `Annotated[T, typer.Option(...)]` parameters
3. Use `run_with_error_handling()` wrapper for async calls
4. Support both human (`output_table`) and JSON (`output_json`) output
5. Update `skills/ha-tool.md` (installable skill — source of truth for CLI usage docs) and add a `CHANGELOG.md` entry
6. Run `./scripts/check-docs.sh` — the pre-commit hook fails if a command is undocumented or `ruff`/`mypy` complain

### WebSocket API

```python
async with HAWebSocketClient(url, token) as client:
    result = await client.send_command("get_states")
    await client.call_service("light", "turn_on", target={"entity_id": "light.kitchen"})
```

For subscription-based APIs (like `render_template`), use `asyncio.Queue` instead of `Future`.

### Output formats

Global flags live on the module-level `state` object, set by the Typer callback:

```python
if state.output == OutputFormat.json:
    output_json([r.model_dump(exclude_none=True) for r in results])
else:
    output_table(rows, ["col1", "col2", "col3"])
```

## Testing

Unit tests cover the pure helpers (no HA connection needed):

```bash
uv run pytest
```

Anything touching the WebSocket API still needs manual testing against a real instance:

```bash
export HASS_SERVER=https://your-ha:8123
export HASS_TOKEN=your_token

ha-tool -v search "test"           # Verbose mode shows WebSocket traffic
ha-tool -o json integrations       # JSON output
ha-tool template '{{ now() }}'     # Template rendering
ha-tool call light.turn_on --target '{"entity_id": "light.test"}'
```

## Style

- Python 3.12+, type hints everywhere
- Pydantic v2 for models
- Typer for CLI
- No comments unless explaining non-obvious logic
- Prefer `model_dump()` over `dict()` for Pydantic models

## Documentation

- `README.md` — User-facing documentation
- `skills/ha-tool.md` — Installable skill; source of truth for CLI command schemas and examples
- `AGENTS.md` — Signpost for AI agents (points to CLAUDE.md / CONTRIBUTING.md / the skill)
- `CONTRIBUTING.md` — Development setup and guidelines
