# ha-tool — Home Assistant CLI

Use `ha-tool` for discovering, querying, and controlling Home Assistant. Always use `-o json` for structured output.

## Prerequisites

Requires `HASS_SERVER` and `HASS_TOKEN` environment variables.

## Commands

### Discovery

```bash
ha-tool -o json areas                    # List areas
ha-tool -o json domains                  # List entity domains
ha-tool -o json integrations             # List integrations
ha-tool -o json services [--domain X]    # List services
ha-tool -o json info                     # Core config (version, location, units)
ha-tool -o json panels                   # Registered UI panels
ha-tool -o json config-entries [-d X]    # Integration config entries
ha-tool -o json labels                   # Label registry
ha-tool -o json floors                   # Floor registry
ha-tool -o json categories <scope>       # Category registry (default scope: automation)
```

### Search & Inspect

```bash
ha-tool -o json search <text> [--domain X] [--device-class X] [--area X] [--integration X] [--include-disabled]
ha-tool -o json inspect <entity_id> [entity_id ...]
ha-tool -o json get <entity_id>
```

`search` TEXT supports substring, glob (`*` `?`), and regex (`[0-9]`, `|`, etc.) patterns.

### Control

```bash
ha-tool -o json call <domain.service> [--data JSON] [--target JSON]
ha-tool -o json reload [domain|all]
ha-tool -o json restart [--confirm]
ha-tool -o json template '<jinja2>'
ha-tool -o json check-config             # Validate configuration.yaml (exit 1 if invalid)
ha-tool -o json lovelace-refresh [url_path ...]   # Reload YAML-mode dashboards from disk (exit 1 if any fail)
```

`lovelace-refresh` with no arguments discovers all yaml-mode dashboards and also refreshes the built-in default dashboard. Pass explicit URL_PATHS to target specific dashboards; use the literal `default` for the default dashboard.

### History & logs

```bash
ha-tool -o json history <entity_id> [--since 1h] [--until now] [--minimal]
ha-tool -o json logbook [--since 1h] [--until now] [--entity X]
ha-tool -o json error-log [-n LINES]
```

`--since` / `--until` accept relative (`1h`, `30m`, `5d`, `2w`), keywords (`now`, `today`, `yesterday`), or ISO 8601.

### Diagnostics

```bash
ha-tool -o json health                   # System health snapshot per integration
ha-tool -o json repairs [--include-ignored]
ha-tool -o json notifications list
ha-tool notifications dismiss <notification_id>
```

### Live event stream

```bash
ha-tool watch [--event-type X] [--entity X]   # NDJSON stream until Ctrl-C
```

`watch` always emits NDJSON (one JSON object per line) regardless of `-o`.

### Calendar

```bash
ha-tool -o json calendars                                       # List calendar entities
ha-tool -o json calendar <entity_id> [--start now] [--end 7d]   # Events in window
```

`--end` accepts a relative offset from `--start` (e.g. `7d`, `1w`), or an absolute ISO/keyword.

### Verify

```bash
ha-tool -o json verify <file> [--filter all|missing|existing]
```

### Registry edits

```bash
ha-tool -o json rename-entity <entity_id> <new_entity_id>   # Change an entity's entity_id
```

Notes:
- `rename-entity` works for any registered entity (the override is keyed by unique_id, so it survives integration reloads). `NEW_ENTITY_ID` must be in the same domain and not already taken.
- Useful when an integration rebuild re-assigns entity_ids and config/templates still reference the old ones.

### Remove (destructive — prompts unless `-y`)

```bash
ha-tool -o json remove-entity <entity_id> [--yes]                       # Helpers / manual entities only
ha-tool -o json remove-device <device_id> <config_entry_id> [--yes]     # Disassociate device from config entry
ha-tool -o json remove-config-entry <entry_id> [--yes]                  # Remove integration + its entities
```

Notes:
- `remove-entity` works only for entities without unique_id constraint (helpers, manual). Integration-provided entities must go via device or config entry.
- HA has no direct device-remove API; `remove-device` removes one config-entry association — device deletes when last association removed.
- `remove-config-entry` JSON result may contain `require_restart: true`.

## Examples

```bash
# Find temperature sensors in Kitchen
ha-tool -o json search --domain sensor --device-class temperature --area Kitchen

# Find all Z-Wave entities
ha-tool -o json search --integration zwave_js

# Turn on a light
ha-tool call light.turn_on --target '{"entity_id": "light.kitchen"}'

# Set thermostat
ha-tool call climate.set_temperature --data '{"temperature": 22}' --target '{"entity_id": "climate.hvac"}'

# Reload automations
ha-tool reload automations

# Render template
ha-tool template '{{ states("sensor.temperature") }}'

# State history of a sensor for last 6 hours
ha-tool -o json history sensor.outdoor_temperature --since 6h --minimal

# Recent activity for one entity
ha-tool -o json logbook --since 30m -e light.kitchen

# Tail error log
ha-tool error-log -n 50

# Live state-change stream filtered to one entity
ha-tool watch -t state_changed -e light.kitchen
```
