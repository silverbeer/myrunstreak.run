# Production Deployment

Production runs on **Linode Kubernetes Engine (LKE)**. Deployment is **GitOps**:
GitHub Actions build images to GHCR and bump the image tag in the Helm chart;
**ArgoCD** reconciles the chart onto the cluster. There is no manual `kubectl
apply` in the normal flow.

## The pipeline

```
push to main (backend/** | frontend/** | src/shared/** | helm/**)
   │
   ▼  GitHub Actions  (backend-deploy / frontend-deploy)
build Docker image (linux/amd64) ──► push to GHCR (tag = short SHA)
   │
   ▼  sed-bump helm/myrunstreak/values.yaml  (image.tag / backend.image.tag)
auto-commit "ci: update ... image tag ... [skip ci]"
   │
   ▼  ArgoCD watches the chart
reconcile onto LKE
```

- **Backend** image: `ghcr.io/silverbeer/myrunstreak-backend`, tag pinned at
  `backend.image.tag` (marker `# backend-tag`).
- **Frontend** image: `ghcr.io/silverbeer/myrunstreak-frontend`, tag pinned at
  `image.tag` (marker `# frontend-tag`).
- Automated tag-bump commits carry `[skip ci]` so they don't re-trigger CI.

## Helm chart (`helm/myrunstreak/`)

Templates: `backend.yaml`, `frontend.yaml`, `redis.yaml`, `ingress.yaml`,
`external-secret.yaml`, `cronjob-sync.yaml`, `cronjob-publish-status.yaml`.

Key `values.yaml` toggles:

| Value | Meaning |
|-------|---------|
| `image.tag` / `backend.image.tag` | deployed frontend / backend images |
| `backend.enabled`, `redis.enabled` | feature toggles |
| `backend.cronjobs.sync.schedule` | `0 14,17 * * *` UTC daily sync |
| `backend.cronjobs.publishStatus.schedule` | `*/15 * * * *` status publish |
| `ingress.hosts` / `ingress.apiHosts` | `myrunstreak.run` / `api.myrunstreak.run` |
| `externalSecret.awsSecretName` | `myrunstreak-app-secrets` |

## Database (Supabase)

- Production uses a managed **Supabase** project. Schema changes are SQL
  migrations in `supabase/migrations/`, applied by the **`supabase-migrations`**
  workflow on merge to `main` (`supabase db push`).
- The backend reads the Supabase URL + keys + JWT secret from the app secret
  (below). The service-role key bypasses RLS — keep it secret.

## Secrets

A single AWS Secrets Manager secret, **`myrunstreak-app-secrets`**, holds
Supabase keys, the JWT secret, and the SmashRun OAuth client credentials. The
**External Secrets Operator** syncs it into a K8s `Secret` named
`myrunstreak-secrets` (`refreshInterval: 1h`), defined by
`helm/myrunstreak/templates/external-secret.yaml`.

To rotate: edit the secret in AWS Secrets Manager; ESO re-syncs within the
refresh interval (or delete the ExternalSecret's target to force an immediate
re-pull). See [TERRAFORM.md](TERRAFORM.md).

## Manual operations (rare)

```bash
# Inspect what ArgoCD deployed
helm -n <ns> get values myrunstreak

# Render the chart locally to review changes
helm template helm/myrunstreak -f helm/myrunstreak/values.yaml

# Trigger a sync out-of-band (or just wait for the CronJob)
kubectl -n <ns> create job --from=cronjob/<sync-cronjob> manual-sync-$(date +%s)
```

Prefer the GitOps path; reserve manual `kubectl`/`helm` for inspection and
break-glass.

## Rollback

Revert the tag-bump commit (or set the previous `image.tag` in `values.yaml`)
and let ArgoCD reconcile back. Database changes roll back via a new forward
migration — never edit an applied migration.

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) · [TERRAFORM.md](TERRAFORM.md) ·
  [SUPABASE_MIGRATION.md](SUPABASE_MIGRATION.md)
