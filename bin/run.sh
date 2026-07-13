#!/usr/bin/env bash
# Local collection half of the internship pipeline (2026-07-12).
#
# WHY LOCAL: the cloud routine's sandbox blocks outbound egress to the job-feed
# hosts (greenhouse / *.myworkdayjobs.com / etc.) — a test run returned 0 with
# "egress policy denied all ATS/Workday hosts". So the feed fetching must run
# where egress is open: here. The Mac already has the keys-free ATS + Workday
# reach and the SSO'd Handshake browser. The cloud routine (internship-watch)
# then JUDGES the artifact this job pushes.
#
# This runs the full KEYLESS collection (ATS + Workday via cloud_collect.py) plus
# Handshake, and pushes the artifacts with a RESILIENT push that retries until
# the network is up — fixing the old 6am "could not resolve host" hard-fail.
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

  # (1) Handshake → its own drop file (the one source only this machine can reach).
  #     Skips itself cleanly if the Chrome profile / search URL isn't configured.
  "$PY" "$REPO/collector.py" --sources handshake \
       --artifact handshake_candidates.json --no-tracker --no-push \
       || echo "warn: handshake collect skipped/failed — continuing"

  # (2) Keyless ATS + Workday feeds + merge the Handshake drop → todays_candidates.json
  #     + advance seen_postings.json (dedup state committed in the repo).
  "$PY" "$REPO/cloud_collect.py" || echo "warn: cloud_collect failed"

  # (3) Resilient push of the bridge artifacts (retry until network is up).
  git add todays_candidates.json seen_postings.json handshake_candidates.json 2>/dev/null || true
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
