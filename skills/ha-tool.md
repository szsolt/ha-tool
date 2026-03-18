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
```

### Search & Inspect

```bash
ha-tool -o json search <text> [--domain X] [--device-class X] [--area X] [--integration X]
ha-tool -o json inspect <entity_id> [entity_id ...]
ha-tool -o json get <entity_id>
```

### Control

```bash
ha-tool -o json call <domain.service> [--data JSON] [--target JSON]
ha-tool -o json reload [domain|all]
ha-tool -o json restart [--confirm]
ha-tool -o json template '<jinja2>'
```

### Verify

```bash
ha-tool -o json verify <file> [--missing-only]
```

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
```
