# GitHub Actions OIDC Authentication with AWS

A comprehensive guide to secure, token-free CI/CD authentication between GitHub Actions and AWS using OpenID Connect (OIDC).

## Table of Contents

1. [Why OIDC?](#why-oidc)
2. [How OIDC Works](#how-oidc-works)
3. [Architecture](#architecture)
4. [Terraform Implementation](#terraform-implementation)
5. [GitHub Actions Configuration](#github-actions-configuration)
6. [Security Best Practices](#security-best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Learning Resources](#learning-resources)

---

## Why OIDC?

### The Problem with Long-Lived Credentials

Traditional CI/CD setups store AWS access keys as GitHub Secrets:

```
❌ Traditional Approach:
┌─────────────────┐     ┌─────────────────┐
│  GitHub Secrets │────▶│   AWS Account   │
│  - Access Key   │     │                 │
│  - Secret Key   │     │  (60+ day keys) │
└─────────────────┘     └─────────────────┘
```

**Problems:**
- **Security Risk**: Long-lived credentials can be stolen/leaked
- **Manual Rotation**: Keys must be rotated regularly (compliance burden)
- **Blast Radius**: Compromised keys have full access until revoked
- **Audit Gaps**: Hard to trace which workflow used credentials

### The OIDC Solution

OIDC replaces static credentials with temporary, automatically-rotating tokens:

```
✅ OIDC Approach:
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ GitHub Actions  │────▶│  AWS STS        │────▶│  AWS Resources  │
│ (JWT Token)     │     │  (Validates)    │     │  (1-hour creds) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Benefits:**
- **No Secrets to Manage**: No access keys stored anywhere
- **Auto-Expiration**: Credentials last only 1 hour
- **Fine-Grained Control**: Restrict by repo, branch, environment
- **Full Audit Trail**: Every assumption logged in CloudTrail
- **Zero Rotation**: Nothing to rotate - ever

---

## How OIDC Works

### The Authentication Flow

```
┌──────────────┐    1. Request JWT    ┌──────────────────┐
│   GitHub     │─────────────────────▶│  GitHub OIDC     │
│   Actions    │                      │  Provider        │
│   Workflow   │◀─────────────────────│                  │
└──────────────┘    2. Return JWT     └──────────────────┘
       │
       │ 3. Present JWT + Role ARN
       ▼
┌──────────────────┐
│   AWS STS        │
│   (Security      │
│   Token Service) │
└──────────────────┘
       │
       │ 4. Validate JWT against GitHub OIDC provider
       │ 5. Check trust policy conditions
       │ 6. Issue temporary credentials
       ▼
┌──────────────────┐
│  Temporary AWS   │
│  Credentials     │
│  (1 hour TTL)    │
└──────────────────┘
```

### JWT Token Claims

GitHub's OIDC token includes claims that AWS uses for authorization:

```json
{
  "iss": "https://token.actions.githubusercontent.com",
  "sub": "repo:silverbeer/myrunstreak.com:ref:refs/heads/main",
  "aud": "sts.amazonaws.com",
  "ref": "refs/heads/main",
  "repository": "silverbeer/myrunstreak.com",
  "repository_owner": "silverbeer",
  "actor": "silverbeer",
  "workflow": "Deploy Lambda Function",
  "event_name": "push"
}
```

**Key claims for trust policies:**
- `sub`: Subject - includes repo, ref, and context
- `aud`: Audience - always `sts.amazonaws.com` for AWS
- `repository`: Full repository name
- `ref`: Git reference (branch/tag)

---

## Architecture

### AWS Resources Created

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS Account                          │
│                                                             │
│  ┌─────────────────────────────────────┐                   │
│  │  IAM OIDC Identity Provider         │                   │
│  │  (token.actions.githubusercontent.com)                  │
│  └─────────────────────────────────────┘                   │
│                         │                                   │
│                         │ trusts                            │
│                         ▼                                   │
│  ┌─────────────────────────────────────┐                   │
│  │  IAM Role: github-actions-deploy    │                   │
│  │  ├─ Trust Policy (who can assume)   │                   │
│  │  └─ Permission Policies (what they  │                   │
│  │     can do)                         │                   │
│  │     ├─ Lambda deployment            │                   │
│  │     ├─ ECR push/pull                │                   │
│  │     ├─ S3 access                    │                   │
│  │     └─ CloudWatch logs              │                   │
│  └─────────────────────────────────────┘                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Terraform Implementation

All OIDC infrastructure is managed via Terraform - **100% Infrastructure as Code**.

### Module Location

```
terraform/modules/github_oidc/
├── main.tf        # Resources
├── variables.tf   # Input variables
└── outputs.tf     # Outputs
```

### Key Resources

#### 1. OIDC Identity Provider

Establishes trust between AWS and GitHub:

```hcl
# terraform/modules/github_oidc/main.tf

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  # Client ID - always "sts.amazonaws.com" for AWS
  client_id_list = ["sts.amazonaws.com"]

  # Thumbprint - AWS auto-validates for known providers
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]

  tags = {
    Name = "github-actions-oidc"
  }
}
```

**Why this matters:**
- Creates the trust relationship (one per AWS account)
- URL is GitHub's OIDC provider endpoint
- Thumbprint validates GitHub's SSL certificate

#### 2. IAM Role with Trust Policy

Defines WHO can assume the role:

```hcl
resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions-${var.environment}"

  # Trust Policy - WHO can assume this role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            # Restrict to specific repository
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/${var.github_repo}:*"
          }
        }
      }
    ]
  })
}
```

**Trust Policy Breakdown:**
- `Principal.Federated`: Trust the GitHub OIDC provider
- `Action`: Use `AssumeRoleWithWebIdentity` (OIDC-specific)
- `Condition.StringEquals`: Verify audience is AWS STS
- `Condition.StringLike`: Restrict to your repository

#### 3. Permission Policies

Defines WHAT the role can do:

```hcl
# Lambda deployment permissions
resource "aws_iam_role_policy" "lambda_deploy" {
  name = "lambda-deployment"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaUpdateCode"
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${var.account_id}:function:${var.project_name}-*"
      }
    ]
  })
}

