# MyRunStreak.com - Development Environment
# This is the main Terraform configuration for the dev environment

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

# Data source to get current AWS account ID
data "aws_caller_identity" "current" {}

# Data source to get current AWS region
data "aws_region" "current" {}

locals {
  project_name = "myrunstreak"
  common_tags = {
    Project     = "MyRunStreak"
    Environment = var.environment
  }
}

# ==============================================================================
# Module: IAM Roles and Policies
# ==============================================================================
# Create Lambda execution role before other resources that depend on it

module "iam" {
  source = "../../modules/iam"

  project_name = local.project_name
  environment  = var.environment
  account_id   = data.aws_caller_identity.current.account_id
  aws_region   = data.aws_region.current.name

  # S3 bucket ARN will be provided by s3 module
  s3_bucket_arn = module.s3.bucket_arn

  tags = local.common_tags
}

# ==============================================================================
# Module: S3 Bucket for DuckDB Database
# ==============================================================================
# Store runs.duckdb file with versioning and encryption

module "s3" {
  source = "../../modules/s3"

  project_name              = local.project_name
  environment               = var.environment
  account_id                = data.aws_caller_identity.current.account_id
  lambda_execution_role_arn = module.iam.lambda_execution_role_arn

  # Optional features
  enable_cors       = false  # Enable if building web UI
  enable_monitoring = true   # CloudWatch alarms for bucket size

  tags = local.common_tags
}

# ==============================================================================
# Module: Secrets Manager
# ==============================================================================
# Store SmashRun OAuth credentials and API keys securely

module "secrets" {
  source = "../../modules/secrets"

  project_name = local.project_name
  environment  = var.environment

  # SmashRun OAuth credentials (from terraform.tfvars - not committed to git)
  smashrun_client_id     = var.smashrun_client_id
  smashrun_client_secret = var.smashrun_client_secret
  smashrun_access_token  = var.smashrun_access_token
  smashrun_refresh_token = var.smashrun_refresh_token

  # API Gateway API key
  api_key_personal = var.api_key_personal

  # Supabase credentials
  supabase_url              = var.supabase_url
  supabase_service_role_key = var.supabase_service_role_key

  # Optional features
  enable_rotation      = false  # Manual token management for now
  enable_age_monitoring = false  # Optional alarm for stale secrets

  tags = local.common_tags
}

# ==============================================================================
# Module: ECR Repositories
# ==============================================================================
# Container registries for Lambda function images

module "ecr" {
  source = "../../modules/ecr"

  project_name = local.project_name
  environment  = var.environment
  account_id   = data.aws_caller_identity.current.account_id

  # Keep last 10 images to allow rollback
  image_retention_count = 10

  tags = local.common_tags
}

# ==============================================================================
# Module: GitHub OIDC Authentication
# ==============================================================================
# Secure CI/CD authentication without long-lived credentials

module "github_oidc" {
  source = "../../modules/github_oidc"

  project_name = local.project_name
  environment  = var.environment
  account_id   = data.aws_caller_identity.current.account_id
  aws_region   = data.aws_region.current.name

  # GitHub repository configuration
  github_org  = var.github_org
  github_repo = var.github_repo

  tags = local.common_tags
}

# ==============================================================================
# Module: Lambda Function
# ==============================================================================
# Serverless sync function that runs on schedule or via API

module "lambda" {
  source = "../../modules/lambda"

  function_name      = "${local.project_name}-sync-runner-${var.environment}"
  execution_role_arn = module.iam.lambda_execution_role_arn

  # Container-based deployment (solves Pydantic compatibility issues)
  package_type = "Image"
  image_uri    = "${module.ecr.sync_repository_url}:latest"

  # Environment configuration
  environment = var.environment
  aws_region  = data.aws_region.current.name

  # S3 and Secrets configuration
  s3_bucket_name       = module.s3.bucket_id
  smashrun_secret_name = module.secrets.smashrun_oauth_secret_name

  # Performance tuning
  memory_size             = 512   # MB (affects CPU allocation)
  timeout                 = 300   # 5 minutes
  ephemeral_storage_size  = 1024  # 1 GB for DuckDB operations

  # Logging
  log_level           = var.lambda_log_level
  log_retention_days  = 14

  # Monitoring
  enable_xray_tracing = false  # Enable for distributed tracing
  enable_alarms       = true

  # Permissions will be created separately below to avoid circular dependencies
  api_gateway_execution_arn = null
  eventbridge_rule_arn      = null

  # Additional environment variables needed by the sync handler
  # Note: Secrets (Supabase, SmashRun credentials) are fetched from Secrets Manager
  extra_environment_variables = {
    SMASHRUN_REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"  # Out-of-band redirect for CLI
  }

  tags = local.common_tags

  depends_on = [
    module.iam,
    module.s3,
    module.secrets,
    module.ecr
  ]
}

# ==============================================================================
# Module: Query Lambda Function
# ==============================================================================
# Fast read-only Lambda for querying run statistics

module "lambda_query" {
  source = "../../modules/lambda"

  function_name      = "${local.project_name}-query-runner-${var.environment}"
  execution_role_arn = module.iam.lambda_execution_role_arn

  # Container-based deployment (solves Pydantic compatibility issues)
  package_type = "Image"
  image_uri    = "${module.ecr.query_repository_url}:latest"

  # Environment configuration
  environment = var.environment
  aws_region  = data.aws_region.current.name

