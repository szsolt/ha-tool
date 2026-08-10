#!/usr/bin/env bash
# Completeness + quality gate for ha-tool.
#
# Fails if any CLI command defined in ha_tool/cli.py is missing from the
# installable skill (skills/ha-tool.md) or CHANGELOG.md, and runs ruff/mypy.
# Wired as a git pre-commit hook via scripts/install-hooks.sh, but also
# runnable by hand: ./scripts/check-docs.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

fail=0
note() { echo "  - $1"; fail=1; }

# --- Extract command names from cli.py ----------------------------------
# Named commands: @cli.command(name="foo")  → foo
# Default commands: bare @cli.command() decorating def foo_bar → foo-bar
commands="$(python3 - <<'PY'
import re
src = open("ha_tool/cli.py").read()
# Only top-level commands (registered on `app`) are gated for documentation.
# Sub-group commands (e.g. `@notifications_app.command`) are covered by their
# parent group's entry and use generic verbs (list/dismiss) we don't gate.
named = re.findall(r'@app\.command\(name="([^"]+)"\)', src)
defs = re.findall(r'@app\.command\(\)\s*\n(?:@[^\n]*\n)*def (\w+)', src)
defs = [d.replace("_", "-") for d in defs]
print("\n".join(sorted(set(named + defs))))
PY
)"

# --- Check each command is documented ------------------------------------
skill="skills/ha-tool.md"
changelog="CHANGELOG.md"

echo "Checking command documentation..."
while IFS= read -r cmd; do
    [ -z "$cmd" ] && continue
    grep -q -- "$cmd" "$skill"     || note "command '$cmd' not found in $skill"
    grep -q -- "\`$cmd\`" "$changelog" || note "command '$cmd' not found in $changelog"
done <<< "$commands"

# --- Quality gate --------------------------------------------------------
# Run through `uv run` so we get the ruff/mypy versions pinned in the dev
# dependency group. A bare `ruff` off PATH is whatever the developer happens
# to have installed, and rules move between releases — that drift let a tree
# pass this hook and then fail CI. Lint the whole tree, as CI does; linting
# only ha_tool/ let violations land in tests/.
if command -v uv >/dev/null 2>&1; then
    run_tool() { uv run --quiet --group dev "$@"; }
else
    echo "uv not found — falling back to PATH tools; versions may differ from CI"
    run_tool() { "$@"; }
fi

echo "Running ruff..."
run_tool ruff check . || fail=1
run_tool ruff format --check . || { echo "  - run: ruff format ."; fail=1; }

echo "Running mypy..."
run_tool mypy ha_tool || fail=1

if [ "$fail" -ne 0 ]; then
    echo ""
    echo "✗ check-docs failed. See CONTRIBUTING.md → 'Adding a New Command'."
    exit 1
fi
echo "✓ all checks passed"
