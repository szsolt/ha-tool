# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `rename-entity` — Change an entity's `entity_id` in the entity registry (via `config/entity_registry/update` with `new_entity_id`). Works for integration-provided entities since the override is keyed by unique_id; handy after an integration rebuild re-assigns entity_ids and existing templates/config still point at the old ones.

## [0.3.0] - 2026-06-17

### Added

- `lovelace-refresh` — Reload YAML-mode Lovelace dashboards from disk into Home Assistant's in-memory cache (via `lovelace/config` with `force=true`). With no arguments, discovers all yaml-mode dashboards and refreshes them plus the built-in default; accepts explicit URL paths. Exits 1 if any refresh fails.

### Changed

- WebSocket client now uses a 10s connect `open_timeout` so a hung Home Assistant doesn't block indefinitely.
- Restructured documentation: CLI usage docs now live solely in the installable skill (`skills/ha-tool.md`); `AGENTS.md` is now a signpost for working on the repo.

## [0.2.0] - 2026-05-01

### Added

- **Discovery**
  - `info` — Core config (version, location, units, components)
  - `panels` — Registered UI panels
  - `config-entries` — Integration config entries (with `--domain` filter)
  - `labels` — Label registry
  - `floors` — Floor registry
  - `categories` — Category registry by scope

- **History & Logs**
  - `history` — State history of an entity over a time window
  - `logbook` — Human-readable activity log
  - `error-log` — Fetch Home Assistant's error log

- **Diagnostics**
  - `health` — System health snapshot per integration
  - `repairs` — Active repair issues
  - `notifications` — List and dismiss persistent notifications

- **Live & Calendar**
  - `watch` — Stream Home Assistant events as NDJSON
  - `calendars` — List calendar entities
  - `calendar` — Events for a calendar entity over a time window

- **Registry Cleanup** (destructive, with `--yes` confirmation)
  - `remove-entity` — Remove a helper/manual entity
  - `remove-device` — Disassociate a device from a config entry
  - `remove-config-entry` — Remove an integration config entry and its entities

- **Configuration**
  - `check-config` — Validate `configuration.yaml` via REST `/api/config/core/check_config`

- `--version` flag, time/duration parsing helpers, and REST helpers.

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
