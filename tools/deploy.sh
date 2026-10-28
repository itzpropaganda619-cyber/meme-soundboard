#!/usr/bin/env bash
# Commit + push public/ to GitHub, then make sure Render redeploys.
set -euo pipefail
cd "$(dirname "$0")/.."
MSG="${1:-Update soundboard}"
git add -A
git diff --cached --quiet && echo "nothing to commit" || git commit -qm "$MSG"
git push -q origin main
echo "pushed $(git rev-parse --short HEAD)"
# Render: auto-deploys on push if the repo is linked via Render's GitHub app.
# Otherwise trigger via a deploy hook URL (Render dashboard > service > Settings > Deploy Hook) saved in tools/.render_deploy_hook,
# or via the Render API if RENDER_API_KEY + tools/.render_service_id exist.
if [[ -s tools/.render_deploy_hook ]]; then
  curl -fsS -X POST "$(cat tools/.render_deploy_hook)" >/dev/null && echo "Render deploy hook triggered"
elif [[ -n "${RENDER_API_KEY:-}" && -s tools/.render_service_id ]]; then
  curl -fsS -X POST -H "Authorization: Bearer $RENDER_API_KEY" -H "Accept: application/json" \
    "https://api.render.com/v1/services/$(cat tools/.render_service_id)/deploys" -d '{}' >/dev/null && echo "Render API deploy triggered"
else
  echo "NOTE: no deploy hook/API key on box; if Render doesn't auto-deploy, trigger it (Render MCP trigger_deploy)."
fi
# GitHub Pages mirror: publish public/ to the gh-pages branch (Pages rebuilds automatically, no extra auth needed)
SPLIT=$(git subtree split --prefix public main 2>/dev/null)
git push -qf origin "$SPLIT:refs/heads/gh-pages" && echo "gh-pages updated (GitHub Pages mirror rebuilds in ~1 min)"
