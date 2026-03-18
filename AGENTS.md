# AGENTS.md — ha-tool for AI agents

## What this tool does

`ha-tool` is a CLI for discovering, querying, and controlling Home Assistant over WebSocket. It is stateless — each invocation opens a connection, performs the action, and exits. All output goes to stdout.

## Prerequisites

Requires `HASS_SERVER` and `HASS_TOKEN` environment variables. The tool exits with code 1 and a diagnostic message if either is missing.

## Output format

Always use `-o json` for structured output:

```bash
ha-tool -o json <command> [args]
```

All JSON responses are a single JSON value (object or array) on stdout. Errors are also JSON when using `-o json`.

## Commands

### Discovery workflow

Use this sequence to explore an unfamiliar Home Assistant instance:

1. **`ha-tool -o json areas`** — List all areas (rooms/zones). Returns `[{area_id, name, floor_id}]`.
2. **`ha-tool -o json domains`** — List all entity domains with counts. Returns `[{domain, entity_count, sample_entities}]`.
3. **`ha-tool -o json integrations`** — List all integrations with counts. Returns `[{integration, entity_count, sample_entities}]`.
4. **`ha-tool -o json search <text>`** — Find entities. Returns `[{entity_id, domain, friendly_name, device_class, area, state, platform}]`.
5. **`ha-tool -o json inspect <entity_id>`** — Full detail on specific entities. Returns `[{entity_id, domain, friendly_name, device_class, area, state, attributes, last_changed, platform, device_name, device_manufacturer, device_model, entity_category, labels}]`.
6. **`ha-tool -o json services`** — List available service actions. Returns `[{domain, service, name, description, fields}]`.

### search

```bash
ha-tool -o json search [TEXT] [--domain DOMAIN] [--device-class CLASS] [--area AREA] [--integration INTEGRATION] [--include-disabled]
```

- `TEXT` — Matches against entity_id, friendly_name, and area name. Supports:
  - Plain text: substring match (case-insensitive)
  - Glob: `sensor.pool_*`, `binary_sensor.door_?`
  - Regex: `temperature_[0-9]+`, `pool|kitchen` (auto-detected by `[]|^$+(){}`)
- `--domain` — Exact match on entity domain (e.g. `sensor`, `light`, `climate`)
- `--device-class` — Exact match on device_class (e.g. `temperature`, `motion`, `humidity`)
- `--area` — Substring match on resolved area name
- `--integration` — Exact match on integration/platform (e.g. `hue`, `zwave_js`, `mqtt`)
- All filters are AND-combined
- Disabled entities are excluded by default

### inspect

```bash
ha-tool -o json inspect <entity_id> [entity_id ...]
```

Accepts one or more entity IDs. Returns the full entity detail including all attributes, device info, and timestamps.

### get

```bash
ha-tool -o json get <entity_id>
```

Returns minimal state info: `{entity_id, state, friendly_name, last_changed}`.

### areas

```bash
ha-tool -o json areas
```

Returns all configured areas: `[{area_id, name, floor_id}]`.

### domains

```bash
ha-tool -o json domains
```

Returns all entity domains with counts and up to 5 sample entity IDs.

### integrations

```bash
ha-tool -o json integrations
```

Returns all integrations (platforms) with entity counts and up to 5 sample entity IDs. Useful for discovering which integrations are configured (e.g. `hue`, `zwave_js`, `mqtt`, `esphome`).

### services

```bash
ha-tool -o json services [TEXT] [--domain DOMAIN]
```

Lists available service actions. Each service includes its fields with descriptions.

### verify

```bash
ha-tool -o json verify <file> [file ...] [--missing-only]
```

Extracts all entity references from the given files and checks each against the live HA instance. Returns `[{entity_id, exists, file, line, friendly_name}]`.

- Recognizes patterns matching `<known_domain>.<object_id>` (e.g. `sensor.pool_temp`, `binary_sensor.front_door`)
- Automatically excludes known service names (e.g. `light.turn_on`, `climate.set_temperature`)
- `--missing-only` / `-m` filters to only non-existent references
- Accepts multiple files: YAML, Python, Lua, JSON, or any text format

