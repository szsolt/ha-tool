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

### remove-entity

```bash
ha-tool -o json remove-entity <entity_id> [--yes]
```

Remove an entity from the entity registry. Only works for entities without a unique_id constraint (helpers, manually-added entities). Integration-provided entities must be removed via their device or config entry. Prompts for confirmation unless `--yes` / `-y`.

```bash
ha-tool remove-entity input_boolean.test_toggle -y
```

### remove-device

```bash
ha-tool -o json remove-device <device_id> <config_entry_id> [--yes]
```

Disassociate a device from a config entry. The device is fully removed when its last config entry association is removed. Prompts for confirmation unless `--yes` / `-y`.

```bash
ha-tool remove-device abc123def456 zwave_js_entry_id -y
```

### remove-config-entry

```bash
ha-tool -o json remove-config-entry <entry_id> [--yes]
```

Remove an integration config entry along with its associated devices and entities. Some integrations require a Home Assistant restart to fully unload — the JSON output includes `require_restart` when so. Prompts for confirmation unless `--yes` / `-y`.

```bash
ha-tool remove-config-entry 01HXY7Z8ABCDEF -y
```

### check-config

```bash
ha-tool -o json check-config
```

Validate the Home Assistant `configuration.yaml`. Calls the REST endpoint `/api/config/core/check_config`. Returns `{result: "valid"|"invalid", errors: string|null, warnings: string|null}`. Exits with code 1 when invalid.

```bash
ha-tool check-config
ha-tool -o json check-config
```

### info

```bash
ha-tool -o json info
```

Returns Home Assistant core configuration: `{version, location_name, latitude, longitude, elevation, time_zone, unit_system, components, config_dir, external_url, internal_url, currency, country, language, safe_mode, state}`.

### panels

```bash
ha-tool -o json panels
```

Returns registered UI panels: `[{component_name, url_path, title, icon, require_admin, config_panel_domain}]`.

### config-entries

```bash
ha-tool -o json config-entries [--domain DOMAIN]
```

Lists integration config entries. Returns `[{entry_id, domain, title, state, source, disabled_by, pref_disable_polling, pref_disable_new_entities, supports_options, supports_remove_device, supports_unload, reason}]`. The `--domain` / `-d` flag filters client-side by integration domain.

```bash
ha-tool config-entries -d zwave_js
```

### labels

```bash
ha-tool -o json labels
```

Returns configured labels: `[{label_id, name, color, icon, description}]`.

### floors

```bash
ha-tool -o json floors
```

Returns configured floors: `[{floor_id, name, level, icon, aliases}]`.

### categories

```bash
ha-tool -o json categories [SCOPE]
```

Lists categories for a scope. SCOPE defaults to `automation`; common values include `automation`, `script`, `scene`. Returns `[{category_id, scope, name, icon}]`.

```bash
ha-tool categories script
```

### history

```bash
ha-tool -o json history <entity_id> [--since 1h] [--until now] [--minimal]
```

State history of an entity over a time window. Returns `[{entity_id, state, last_changed, last_updated, attributes}]`.

- `--since` / `--until` accept relative (`1h`, `30m`, `5d`, `2w`), keywords (`now`, `today`, `yesterday`), or ISO 8601.
- `--minimal` strips attributes server-side for a smaller payload.

```bash
ha-tool history sensor.outdoor_temperature --since 6h
ha-tool -o json history sensor.power --since today --minimal
```

### logbook

```bash
ha-tool -o json logbook [--since 1h] [--until now] [--entity ENTITY_ID]
```

Human-readable activity log. Returns `[{when, name, message, entity_id, domain, context_id, ...}]`.

- `--since` / `--until` accept relative (`1h`, `30m`, `5d`), keywords (`now`, `today`, `yesterday`), or ISO 8601.
- `--entity` / `-e` filters by entity_id; repeat for multiple entities.

```bash
ha-tool logbook --since 30m
ha-tool logbook --since today -e light.kitchen
```

### error-log

```bash
ha-tool -o json error-log [--lines N]
```

Fetch Home Assistant's error log via REST `/api/error_log` (plaintext). With `-o json`, returns `{log: "..."}`. With `--lines` / `-n N`, tail to the last N lines.

```bash
ha-tool error-log -n 50
ha-tool -o json error-log -n 5
```

### health

```bash
ha-tool -o json health
```

System health snapshot per integration. Returns `{domain: {info_key: value, ...}}` — exact info varies per integration (e.g. version, can_reach_server, observer status).

```bash
ha-tool health
```

### repairs

```bash
ha-tool -o json repairs [--include-ignored]
```

Lists active repair issues. Returns `[{issue_id, domain, severity, breaks_in_ha_version, created, is_fixable, is_persistent, learn_more_url, translation_key, translation_placeholders, ignored, dismissed_version}]`. Ignored issues are filtered out by default.

```bash
ha-tool repairs
```

### notifications

```bash
ha-tool -o json notifications list
ha-tool notifications dismiss <notification_id>
```

List or dismiss persistent notifications.

- `list` — Returns `[{notification_id, title, message, created_at, status}]`.
- `dismiss <notification_id>` — Dismisses a notification via the `persistent_notification.dismiss` service.

```bash
ha-tool notifications list
ha-tool notifications dismiss config_entry_setup_failed
```

### watch

```bash
ha-tool watch [--event-type EVENT] [--entity ENTITY_ID]
```

Stream Home Assistant events as NDJSON (one JSON object per line) until interrupted with Ctrl-C. Output is always NDJSON regardless of `-o`.

- `--event-type` / `-t` filters at subscription time (e.g. `state_changed`).
- `--entity` / `-e` filters client-side by entity_id.

```bash
ha-tool watch --event-type state_changed
ha-tool watch -t state_changed -e light.kitchen
```

### calendars

```bash
ha-tool -o json calendars
```

Lists available calendar entities (REST `/api/calendars`). Returns `[{entity_id, name}]`.

### calendar

```bash
ha-tool -o json calendar <entity_id> [--start now] [--end 7d]
```

Returns events for a calendar entity over a time window (REST `/api/calendars/<entity_id>?start=&end=`).

- `--start` accepts relative (`1h`, `today`, `now`), ISO 8601, or keyword.
- `--end` accepts a relative duration (offset from start, e.g. `7d`, `1w`), ISO 8601, or keyword.

Returns `[{start, end, summary, description, location, uid, recurrence_id}]`. `start` / `end` are typically `{date}` (all-day) or `{dateTime}` (timed).

```bash
ha-tool calendar calendar.holidays --start now --end 7d
ha-tool -o json calendar calendar.work --start today --end 30d
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
