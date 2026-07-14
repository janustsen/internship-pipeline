#!/usr/bin/env bash
# Manual / backup local collector for the internship pipeline.
#
# PRIMARY host is now GitHub Actions (.github/workflows/collect-internships.yml):
# the keyless collection makes direct HTTP calls to greenhouse/*.myworkdayjobs.com,
# which the Claude cloud sandbox blocks ("egress policy denied all ATS/Workday
# hosts") but Actions runners allow — free, no laptop. This script does the same
# KEYLESS collection (ATS + Workday via cloud_collect.py) on the Mac and is kept
# only as a manual/backup runner; disable the launchd plist so it doesn't
# double-collect with Actions. Handshake has been retired.
set -uo pipefail   # not -e: a single source hiccup must not abort before the push

REPO="${INTERNSHIP_REPO:-$HOME/dev/internship-pipeline}"
PY="$REPO/venv/bin/python"
cd "$REPO" || exit 1
mkdir -p "$REPO/logs"
LOG="$REPO/logs/run-$(date +%Y%m%d).log"

{
  echo "==================================================================="
  echo "internship collector run — $(date)"
  git pull --rebase --autostash origin main || echo "warn: git pull failed, continuing"

  # (1) Keyless ATS + Workday feeds → todays_candidates.json + advance
  #     seen_postings.json (dedup state committed in the repo).
  "$PY" "$REPO/cloud_collect.py" || echo "warn: cloud_collect failed"

  # (2) Resilient push of the bridge artifacts (retry until network is up).
  git add todays_candidates.json seen_postings.json 2>/dev/null || true
  if git diff --cached --quiet 2>/dev/null; then
    echo "no candidate changes to push"
  else
    git commit -m "collector: refresh candidates $(date -u +%FT%TZ)" || true
    pushed=""
    for attempt in 1 2 3 4 5 6; do
      if git push origin main; then echo "pushed on attempt $attempt"; pushed=1; break; fi
      echo "push attempt $attempt failed (network likely not up yet) — retry in 60s"
      sleep 60
    done
    [ -z "$pushed" ] && echo "ERROR: push never succeeded — committed locally, will push next run"
  fi
  echo "done — $(date)"
} >> "$LOG" 2>&1
