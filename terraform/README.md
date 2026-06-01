# Terraform

This directory manages **only** the Terraform state backend and a reference to
the app's AWS Secrets Manager secret. **No application infrastructure lives
here** — the app runs on Linode Kubernetes via the Helm chart in
`helm/myrunstreak/`, deployed by ArgoCD.

The AWS Lambda / API Gateway / EventBridge / S3 modules that used to live under
`modules/` were removed in the LKE migration ("Phase C").

## Layout

```
terraform/
├── bootstrap/          # one-time: S3 bucket + lock table for remote state
└── environments/dev/   # ~40 lines: backend config + ASM secret reference
```

## Usage

```bash
cd terraform/environments/dev
terraform init && terraform plan && terraform apply
```

Full notes: [`docs/TERRAFORM.md`](../docs/TERRAFORM.md).

**Never commit** `terraform.tfvars` or `*.tfstate`.
