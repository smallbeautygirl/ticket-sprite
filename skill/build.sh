#!/usr/bin/env bash
# Refresh the bundled Knowledge Source from the repo's main branch and zip the skill
# for upload in claude.ai (Settings → Capabilities → Skills).
set -euo pipefail

REPO="${REPO:-/opt/lighthouse-saas-api}"
BRANCH="${BRANCH:-origin/main}"  # last fetched GitHub main
PRODUCT="apps/visionai_middleware"
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HERE/ticket-sprite/knowledge/middleware"

rm -rf "$DEST" && mkdir -p "$DEST/adr"
git -C "$REPO" show "$BRANCH:$PRODUCT/CONTEXT.md" > "$DEST/CONTEXT.md"
git -C "$REPO" ls-tree --name-only "$BRANCH" "$PRODUCT/docs/adr/" | grep '\.md$' | while read -r f; do
  git -C "$REPO" show "$BRANCH:$f" > "$DEST/adr/$(basename "$f")"
done
{
  echo "# Middleware ADR index"
  echo
  echo "Source: \`$PRODUCT/docs/adr\` @ $BRANCH ($(git -C "$REPO" rev-parse --short "$BRANCH"))"
  echo
  for f in "$DEST"/adr/*.md; do
    echo "- [$(basename "$f")](adr/$(basename "$f")) — $(grep -m1 '^# ' "$f" | sed 's/^# //')"
  done
} > "$DEST/ADR-INDEX.md"

rm -f "$HERE/ticket-sprite.zip"
(cd "$HERE" && python3 -c "import shutil; shutil.make_archive('ticket-sprite', 'zip', '.', 'ticket-sprite')")
echo "built $HERE/ticket-sprite.zip from $BRANCH@$(git -C "$REPO" rev-parse --short "$BRANCH")"
