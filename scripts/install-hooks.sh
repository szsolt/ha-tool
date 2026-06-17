#!/usr/bin/env bash
# Install ha-tool git hooks. Run once after cloning: ./scripts/install-hooks.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
HOOK="$REPO_DIR/.git/hooks/pre-commit"

cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
exec "$(git rev-parse --show-toplevel)/scripts/check-docs.sh"
EOF
chmod +x "$HOOK"

echo "✓ Installed pre-commit hook → $HOOK"
echo "  It runs scripts/check-docs.sh on every commit."
