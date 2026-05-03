# MyRunStreak.com - Development Environment
#
# As of Phase C of the LKE migration, ALL application infrastructure runs on
# Linode Kubernetes Engine (Helm chart in helm/myrunstreak/). The only AWS
# resource still required is the terraform state backend itself, plus the
# manually-managed AWS Secrets Manager secret `myrunstreak-app-secrets` which
# the External Secrets Operator pulls from.
#
# Removed in Phase C: Lambda × 4, ECR × 4, API Gateway routes, EventBridge
# rules, IAM roles, GitHub OIDC, terraform-managed secrets, S3 data bucket.
# Module source code (terraform/modules/*) is retained for reference.

terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "myrunstreak-terraform-state-855323747881"
    key            = "myrunstreak/dev/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "myrunstreak-terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "MyRunStreak"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
