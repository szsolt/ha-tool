# ha-tool

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A CLI tool for discovering, querying, and controlling Home Assistant over WebSocket. Designed for both human use and AI agent consumption.

## Features

- **Entity Discovery** — Search, inspect, and list entities with flexible filtering
- **Service Calls** — Call any Home Assistant service with JSON data/targets
- **Configuration Reload** — Reload automations, scripts, scenes, and more
- **Template Rendering** — Test Jinja2 templates against your live instance
- **Entity Verification** — Validate entity references in YAML/config files
- **Dual Output** — Human-readable tables or JSON for scripting/AI agents
- **Stateless** — Each invocation opens a connection, performs the action, and exits

## Installation

```bash
# From PyPI (when published)
pip install ha-tool

# From source
pip install -e .

# With uv
uv tool install .
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
ha-tool verify -m automations.yaml
```

Extracts all patterns matching `<known_domain>.<object_id>` from the given files, filters out known service names (e.g. `light.turn_on`), and checks each entity against the live HA instance.

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

See [AGENTS.md](AGENTS.md) for structured documentation optimized for AI agent consumption, including:
- Command reference with exact output schemas
- Discovery workflow patterns
- Common usage examples

### Claude Code Integration

Install the ha-tool skill for Claude Code:

```bash
./scripts/install-skill.sh
```

This copies the skill to `~/.claude/commands/ha-tool.md`, making it available globally in Claude Code.

## Dependencies

- Python 3.12+
- [click](https://click.palletsprojects.com/) — CLI framework
- [pydantic](https://docs.pydantic.dev/) — Data validation
- [websockets](https://websockets.readthedocs.io/) — WebSocket client

## License

MIT License. See [LICENSE](LICENSE) for details.
