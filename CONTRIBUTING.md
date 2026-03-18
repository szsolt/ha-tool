# Contributing to ha-tool

Thanks for your interest in contributing! This document outlines how to get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/szsolt/ha-tool.git
cd ha-tool

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Or with uv
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Environment Variables

You'll need a Home Assistant instance for testing:

```bash
export HASS_SERVER=https://your-ha-instance:8123
export HASS_TOKEN=your_long_lived_access_token
```

## Code Style

- Python 3.12+ with type hints
- Use `ruff` for linting and formatting
- Follow existing code patterns

```bash
# Install dev tools
pip install ruff mypy

# Lint
ruff check .

# Format
ruff format .

# Type check
mypy ha_tool
```

## Project Structure

```
ha-tool/
├── ha_tool/
│   ├── __init__.py
│   ├── cli.py        # Click CLI commands
│   ├── client.py     # WebSocket client
│   ├── models.py     # Pydantic models
│   └── registry.py   # Entity index and search logic
├── AGENTS.md         # AI agent documentation
├── README.md
├── pyproject.toml
└── ...
```

## Adding a New Command

1. Add any new client methods to `client.py`
2. Add Pydantic models to `models.py` if needed
3. Add the CLI command to `cli.py`
4. Update `AGENTS.md` with the command documentation
5. Update `README.md` usage section
6. Add entry to `CHANGELOG.md`

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>: <description>

[optional body]
```

Types:
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `chore:` — Maintenance tasks

Examples:
```
feat: add history command for entity state history
fix: handle WebSocket timeout on slow connections
docs: update AGENTS.md with new command
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with conventional commit messages
4. Test against a real Home Assistant instance
5. Update documentation
6. Submit a pull request

## Reporting Issues

When reporting bugs, please include:

- ha-tool version (`pip show ha-tool`)
- Python version (`python --version`)
- Home Assistant version
- Full error output with `-v` flag
- Steps to reproduce

## Questions?

Open an issue for questions or discussion.
