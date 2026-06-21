#!/usr/bin/env bash
#
# At-a-glance health of the splits backfill: is the launchd job loaded, how far
# along is the backfill, the last few ticks, and any recent errors. SB-184.
LOG_DIR="${STK_BACKFILL_LOG_DIR:-$HOME/Library/Logs/myrunstreak}"
STK="${STK_BIN:-stk}"
LOG="$LOG_DIR/backfill-splits.log"
LABEL="com.myrunstreak.backfill-splits"

echo "== launchd job =="
if launchctl list | grep -q "$LABEL"; then
  launchctl list | grep "$LABEL"
else
  echo "  NOT loaded — run: launchctl load ~/Library/LaunchAgents/$LABEL.plist"
fi

echo
echo "== progress =="
"$STK" splits status || echo "  (could not reach API — check 'stk auth status')"

echo
echo "== last 5 ticks =="
tail -n 5 "$LOG" 2>/dev/null || echo "  no log yet at $LOG"

echo
echo "== recent errors =="
grep -i error "$LOG" 2>/dev/null | tail -n 5 || echo "  none 🎉"
