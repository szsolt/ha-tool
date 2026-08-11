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

# --- Tool runner ---------------------------------------------------------
# Run through `uv run` so we get the ruff/mypy versions pinned in the dev
# dependency group. A bare `ruff` off PATH is whatever the developer happens
# to have installed, and rules move between releases — that drift let a tree
# pass this hook and then fail CI.
if command -v uv >/dev/null 2>&1; then
    run_tool() { uv run --quiet --group dev "$@"; }
else
    echo "uv not found — falling back to PATH tools; versions may differ from CI"
    # `python` is frequently absent where `python3` exists (CI images, distros).
    run_tool() {
        if [ "$1" = "python" ] && ! command -v python >/dev/null 2>&1; then
            shift
            command python3 "$@"
        else
            command "$@"
        fi
    }
fi

# --- Every documented example must parse against the real CLI ------------
# Docs drift silently: the Click->Typer migration left "Click" in three files
# and a rewrite recipe referencing decorators that no longer exist. Examples
# are checkable, so check them. `--help` short-circuits before any network
# call, which exercises the command name and flag names without touching HA.
echo "Checking documented examples parse..."
# Needs the package importable, so run it in the project env like the linters.
run_tool python - <<'PY' || fail=1
import os, pathlib, re, shlex, subprocess, sys

# Drive the installed console script rather than importing a test runner:
# typer >=0.27 vendors its CLI layer and no longer depends on click, so
# click.testing/typer.testing are absent from a plain `pip install -e .`.
env = dict(os.environ, HASS_SERVER="http://127.0.0.1:1", HASS_TOKEN="x",
           NO_COLOR="1", COLUMNS="200")
runner = [sys.executable, "-c", "from ha_tool.cli import app; app()"]

probe = subprocess.run([*runner, "--help"], capture_output=True, text=True, env=env)
if probe.returncode != 0:
    print("  - cannot run the CLI; is the package installed?")
    print((probe.stdout + probe.stderr).strip()[:400])
    sys.exit(1)

bad = 0
for doc in ("README.md", "skills/ha-tool.md", "AGENTS.md", "CONTRIBUTING.md", "CLAUDE.md"):
    p = pathlib.Path(doc)
    if not p.exists():
        continue
    for block in re.findall(r"```(?:bash|sh|console)?\n(.*?)```", p.read_text(), re.S):
        for line in block.splitlines():
            line = line.strip()
            # ```console blocks prefix commands with a shell prompt.
            if line.startswith("$ "):
                line = line[2:].strip()
            # Only check the ha-tool side of a pipeline; `| jq .state` is not ours.
            line = line.split("|")[0].strip()
            if not line.startswith("ha-tool ") or "--help" in line:
                continue
            try:
                args = shlex.split(line)[1:]
            except ValueError:
                continue
            # --help short-circuits before any network call, so this checks the
            # command name and flag names without contacting Home Assistant.
            result = subprocess.run([*runner, *args, "--help"],
                                    capture_output=True, text=True, env=env)
            text = result.stdout + result.stderr
            if any(m in text for m in ("No such command", "No such option", "Got unexpected")):
                detail = " ".join(
                    l.strip() for l in text.splitlines()
                    if "No such" in l or "unexpected" in l
                )
                print(f"  - {doc}: {line}\n      {detail.strip('│ ')}")
                bad += 1
sys.exit(1 if bad else 0)
PY

# --- Quality gate --------------------------------------------------------
# CI runs ruff/mypy in a dedicated lint job, so --docs-only skips them there
# rather than requiring the linters in every matrix job.
if [ "${1:-}" = "--docs-only" ]; then
    if [ "$fail" -ne 0 ]; then
        echo ""
        echo "✗ check-docs failed. See CONTRIBUTING.md → 'Adding a New Command'."
        exit 1
    fi
    echo "✓ documentation checks passed"
    exit 0
fi

# Lint the whole tree, as CI does; linting only ha_tool/ let violations land
# in tests/.
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
