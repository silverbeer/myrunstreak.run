#!/usr/bin/env bash
#
# One gentle splits-backfill "tick": process a small batch of runs that are
# still missing per-mile splits, then exit. launchd runs this on an interval
# (see com.myrunstreak.backfill-splits.plist), so many small ticks add up to a
# full-history backfill without ever overwhelming the SmashRun API or timing
# out a request. SB-184.
#
# Tunables (env, set in the plist):
#   STK_BACKFILL_BATCH      runs per tick           (default 5)
#   STK_BACKFILL_LOG_DIR    where to write the log  (default ~/Library/Logs/myrunstreak)
#   STK_BIN                 path to the stk binary  (default: stk on PATH)
set -uo pipefail

BATCH="${STK_BACKFILL_BATCH:-5}"
LOG_DIR="${STK_BACKFILL_LOG_DIR:-$HOME/Library/Logs/myrunstreak}"
STK="${STK_BIN:-stk}"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/backfill-splits.log"

ts() { date "+%Y-%m-%dT%H:%M:%S%z"; }
log() { echo "$(ts) $*" >> "$LOG"; }

# Cheap read-only check first: if nothing remains, no-op (and don't hammer the
# API). If the status call fails (e.g. auth expired), record it clearly.
STATUS_JSON="$("$STK" splits status --json 2>>"$LOG")"
REMAINING="$(printf '%s' "$STATUS_JSON" \
  | /usr/bin/python3 -c 'import sys,json; print(json.load(sys.stdin).get("runs_missing_splits",""))' 2>/dev/null)"

if [ -z "$REMAINING" ]; then
  log "ERROR could not read status — is stk authed? run 'stk auth status'"
  exit 1
fi
if [ "$REMAINING" = "0" ]; then
  log "done — 0 remaining; nothing to do"
  exit 0
fi

OUT="$("$STK" splits backfill --limit "$BATCH" --max-batches 1 2>&1)"
RC=$?
SUMMARY="$(printf '%s' "$OUT" | tr '\n' ' ' | sed 's/  */ /g')"
if [ $RC -eq 0 ]; then
  log "ok batch=$BATCH remaining_before=$REMAINING :: $SUMMARY"
else
  log "ERROR rc=$RC :: $SUMMARY"
fi
exit $RC
