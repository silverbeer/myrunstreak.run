# Mac-mini splits backfill (SB-184)

A slow, polite background process that fills in per-mile **splits** for your
whole run history — without overwhelming the SmashRun API or tripping the
backend's request timeouts.

## How it works

The backend already exposes a batched, rate-limited backfill (`stk splits
backfill`). The fragility was only ever from driving *big* batches inside one
HTTP request. So instead we drive **tiny** batches on a timer:

```
launchd ──every 5 min──▶ backfill-splits.sh ──▶ stk splits backfill --limit 5 --max-batches 1
```

5 runs every 5 minutes ≈ 60 runs/hour → a ~4,700-run history completes in a few
days, as a barely-there trickle. The job no-ops once nothing remains.

## One-time setup (on the Mac mini)

1. **Install + auth stk** (durable login, SB-170):
   ```bash
   uv tool install /path/to/repo/stk        # or: git pull && uv tool install ./stk
   stk auth login                            # email + password
   stk splits status                         # sanity: shows runs remaining
   ```
2. **Copy the scripts** somewhere stable, e.g. `~/myrunstreak-ops/`:
   ```bash
   mkdir -p ~/myrunstreak-ops
   cp ops/macmini/backfill-splits.sh ops/macmini/backfill-status.sh ~/myrunstreak-ops/
   chmod +x ~/myrunstreak-ops/*.sh
   ```
3. **Install the launchd agent** — fill in your home dir, then load:
   ```bash
   sed "s#__HOME__#$HOME#g" ops/macmini/com.myrunstreak.backfill-splits.plist \
     > ~/Library/LaunchAgents/com.myrunstreak.backfill-splits.plist
   launchctl load ~/Library/LaunchAgents/com.myrunstreak.backfill-splits.plist
   ```

That's it. It starts immediately (`RunAtLoad`) and ticks every 5 minutes.

## Check status / report issues

```bash
~/myrunstreak-ops/backfill-status.sh
```
Shows: whether the job is loaded, backfill progress (`stk splits status`), the
last few ticks, and any recent errors. Or just:
```bash
stk splits status                 #  … splits: 1840/4700 runs (39.1%) — 2860 remaining
```

Logs live at `~/Library/Logs/myrunstreak/`:
- `backfill-splits.log` — one line per tick (`ok …` / `ERROR …`)
- `launchd.out.log` / `launchd.err.log` — raw launchd capture

## Tuning

Edit the env vars in `~/Library/LaunchAgents/com.myrunstreak.backfill-splits.plist`,
then `launchctl unload` + `load` to apply:
- `STK_BACKFILL_BATCH` — runs per tick (default `5`)
- `StartInterval` — seconds between ticks (default `300`)

## Stop it

When `stk splits status` shows `done` (0 remaining) the job already no-ops, but
to remove it entirely:
```bash
launchctl unload ~/Library/LaunchAgents/com.myrunstreak.backfill-splits.plist
```

## Troubleshooting

- **`ERROR could not read status — is stk authed?`** → session expired; run
  `stk auth login` again on the mini.
- **Nothing happens / `stk: command not found` in the log** → the plist's `PATH`
  / `STK_BIN` don't point at your stk. Confirm `which stk` and fix the plist.
- **Want it faster/slower** → see Tuning above. Backfill is idempotent, so
  changing the rate mid-run is safe.