# ECR push permissions
resource "aws_iam_role_policy" "ecr_push" {
  name = "ecr-push"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRGetAuthToken"
        Effect = "Allow"
        Action = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ECRPushPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = "arn:aws:ecr:${var.aws_region}:${var.account_id}:repository/${var.project_name}-*"
      }
    ]
  })
}
```

### Module Usage

In your environment configuration:

```hcl
# terraform/environments/dev/main.tf

module "github_oidc" {
  source = "../../modules/github_oidc"

  project_name = local.project_name
  environment  = var.environment
  account_id   = data.aws_caller_identity.current.account_id
  aws_region   = data.aws_region.current.name
  github_org   = "silverbeer"
  github_repo  = "myrunstreak.com"

  tags = local.common_tags
}

# Output the role ARN for GitHub Secrets
output "github_actions_role_arn" {
  description = "Set this as AWS_LAMBDA_DEPLOY_ROLE_ARN in GitHub Secrets"
  value       = module.github_oidc.deploy_role_arn
}
```

### Deploying the Infrastructure

```bash
cd terraform/environments/dev

# Initialize
terraform init

# Preview changes
terraform plan

# Apply
terraform apply

# Get the role ARN for GitHub
terraform output github_actions_role_arn
```

---

## GitHub Actions Configuration

### Workflow Permissions

Enable OIDC token generation in your workflow:

```yaml
# .github/workflows/lambda-deploy.yml

permissions:
  id-token: write   # Required for OIDC
  contents: read    # Required for checkout
```

### AWS Credentials Action

Use the official AWS action to assume the role:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.AWS_LAMBDA_DEPLOY_ROLE_ARN }}
    aws-region: us-east-2
```

### Complete Example

```yaml
name: Deploy Lambda

on:
  push:
    branches: [main]

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_LAMBDA_DEPLOY_ROLE_ARN }}
          aws-region: us-east-2

      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Deploy Lambda
        run: |
          aws lambda update-function-code \
            --function-name my-function \
            --image-uri $ECR_URI:latest
```

### GitHub Secret Setup

Add a single secret to your repository:

