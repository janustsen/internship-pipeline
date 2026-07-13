#!/usr/bin/env bash
# Local HYBRID half of the internship pipeline (2026-07-11 redesign).
#
# The cloud `internship-watch` routine now does the bulk collection itself —
# keyless ATS + Workday feeds + a WebSearch discovery net — so it needs no
# laptop. This local job exists ONLY for the one source the cloud can't reach:
# **Handshake** (Stanford's job board, behind an SSO'd Chrome profile). It runs
# Handshake-only, writes `handshake_candidates.json`, and pushes it to the bridge
# repo for the cloud routine to merge in.
#
# Push is RESILIENT: the old job hard-failed at 06:00 when the Mac had just woken
# and Wi-Fi wasn't up yet ("could not resolve host"). We now retry the push until
# the network is available, so a momentary offline wake no longer loses the run.
set -uo pipefail   # not -e: a Handshake hiccup must not abort before the push/log

REPO="${INTERNSHIP_REPO:-$HOME/dev/internship-pipeline}"
cd "$REPO" || exit 1
mkdir -p "$REPO/logs"
LOG="$REPO/logs/run-$(date +%Y%m%d).log"

{
  echo "==================================================================="
  echo "handshake-only collector run — $(date)"
  git pull --rebase --autostash origin main || echo "warn: git pull failed, continuing"

  # Handshake ONLY → its own drop file. Cloud owns ATS/Workday/discovery.
  # --no-push: this script owns the (resilient) push below.
  "$REPO/venv/bin/python" "$REPO/collector.py" \
      --sources handshake \
      --artifact handshake_candidates.json \
      --no-tracker --no-push \
      || echo "warn: handshake collect failed (missing Chrome profile / login?) — continuing"

  git add handshake_candidates.json 2>/dev/null || true
  if git diff --cached --quiet 2>/dev/null; then
    echo "no handshake changes to push"
  else
    git commit -m "handshake drop $(date -u +%FT%TZ)" || true
    pushed=""
    for attempt in 1 2 3 4 5 6; do
      if git push origin main; then echo "pushed on attempt $attempt"; pushed=1; break; fi
      echo "push attempt $attempt failed (network likely not up yet) — retry in 60s"
      sleep 60
    done
    [ -z "$pushed" ] && echo "ERROR: push never succeeded — handshake drop is committed locally, will push next run"
  fi
  echo "done — $(date)"
} >> "$LOG" 2>&1
