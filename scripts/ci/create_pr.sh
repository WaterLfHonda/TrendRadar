#!/usr/bin/env bash
set -euo pipefail
owner="WaterLfHonda"; repo="TrendRadar"; head="ci/pages-pipeline"
base=$(git remote show origin | sed -n '/HEAD branch/s/.*: //p'); base=${base:-master}
# fallback if base not exists on remote
if ! git ls-remote --exit-code --heads origin "$base" >/dev/null 2>&1; then
  base=main
fi

title="Automate crawler + Pages deployment"
body="Enable hourly crawl and Pages deployment; base config defaults; README updates."

if [[ -z "${GH_PAT:-}" ]]; then
  echo "[info] GH_PAT not set; open one of these links to create PR:" >&2
  echo "https://github.com/${owner}/${repo}/compare/${base}...${head}?expand=1"
  if [[ "$base" != "main" ]]; then
    echo "https://github.com/${owner}/${repo}/compare/main...${head}?expand=1"
  fi
  exit 0
fi

resp=$(curl -sSL -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GH_PAT}" \
  "https://api.github.com/repos/${owner}/${repo}/pulls" \
  -d "{\"title\":\"${title}\",\"head\":\"${head}\",\"base\":\"${base}\",\"body\":\"${body}\"}")

num=$(printf '%s' "$resp" | python3 -c 'import sys, json; j=json.load(sys.stdin); print(j.get("number",""))')
url=$(printf '%s' "$resp" | python3 -c 'import sys, json; j=json.load(sys.stdin); print(j.get("html_url",""))')
if [[ -n "$num" && -n "$url" ]]; then
  echo "PR_NUMBER=$num"
  echo "PR_URL=$url"
else
  echo "$resp" | sed -n '1,120p' >&2
  exit 1
fi
