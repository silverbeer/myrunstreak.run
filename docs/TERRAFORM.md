# Terraform

Terraform's footprint is intentionally tiny. **No application infrastructure is
managed by Terraform** — all of that is the Helm chart (`helm/myrunstreak/`)
deployed to LKE by ArgoCD. See [ARCHITECTURE.md](ARCHITECTURE.md).

## What Terraform still manages

As of the LKE migration ("Phase C"), the dev environment
(`terraform/environments/dev/`, ~40 lines) covers only:

- The **Terraform state backend** itself (AWS S3 + lock table).
- A reference to the manually-managed AWS Secrets Manager secret
  **`myrunstreak-app-secrets`**, which the External Secrets Operator pulls into
  the cluster.

Everything else — Lambda × 4, ECR × 4, API Gateway, EventBridge, IAM, GitHub
OIDC, the S3 data bucket, and all the reusable modules — was **removed** in the
migration. (The big `TERRAFORM_BOOTSTRAP.md` / `TERRAFORM_GUIDE.md` guides that
documented them were deleted with this housekeeping pass.)

## Usage

```bash
cd terraform/environments/dev
terraform init        # uses the S3 backend
terraform plan
terraform apply
```

Convenience Make targets exist: `make bootstrap-tf`, `make init-tf`,
`make plan-tf`, `make apply-tf`, `make destroy-tf`.

## Rotating the app secret

The secret is managed **outside** Terraform (created/edited directly in AWS
Secrets Manager). The External Secrets Operator re-syncs it into a K8s `Secret`
on its `refreshInterval` (1h) — see `helm/myrunstreak/templates/external-secret.yaml`.