```bash
# Get the role ARN from Terraform
ROLE_ARN=$(terraform output -raw github_actions_role_arn)

# Set it as a GitHub secret
gh secret set AWS_LAMBDA_DEPLOY_ROLE_ARN --body "$ROLE_ARN"
```

That's it! No access keys, no secret keys - just one role ARN.

---

## Security Best Practices

### 1. Restrict by Repository

Always limit to specific repositories:

```hcl
"token.actions.githubusercontent.com:sub" = "repo:myorg/myrepo:*"
```

### 2. Restrict by Branch (Production)

For production, limit to specific branches:

```hcl
# Only allow from main branch
"token.actions.githubusercontent.com:sub" = "repo:myorg/myrepo:ref:refs/heads/main"
```

### 3. Restrict by Environment

Use GitHub Environments for deployment protection:

```hcl
# Only allow from production environment
"token.actions.githubusercontent.com:sub" = "repo:myorg/myrepo:environment:production"
```

### 4. Least Privilege Permissions

Only grant what's needed:

```hcl
# ✅ Good - specific resources
Resource = "arn:aws:lambda:us-east-2:123456789012:function:myproject-*"

# ❌ Bad - too broad
Resource = "*"
```

### 5. Audit Trail

All role assumptions are logged in CloudTrail:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity \
  --query 'Events[*].CloudTrailEvent' \
  --output text | jq .
```

---

## Troubleshooting

### Error: "Could not assume role"

**Causes:**
1. Role ARN is incorrect in GitHub Secrets
2. Trust policy doesn't match repository name
3. OIDC provider doesn't exist

**Debug:**
```bash
# Verify OIDC provider exists
aws iam list-open-id-connect-providers

# Check trust policy
aws iam get-role --role-name myrunstreak-github-actions-dev \
  --query 'Role.AssumeRolePolicyDocument' | jq .
```

### Error: "Not authorized to perform"

**Cause:** Role lacks required permissions

**Debug:**
```bash
# List attached policies
aws iam list-role-policies --role-name myrunstreak-github-actions-dev
aws iam list-attached-role-policies --role-name myrunstreak-github-actions-dev
```

### Error: "Token is expired"

**Cause:** Workflow took longer than token lifetime (1 hour)

**Solution:** Break up long-running workflows or increase session duration:

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.AWS_LAMBDA_DEPLOY_ROLE_ARN }}
    role-duration-seconds: 3600  # Default, max 43200 (12 hours)
```

---

## Learning Resources

### Official Documentation

- [GitHub: About security hardening with OpenID Connect](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [AWS: Creating OpenID Connect identity providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [AWS: Configure AWS Credentials Action](https://github.com/aws-actions/configure-aws-credentials)

### Tutorials & Articles

- [GitHub Blog: Secure deployments with OIDC](https://github.blog/2021-10-27-github-actions-oidc-for-secure-deployments/)
- [AWS Blog: Use IAM roles to connect GitHub Actions](https://aws.amazon.com/blogs/security/use-iam-roles-to-connect-github-actions-to-actions-in-aws/)

### Key Concepts

- **OIDC (OpenID Connect)**: Identity layer on top of OAuth 2.0
- **JWT (JSON Web Token)**: Signed token containing claims
- **STS (Security Token Service)**: AWS service that issues temporary credentials
- **Trust Policy**: IAM policy defining who can assume a role
- **Permission Policy**: IAM policy defining what actions are allowed

---

## Summary

OIDC provides secure, modern authentication between GitHub Actions and AWS:

| Aspect | Long-Lived Keys | OIDC |
|--------|----------------|------|
| Credential Lifetime | 90+ days | 1 hour |
| Rotation Required | Manual | Automatic |
| Storage | GitHub Secrets | None |
| Audit Trail | Limited | Full CloudTrail |
| Blast Radius | High | Low |
| Setup Complexity | Low | Medium |

**This project uses 100% Terraform for OIDC infrastructure** - see `terraform/modules/github_oidc/` for the complete implementation.

---

*This documentation is part of the MyRunStreak.com Infrastructure as Code (IaC) commitment. All infrastructure is managed via Terraform with no manual AWS CLI commands required.*
