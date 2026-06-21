# k3s splits backfill (SB-184)

A slow, polite background process on your k3s mini that fills in per-mile
**splits** for your whole run history — without overwhelming the SmashRun API
or tripping the backend's request timeouts.

## How it works

The backend already exposes a batched, rate-limited backfill. The fragility was
only ever from driving *big* batches inside one HTTP request. So we drive
**tiny** batches on a timer:

```
CronJob ─every 5 min─▶ stk splits status (skip if done)
                       stk splits backfill --limit 5 --max-batches 1
```

5 runs every 5 minutes ≈ 60 runs/hour → a ~4,700-run history completes in a few
days, as a barely-there trickle. Each tick no-ops once nothing remains.

**Auth:** a tiny PVC (`stk-session`) holds stk's `session.json`. You log in
once into a bootstrap pod; the CronJob mounts the same PVC, and stk's rotated
refresh token is written back to the PVC so it survives across ticks. No
password is stored in the cluster.

## Prerequisites

- k3s on the mini with `kubectl` access and the default `local-path` storage
  class (k3s ships it).
- The **stk image** built + pushed: `ghcr.io/silverbeer/myrunstreak-stk:latest`.
  The `stk image` GitHub Action builds it (multi-arch) on any change under
  `stk/`; trigger it once via *Actions → stk image → Run workflow* if needed.
- Image must be **pullable by the mini**. Easiest: make the `myrunstreak-stk`
  package **public** (GitHub → Packages → myrunstreak-stk → Package settings →
  Change visibility). Otherwise create a pull secret (see Troubleshooting).

## Install

```bash
# 1. namespace + session volume
kubectl apply -f ops/k3s/pvc.yaml

# 2. one-time login (writes session.json onto the PVC)
kubectl apply -f ops/k3s/bootstrap-login-pod.yaml
kubectl wait -n myrunstreak --for=condition=Ready pod/stk-login --timeout=120s
kubectl exec -it -n myrunstreak stk-login -- stk auth login      # email + password
kubectl exec      -n myrunstreak stk-login -- stk splits status   # sanity check
kubectl delete pod -n myrunstreak stk-login

# 3. start the trickle
kubectl apply -f ops/k3s/cronjob.yaml
```

## Status / report issues

```bash
kubectl get cronjob,jobs,pods -n myrunstreak           # schedule + recent ticks
kubectl logs -n myrunstreak -l job-name --tail=20 --prefix   # tick output
stk splits status                                      # from your laptop, anytime
#   … splits: 1840/4700 runs (39.1%) — 2860 remaining
```

Each tick logs `remaining=N` and either the backfill summary or `done`.

## Tuning

Edit `ops/k3s/cronjob.yaml` and re-apply:
- `BATCH` env — runs per tick (default `5`)
- `schedule` — cron cadence (default every 5 min)

Backfill is idempotent, so changing the rate mid-run is safe.

## Pause / stop

```bash
# pause without deleting
kubectl patch cronjob splits-backfill -n myrunstreak -p '{"spec":{"suspend":true}}'
# or remove entirely (PVC + session stay)
kubectl delete -f ops/k3s/cronjob.yaml
```

When `stk splits status` shows `done`, ticks already no-op — you can leave it or
delete it.

## Troubleshooting

- **`ImagePullBackOff`** → the package is private. Make it public (above) or
  create a pull secret and add it to the pod specs:
  ```bash
  kubectl create secret docker-registry ghcr -n myrunstreak \
    --docker-server=ghcr.io --docker-username=<gh-user> \
    --docker-password=<gh-PAT-with-read:packages>
  # then add under each pod spec:  imagePullSecrets: [{name: ghcr}]
  ```
- **Auth errors in the tick log** → session expired/revoked; redo step 2
  (bootstrap login) to refresh `session.json` on the PVC.
- **Nothing progresses** → `kubectl describe cronjob splits-backfill -n
  myrunstreak` and check the last job's pod logs.
