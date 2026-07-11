#!/usr/bin/env bash
# Local half of the internship pipeline. Runs the collector, which writes
# todays_candidates.json and commits+pushes it to the git bridge for the cloud
# internship-watch routine to read. Invoked daily ~06:00 PT by launchd.
set -euo pipefail

REPO="${INTERNSHIP_REPO:-$HOME/dev/internship-pipeline}"
cd "$REPO"
mkdir -p "$REPO/logs"
LOG="$REPO/logs/run-$(date +%Y%m%d).log"

{
  echo "==================================================================="
  echo "internship collector run — $(date)"
  # Pull first so the artifact push never conflicts with the remote.
  git pull --rebase --autostash origin main || echo "warn: git pull failed, continuing"
  # Run every source; sources without configured keys skip themselves, a dead
  # source (e.g. Handshake without a logged-in browser) is logged and skipped.
  "$REPO/venv/bin/python" "$REPO/collector.py"
  echo "done — $(date)"
} >> "$LOG" 2>&1
