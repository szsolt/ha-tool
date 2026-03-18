# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-03

### Added

- **Entity Discovery**
  - `search` — Find entities by name, domain, device class, area, or integration
  - `inspect` — Get full details for one or more entities
  - `get` — Get current state of a single entity
  - `areas` — List all configured areas
  - `domains` — List all entity domains with counts
  - `integrations` — List all integrations with entity counts
  - `services` — List or search available service actions
  - `verify` — Validate entity references in YAML/config files

- **Control Commands**
  - `call` — Call any Home Assistant service with JSON data/targets
  - `reload` — Reload automations, scripts, scenes, and other configuration
  - `restart` — Restart Home Assistant (with confirmation)
  - `template` — Render Jinja2 templates

- **Output Formats**
  - Human-readable table output (default)
  - JSON output (`-o json`) for scripting and AI agents

- **Search Features**
  - Substring matching (default)
  - Glob patterns (`*`, `?`)
  - Regex patterns (auto-detected)
  - Filters: `--domain`, `--device-class`, `--area`, `--integration`

- **Documentation**
  - `AGENTS.md` — Structured documentation for AI agent consumption
