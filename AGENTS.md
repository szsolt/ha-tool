# AGENTS.md — ha-tool

Guidance for AI agents working in this repository.

## Working on this repo (extend / fix)

- **[CLAUDE.md](CLAUDE.md)** — architecture, code structure, key patterns, and style.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — dev setup, linting/type-checking, the add-a-command workflow, and commit conventions.

## Using the `ha-tool` CLI

`ha-tool` is the installable CLI for discovering, querying, and controlling Home Assistant.

- End-user / runtime command reference (schemas, examples, return shapes) lives in the **installable skill** at [`skills/ha-tool.md`](skills/ha-tool.md). Install it with `./scripts/install-skill.sh`.
- This skill is the **source of truth** for CLI usage docs — update it (not this file) when adding or changing a command.
- See [README.md](README.md) for human-facing usage.
