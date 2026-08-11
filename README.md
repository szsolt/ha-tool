# ha-tool

[![PyPI](https://img.shields.io/pypi/v/ha-tool.svg)](https://pypi.org/project/ha-tool/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A CLI tool for discovering, querying, and controlling Home Assistant over WebSocket. Designed for both human use and AI agent consumption.

```console
$ ha-tool search "pool" -d sensor
ENTITY_ID                FRIENDLY_NAME     STATE  AREA
───────────────────────  ────────────────  ─────  ────
sensor.pool_temperature  Pool Temperature  27.4   Pool
sensor.pool_ph           Pool pH           7.2    Pool

(2 results)

$ ha-tool -o json get sensor.pool_temperature | jq .state
"27.4"
```

Every command speaks `-o json`, so it composes with `jq` and is easy for an
agent to consume.

## Features

- **Entity Discovery** — Search, inspect, and list entities with flexible filtering
- **Registry Editing** — Rename, re-area, relabel, and bulk-remap entities live
- **Service Calls** — Call any Home Assistant service with JSON data/targets
- **Configuration Reload** — Reload automations, scripts, scenes, and more
- **Template Rendering** — Test Jinja2 templates against your live instance
- **Entity Verification** — Validate entity references in YAML/config files
- **Dual Output** — Human-readable tables or JSON for scripting/AI agents
- **Stateless** — Each invocation opens a connection, performs the action, and exits

## Installation

```bash
# As a standalone CLI (recommended)
uv tool install ha-tool

# Or with pip
pip install ha-tool

# From source
uv tool install .
pip install -e .
```

## Configuration

Set these environment variables:

```bash
export HASS_SERVER=https://your-ha-instance:8123
export HASS_TOKEN=your_long_lived_access_token
```

`HASS_URL` is also accepted as a fallback for `HASS_SERVER`.

Create a long-lived access token in Home Assistant: **Profile → Security → Long-Lived Access Tokens**.

## Usage

### Search entities

```bash
# Substring match
ha-tool search "pool"

# Filter by domain, device class, area
ha-tool search --domain sensor --device-class temperature
ha-tool search --area "Kitchen"
ha-tool search "pool" -d sensor -a "Pool"

# Glob patterns
ha-tool search 'sensor.pool_temp_*'
ha-tool search 'binary_sensor.door_?'

# Regex patterns (auto-detected by metacharacters like [] | ^ $ + ())
ha-tool search 'temperature_[0-9]+'
ha-tool search 'pool|kitchen'

# Include disabled entities
ha-tool search "pool" --include-disabled
```

### Inspect entities

```bash
ha-tool inspect climate.wq3a25a01264
ha-tool inspect sensor.pool_temp light.kitchen climate.hvac
```

### Get entity state

```bash
ha-tool get sensor.pool_temperature
```

### List areas

```bash
ha-tool areas
```

### List domains

```bash
ha-tool domains
```

### List integrations

```bash
ha-tool integrations
```

### List/search services

```bash
ha-tool services
ha-tool services --domain light
ha-tool services "temperature"
```

### Call services

```bash
# Turn on a light
ha-tool call light.turn_on --target '{"entity_id": "light.kitchen"}'

# Set thermostat temperature
ha-tool call climate.set_temperature --data '{"temperature": 22}' --target '{"entity_id": "climate.hvac"}'

# Trigger an automation
ha-tool call automation.trigger --target '{"entity_id": "automation.morning_routine"}'
```

### Reload configuration

```bash
# List available reload domains
ha-tool reload

# Reload specific domain
ha-tool reload automations
ha-tool reload scripts
ha-tool reload scenes

# Reload all configuration
ha-tool reload all
```

### Refresh Lovelace dashboards

```bash
# Discover all yaml-mode dashboards and refresh them + the default dashboard
ha-tool lovelace-refresh

# Refresh specific dashboards by url_path ("default" = the built-in dashboard)
ha-tool lovelace-refresh lovelace
ha-tool lovelace-refresh power default
```

Home Assistant caches parsed YAML-mode dashboards in memory, so replacing the
file on disk is invisible to clients. This sends `lovelace/config` with
`force: true` to re-read each dashboard from disk. Exits 1 if any refresh fails.

### Restart Home Assistant

```bash
ha-tool restart        # Prompts for confirmation
ha-tool restart -y     # Skip confirmation
```

### Render Jinja2 templates

```bash
ha-tool template '{{ states("sensor.temperature") }}'
ha-tool template '{{ now().strftime("%H:%M") }}'
ha-tool template '{{ state_attr("climate.hvac", "current_temperature") }}'
```

### Verify entity references in files

```bash
# Check all entity references in a file
ha-tool verify automations.yaml

# Multiple files
ha-tool verify automations.yaml scripts.yaml configuration.yaml

# Only show missing/invalid references
ha-tool verify --filter missing automations.yaml
```

Extracts all patterns matching `<known_domain>.<object_id>` from the given files, filters out known service names (e.g. `light.turn_on`), and checks each entity against the live HA instance.

### Edit the entity registry

```bash
# Only the fields you pass are changed
ha-tool set-entity sensor.pool_temp --name "Pool Temperature" --area "Pool"
ha-tool set-entity light.kitchen --icon mdi:ceiling-light --category config
ha-tool set-entity switch.old_name --new-id switch.new_name

# rename-entity is a shorthand for set-entity --new-id
ha-tool rename-entity switch.old_name switch.new_name
```

Live edit via `config/entity_registry/update` — no restart. `--new-id` must stay
in the same domain. `--label` is repeatable and replaces the whole label set.

### Bulk rename by regex

```bash
# Dry-run by default — prints every old -> new
ha-tool bulk-rename 'sensor\.old_(.*)' 'sensor.new_\1'

ha-tool bulk-rename -d switch 'switch\.zb_(.*)' 'switch.\1' --apply
```

PATTERN is a Python regex `fullmatch`ed against each entity_id; REPLACEMENT
supports backrefs. A batch containing any collision or cross-domain rename is
refused before anything changes.

> [!IMPORTANT]
> Renaming an entity_id does **not** update references to it. Automations,
> scripts, scenes, dashboards, and templates still pointing at the old id will
> silently stop working. Review the dry-run output before `--apply`, and use
> `ha-tool verify` afterwards to catch stale references in your YAML.

### Wrap a switch as another domain

```bash
ha-tool wrap-entity switch.desk_lamp --as light --name "Desk Lamp"
ha-tool wrap-entity switch.vent --as fan -y
```

Creates a new `switch_as_x` entity backed by the source switch. Useful for
re-creating switch→light / switch→fan mappings after an integration rebuild.

### Inspect a device

```bash
ha-tool device-inspect "Kitchen Motion"   # name substring
ha-tool device-inspect a1b2c3d4e5         # exact device_id
```

Device metadata plus its full entity roster. Ambiguous name matches list the
candidates to pick from.

### Report unhealthy entities

```bash
ha-tool stale-report
ha-tool stale-report --stale 2d -d sensor
ha-tool stale-report --only unavailable --only orphaned
```

Read-only sweep flagging `unavailable`, `unknown`, `stale`, `restored`,
`orphaned`, `disabled`, and `hidden` entities. Change-only sensors can
false-positive on `stale`, so treat that flag as advisory.

### Removal commands

> [!WARNING]
> These permanently modify your Home Assistant registry. Removing a config
> entry also removes every entity that integration provided. There is no undo
> — restore from a backup. Take one first.

```bash
ha-tool remove-entity input_boolean.test_toggle
ha-tool remove-device <device_id> <config_entry_id>
ha-tool remove-config-entry <entry_id>
```

Registry cleanup. Each prompts for confirmation; pass `-y` / `--yes` to skip
the prompt in scripts.

### Validate config

```bash
ha-tool check-config
```

Validates `configuration.yaml` (exits 1 when invalid).

### Discovery (extra)

```bash
ha-tool info             # core config (version, location, units)
ha-tool panels           # registered UI panels
ha-tool config-entries   # integrations and their config entries
ha-tool labels           # label registry
ha-tool floors           # floor registry
ha-tool categories <scope>  # category registry (default scope: automation)
```

### History and logs

```bash
ha-tool history sensor.outdoor_temperature --since 6h
ha-tool logbook --since 30m -e light.kitchen
ha-tool error-log -n 50
```

`--since` / `--until` accept `1h`, `30m`, `2d`, `today`, `now`, or ISO 8601.

### Diagnostics

```bash
ha-tool health           # system health snapshot per integration
ha-tool repairs          # active repair issues
ha-tool notifications list
ha-tool notifications dismiss <notification_id>
```

### Live event stream and calendar

```bash
ha-tool watch --event-type state_changed
ha-tool watch -t state_changed -e light.kitchen
ha-tool calendars
ha-tool calendar calendar.work --start now --end 7d
```

`watch` outputs NDJSON until Ctrl-C.

## Output formats

Default output is a human-readable table. Use `-o json` for machine-parseable JSON:

```bash
ha-tool -o json search "pool"
ha-tool -o json inspect sensor.pool_temp
ha-tool -o json services --domain climate
```

## Debugging

Use `-v` to see WebSocket connection details on stderr:

```bash
ha-tool -v search "pool"
```

## Architecture

- Single WebSocket connection per invocation, fires all registry queries concurrently, then closes. Stateless.
- Joins entity registry → device registry → area registry to resolve area names, device info, and friendly names.
- Entity's own `area_id` takes precedence over its device's `area_id`.
- Disabled entities are excluded by default.
- Search pattern auto-detection: plain text → substring, `*`/`?` → glob, regex metacharacters → regex.

## For AI Agents

`ha-tool` is built to be driven by an LLM agent, not just a human:

- **`-o json` on every command** — structured output, no scraping of table
  text. (`watch` is the exception: it streams NDJSON unconditionally.)
- **stdout stays clean.** Diagnostics and progress go to stderr, so piping into
  `jq` (or straight into a model) never picks up stray banners.
- **Meaningful exit codes** — non-zero on connection failure, auth failure, and
  validation errors, so an agent can branch on success instead of parsing prose.
- **Stateless** — no daemon or session to manage. One invocation, one result.
- **A clear read-only subset.** Discovery and inspection (`search`, `get`,
  `inspect`, `areas`, `history`, `stale-report`, `device-inspect`, `verify`, …)
  never write. The rest — `call`, `reload`, `restart`, `set-entity`,
  `rename-entity`, `wrap-entity`, `lovelace-refresh`, `remove-*` — change
  state, so an agent can be given the safe subset explicitly.
  `bulk-rename` is dry-run unless you pass `--apply`.

The installable skill at [`skills/ha-tool.md`](skills/ha-tool.md) is structured
documentation optimized for agent consumption, including:
- Command reference with exact output schemas
- Discovery workflow patterns
- Common usage examples

See [AGENTS.md](AGENTS.md) for guidance on extending or fixing the repo itself.

### Claude Code Integration

Install the ha-tool skill for Claude Code:

```bash
./scripts/install-skill.sh
```

This copies the skill to `~/.claude/commands/ha-tool.md`, making it available globally in Claude Code.

## Dependencies

- Python 3.12+
- [typer](https://typer.tiangolo.com/) — CLI framework
- [pydantic](https://docs.pydantic.dev/) — Data validation
- [websockets](https://websockets.readthedocs.io/) — WebSocket client

## License

MIT License. See [LICENSE](LICENSE) for details.