  # S3 configuration (read-only access)
  s3_bucket_name       = module.s3.bucket_id
  smashrun_secret_name = null  # Query Lambda doesn't need SmashRun credentials

  # Performance tuning for fast queries
  memory_size            = 256  # MB (queries are fast)
  timeout                = 30   # 30 seconds (API Gateway limit)
  ephemeral_storage_size = 512  # 512 MB for DuckDB read operations

  # Logging
  log_level          = var.lambda_log_level
  log_retention_days = 7

  # Monitoring
  enable_xray_tracing = false
  enable_alarms       = false

  # Permissions will be created separately below
  api_gateway_execution_arn = null
  eventbridge_rule_arn      = null

  # Environment variables for query handler
  # Note: Supabase credentials are fetched from Secrets Manager
  extra_environment_variables = {
    PUBLISH_STATUS_FUNCTION_NAME = "${local.project_name}-publish-status-${var.environment}"
  }

  tags = local.common_tags

  depends_on = [
    module.iam,
    module.s3,
    module.ecr
  ]
}

# ==============================================================================
# Module: Publish Status Lambda Function
# ==============================================================================
# Lambda that publishes run status to GCS for qualityplaybook.com

module "lambda_publish_status" {
  source = "../../modules/lambda"

  function_name      = "${local.project_name}-publish-status-${var.environment}"
  execution_role_arn = module.iam.lambda_execution_role_arn

  # Container-based deployment
  package_type = "Image"
  image_uri    = "${module.ecr.publish_status_repository_url}:latest"

  # Environment configuration
  environment = var.environment
  aws_region  = data.aws_region.current.name

  # S3 configuration (not needed for this Lambda)
  s3_bucket_name       = module.s3.bucket_id
  smashrun_secret_name = null

  # Performance tuning
  memory_size            = 256  # MB
  timeout                = 60   # 1 minute
  ephemeral_storage_size = 512  # MB

  # Logging
  log_level          = var.lambda_log_level
  log_retention_days = 7

  # Monitoring
  enable_xray_tracing = false
  enable_alarms       = false

  # Permissions
  api_gateway_execution_arn = null
  eventbridge_rule_arn      = null

  # Environment variables
  extra_environment_variables = {
    GCS_BUCKET_NAME = "myrunstreak-public"
  }

  tags = local.common_tags

  depends_on = [
    module.iam,
    module.ecr
  ]
}

# ==============================================================================
# Module: API Gateway Consumer
# ==============================================================================
# Creates routes on the shared API Gateway (managed by runstreak-common).
# Reads API Gateway configuration from SSM Parameter Store.

module "api_gateway_consumer" {
  source = "../../modules/api_gateway_consumer"

  environment = var.environment
  aws_region  = var.aws_region

  # Sync Lambda (for /sync endpoint)
  sync_lambda_invoke_arn    = module.lambda.function_invoke_arn
  sync_lambda_function_name = module.lambda.function_name

  # Query Lambda (for /stats, /runs, /auth endpoints)
  query_lambda_invoke_arn    = module.lambda_query.function_invoke_arn
  query_lambda_function_name = module.lambda_query.function_name

  depends_on = [module.lambda, module.lambda_query]
}

# ==============================================================================
# Module: EventBridge (CloudWatch Events)
# ==============================================================================
# Schedule Lambda to run twice daily at 9am and 12pm ET

module "eventbridge" {
  source = "../../modules/eventbridge"

  project_name        = local.project_name
  environment         = var.environment
  lambda_function_arn = module.lambda.function_arn

  # Schedules: 9am and 12pm ET (14:00 and 17:00 UTC during EST)
  # Note: During EDT (Mar-Nov), these will be 10am and 1pm local time
  schedules = [
    {
      name        = "morning"
      expression  = "cron(0 14 * * ? *)"
      description = "9am EST / 10am EDT (14:00 UTC)"
    },
    {
      name        = "midday"
      expression  = "cron(0 17 * * ? *)"
      description = "12pm EST / 1pm EDT (17:00 UTC)"
    }
  ]

  # Enable/disable schedule
  enabled = var.eventbridge_enabled

  # Custom input to pass to Lambda
  custom_input = {
    source = "eventbridge"
    action = "daily_sync"
  }

  # Retry configuration
  maximum_event_age_seconds = 3600  # 1 hour
  maximum_retry_attempts    = 2

  # Monitoring
  enable_alarms = true

  tags = local.common_tags

  depends_on = [module.lambda]
}
# ==============================================================================
# Lambda Permissions
# ==============================================================================
# EventBridge permissions for scheduled Lambda invocations
# Note: API Gateway permissions are managed by the api_gateway_consumer module

resource "aws_lambda_permission" "eventbridge_invoke" {
  for_each = module.eventbridge.rule_arns

  statement_id  = "AllowEventBridgeInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.function_name
  principal     = "events.amazonaws.com"

  # Source ARN restricts which EventBridge rule can invoke
  source_arn = each.value
}

# ==============================================================================
# IAM Policy for Lambda-to-Lambda Invocation
# ==============================================================================
# Allow query Lambda to invoke publish_status Lambda after sync

resource "aws_iam_role_policy" "lambda_invoke_publish_status" {
  name = "${local.project_name}-invoke-publish-status-${var.environment}"
  role = module.iam.lambda_execution_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        Resource = module.lambda_publish_status.function_arn
      }
    ]
  })
}

# Note: All API Gateway routes (/sync, /stats, /runs, /auth) are now managed
# by the api_gateway_consumer module above.
