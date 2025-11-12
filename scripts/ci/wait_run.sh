#!/usr/bin/env bash
set -euo pipefail
owner="WaterLfHonda"; repo="TrendRadar"
branch="${1:-ci/pages-pipeline}"
if [[ -z "${GH_PAT:-}" ]]; then
  echo "missing GH_PAT" >&2; exit 1
fi

runs_api="https://api.github.com/repos/${owner}/${repo}/actions/runs?branch=${branch}&event=workflow_dispatch&per_page=5"

attempts=40
sleep 5
for ((i=1;i<=attempts;i++)); do
  resp=$(curl -sS -H "Accept: application/vnd.github+json" -H "Authorization: Bearer ${GH_PAT}" "$runs_api")
  count=$(printf '%s' "$resp" | python3 -c 'import sys,json; j=json.load(sys.stdin); print(len(j.get("workflow_runs",[])))')
  runid=$(printf '%s' "$resp" | python3 -c 'import sys,json; j=json.load(sys.stdin); rs=j.get("workflow_runs",[]); print(rs[0]["id"] if rs else "")')
  html=$(printf '%s' "$resp" | python3 -c 'import sys,json; j=json.load(sys.stdin); rs=j.get("workflow_runs",[]); print(rs[0]["html_url"] if rs else "")')
  status=$(printf '%s' "$resp" | python3 -c 'import sys,json; j=json.load(sys.stdin); rs=j.get("workflow_runs",[]); print(rs[0]["status"] if rs else "")')
  conclusion=$(printf '%s' "$resp" | python3 -c 'import sys,json; j=json.load(sys.stdin); rs=j.get("workflow_runs",[]); print(rs[0]["conclusion"] if rs else "")')
  if [[ -z "$runid" ]]; then
    sleep 5; continue
  fi
  echo "RUN_ID=$runid"
  echo "RUN_URL=$html"
  if [[ "$status" == "completed" ]]; then
    echo "CONCLUSION=$conclusion"; exit 0
  fi
  sleep 15
  # fetch status of this run specifically
  resp2=$(curl -sS -H "Accept: application/vnd.github+json" -H "Authorization: Bearer ${GH_PAT}" "https://api.github.com/repos/${owner}/${repo}/actions/runs/${runid}")
  status=$(printf '%s' "$resp2" | python3 -c 'import sys,json; j=json.load(sys.stdin); print(j.get("status",""))')
  conclusion=$(printf '%s' "$resp2" | python3 -c 'import sys,json; j=json.load(sys.stdin); print(j.get("conclusion",""))')
  if [[ "$status" == "completed" ]]; then
    echo "CONCLUSION=$conclusion"; exit 0
  fi
  sleep 15
done

echo "TIMEOUT waiting for workflow run" >&2; exit 2
