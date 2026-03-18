#!/bin/bash
# Install ha-tool skill for Claude Code

set -e

SKILL_DIR="$HOME/.claude/commands"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$SKILL_DIR"

cp "$REPO_DIR/skills/ha-tool.md" "$SKILL_DIR/ha-tool.md"

echo "✓ Installed ha-tool skill to $SKILL_DIR/ha-tool.md"
echo ""
echo "Claude Code can now use ha-tool in any project."
echo "Make sure HASS_SERVER and HASS_TOKEN are set in your environment."