### call

```bash
ha-tool -o json call <domain.service> [--data JSON] [--target JSON]
```

Call any Home Assistant service. Returns `{success, service, result}`.

- `--data` / `-d` — Service data as JSON object
- `--target` / `-t` — Target as JSON with `entity_id`, `device_id`, or `area_id`

Examples:
```bash
ha-tool call light.turn_on --target '{"entity_id": "light.kitchen"}'
ha-tool call climate.set_temperature --data '{"temperature": 22}' --target '{"entity_id": "climate.living_room"}'
ha-tool call automation.trigger --target '{"entity_id": "automation.morning_routine"}'
```

### reload

```bash
ha-tool -o json reload [DOMAIN]
```

Reload Home Assistant configuration. Without arguments, lists available reload domains.

- `all` — Reload all configuration (`homeassistant.reload_all`)
- `automation`, `script`, `scene`, `group`, `template`, `zone`, `person`, etc.

Examples:
```bash
ha-tool reload all
ha-tool reload automations
ha-tool reload scripts
```

### restart

```bash
ha-tool -o json restart [--confirm]
```

Restart Home Assistant. Requires confirmation unless `--confirm` / `-y` is passed.

```bash
ha-tool restart -y
```

### template

```bash
ha-tool -o json template '<jinja2_template>'
```

Render a Jinja2 template and return the result. Useful for debugging templates.

```bash
ha-tool template '{{ states("sensor.temperature") }}'
ha-tool template '{{ state_attr("climate.living_room", "current_temperature") }}'
ha-tool template '{{ now().strftime("%H:%M") }}'
```

## Entity ID format

Entity IDs follow the pattern `<domain>.<object_id>`, e.g. `sensor.pool_temperature`, `light.kitchen`, `climate.hvac`. The domain determines the entity type.

## Common domains

| Domain | Description |
|--------|-------------|
| `sensor` | Numeric/text sensors (temperature, humidity, power) |
| `binary_sensor` | On/off sensors (motion, door, window) |
| `light` | Lights |
| `switch` | Switches |
| `climate` | HVAC, thermostats |
| `cover` | Blinds, garage doors |
| `automation` | Automations |
| `script` | Scripts |
| `scene` | Scenes |
| `input_boolean` | Virtual toggles |
| `input_number` | Virtual sliders |

## Typical agent patterns

**Find all temperature sensors in a specific area:**
```bash
ha-tool -o json search --domain sensor --device-class temperature --area "Pool"
```

**Find all entities from a specific integration:**
```bash
ha-tool -o json search --integration zwave_js
```

**Find entities by device name pattern:**
```bash
ha-tool -o json search 'wq3a25a01264*'
```

**Get available actions for a domain:**
```bash
ha-tool -o json services --domain climate
```

**Inspect a specific entity to see all its attributes:**
```bash
ha-tool -o json inspect climate.living_room_ac
```

**Validate entity references in a config file:**
```bash
ha-tool -o json verify automations.yaml
```

**Find only broken references across multiple files:**
```bash
ha-tool -o json verify -m automations.yaml scripts.yaml configuration.yaml
```

**Turn on a light:**
```bash
ha-tool call light.turn_on --target '{"entity_id": "light.kitchen"}'
```

**Set thermostat temperature:**
```bash
ha-tool call climate.set_temperature --data '{"temperature": 21}' --target '{"entity_id": "climate.hvac"}'
```

**Reload automations after editing:**
```bash
ha-tool reload automations
```

**Check current sensor value via template:**
```bash
ha-tool template '{{ states("sensor.outdoor_temperature") | float | round(1) }} °C'
```

## Error handling

- Exit code 0: success
- Exit code 1: error (missing config, connection failure, entity not found)
- With `-o json`, errors include an `error` key in the response
- Connection and auth errors are written to stderr
