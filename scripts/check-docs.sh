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
named = re.findall(r'@cli\.command\(name="([^"]+)"\)', src)
defs = re.findall(r'@cli\.command\(\)\s*\n(?:@[^\n]*\n)*def (\w+)', src)
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

# --- Quality gate (skip silently if tools absent) ------------------------
if command -v ruff >/dev/null 2>&1; then
    echo "Running ruff..."
    ruff check ha_tool/ || fail=1
    ruff format --check ha_tool/ || { echo "  - run: ruff format ha_tool/"; fail=1; }
else
    echo "ruff not installed — skipping lint/format check"
fi

if command -v mypy >/dev/null 2>&1; then
    echo "Running mypy..."
    mypy ha_tool || fail=1
else
    echo "mypy not installed — skipping type check"
fi

if [ "$fail" -ne 0 ]; then
    echo ""
    echo "✗ check-docs failed. See CONTRIBUTING.md → 'Adding a New Command'."
    exit 1
fi
echo "✓ all checks passed"
