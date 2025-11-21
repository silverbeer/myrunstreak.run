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
  extra_environment_variables = {}

  tags = local.common_tags

  depends_on = [
    module.iam,
    module.s3,
    module.ecr
  ]
}

# ==============================================================================
# Module: API Gateway
# ==============================================================================
# REST API with authentication for manual sync triggers

module "api_gateway" {
  source = "../../modules/api_gateway"

  project_name         = local.project_name
  environment          = var.environment
  lambda_invoke_arn    = module.lambda.function_invoke_arn
  lambda_function_name = module.lambda.function_name

  # Rate limiting
  burst_limit = 10   # Max concurrent requests
  rate_limit  = 5    # Requests per second

  # Quota
  quota_limit  = 1000  # Total requests per period
  quota_period = "DAY"

  # Logging
  log_retention_days = 14
  logging_level      = "INFO"  # OFF, ERROR, or INFO

  # Monitoring
  enable_xray_tracing = false
  enable_alarms       = true

  tags = local.common_tags

  depends_on = [module.lambda]
}

# ==============================================================================
# Module: EventBridge (CloudWatch Events)
# ==============================================================================
# Schedule Lambda to run daily at 6am EST / 7am EDT

module "eventbridge" {
  source = "../../modules/eventbridge"

  project_name        = local.project_name
  environment         = var.environment
  lambda_function_arn = module.lambda.function_arn

  # Schedule: Daily at 11:00 UTC (6am EST / 7am EDT)
  schedule_expression = "cron(0 11 * * ? *)"
  schedule_description = "6am EST / 7am EDT (11:00 UTC)"

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
# Created separately from Lambda module to avoid circular dependencies
# These permissions allow API Gateway and EventBridge to invoke the Lambda function

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.function_name
  principal     = "apigateway.amazonaws.com"

  # Source ARN restricts which API Gateway can invoke
  # Format: arn:aws:execute-api:region:account:api-id/stage/method/path
  source_arn = "${module.api_gateway.api_execution_arn}/*/*"
  # /*/* means any stage, any method/path
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.function_name
  principal     = "events.amazonaws.com"

  # Source ARN restricts which EventBridge rule can invoke
  source_arn = module.eventbridge.rule_arn
}

# Query Lambda permissions
resource "aws_lambda_permission" "query_api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvokeQuery"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_query.function_name
  principal     = "apigateway.amazonaws.com"

  # Allow invocation from any path in this API Gateway
  source_arn = "${module.api_gateway.api_execution_arn}/*/*"
}

# ==============================================================================
# API Gateway Resources for Query Endpoints
# ==============================================================================
# Create resources and integrations for /stats/* and /runs/* endpoints

# /stats resource
resource "aws_api_gateway_resource" "stats" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = module.api_gateway.root_resource_id
  path_part   = "stats"
}

# /stats/{proxy+} - catches all /stats/* paths
resource "aws_api_gateway_resource" "stats_proxy" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.stats.id
  path_part   = "{proxy+}"
}

# GET method for /stats/{proxy+}
resource "aws_api_gateway_method" "stats_proxy_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.stats_proxy.id
  http_method   = "GET"
  authorization = "NONE"  # Public read access
}

# Integration with query Lambda for /stats/{proxy+}
resource "aws_api_gateway_integration" "stats_proxy" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.stats_proxy.id
  http_method = aws_api_gateway_method.stats_proxy_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_query.function_invoke_arn
}

# /runs resource
resource "aws_api_gateway_resource" "runs" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = module.api_gateway.root_resource_id
  path_part   = "runs"
}

# GET method for /runs (list all runs)
resource "aws_api_gateway_method" "runs_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.runs.id
  http_method   = "GET"
  authorization = "NONE"  # Public read access
}

# Integration with query Lambda for /runs
resource "aws_api_gateway_integration" "runs_get" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.runs.id
  http_method = aws_api_gateway_method.runs_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_query.function_invoke_arn
}

# /runs/{proxy+} - catches all /runs/* paths
resource "aws_api_gateway_resource" "runs_proxy" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.runs.id
  path_part   = "{proxy+}"
}

# GET method for /runs/{proxy+}
resource "aws_api_gateway_method" "runs_proxy_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.runs_proxy.id
  http_method   = "GET"
  authorization = "NONE"  # Public read access
}

# Integration with query Lambda for /runs/{proxy+}
resource "aws_api_gateway_integration" "runs_proxy" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.runs_proxy.id
  http_method = aws_api_gateway_method.runs_proxy_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_query.function_invoke_arn
}

# /sync resource for user-initiated sync via query Lambda
resource "aws_api_gateway_resource" "sync_user" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = module.api_gateway.root_resource_id
  path_part   = "sync-user"  # Different from /sync which goes to sync Lambda
}

# POST method for /sync-user
resource "aws_api_gateway_method" "sync_user_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.sync_user.id
  http_method   = "POST"
  authorization = "NONE"  # Will use user_id for now
}

# Integration with query Lambda for /sync-user
resource "aws_api_gateway_integration" "sync_user" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.sync_user.id
  http_method = aws_api_gateway_method.sync_user_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_query.function_invoke_arn
}

# /auth resource for authentication endpoints
resource "aws_api_gateway_resource" "auth" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = module.api_gateway.root_resource_id
  path_part   = "auth"
}

# /auth/store-tokens resource
resource "aws_api_gateway_resource" "auth_store_tokens" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "store-tokens"
}

# POST method for /auth/store-tokens
resource "aws_api_gateway_method" "auth_store_tokens_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_store_tokens.id
  http_method   = "POST"
  authorization = "NONE"  # Will use user_id for now
}

# Integration with query Lambda for /auth/store-tokens
resource "aws_api_gateway_integration" "auth_store_tokens" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_store_tokens.id
  http_method = aws_api_gateway_method.auth_store_tokens_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_query.function_invoke_arn
}

# /auth/login-url resource
resource "aws_api_gateway_resource" "auth_login_url" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login-url"
}

# GET method for /auth/login-url
resource "aws_api_gateway_method" "auth_login_url_get" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_login_url.id
  http_method   = "GET"
  authorization = "NONE"
}

# Integration with query Lambda for /auth/login-url
resource "aws_api_gateway_integration" "auth_login_url" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_login_url.id
  http_method = aws_api_gateway_method.auth_login_url_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_query.function_invoke_arn
}

# /auth/callback resource
resource "aws_api_gateway_resource" "auth_callback" {
  rest_api_id = module.api_gateway.rest_api_id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "callback"
}

# POST method for /auth/callback
resource "aws_api_gateway_method" "auth_callback_post" {
  rest_api_id   = module.api_gateway.rest_api_id
  resource_id   = aws_api_gateway_resource.auth_callback.id
  http_method   = "POST"
  authorization = "NONE"
}

# Integration with query Lambda for /auth/callback
resource "aws_api_gateway_integration" "auth_callback" {
  rest_api_id = module.api_gateway.rest_api_id
  resource_id = aws_api_gateway_resource.auth_callback.id
  http_method = aws_api_gateway_method.auth_callback_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda_query.function_invoke_arn
}

# ==============================================================================
# API Gateway Deployment for Query Endpoints
# ==============================================================================
# Create a new deployment that includes the query endpoints
# This triggers a redeployment whenever query resources change

resource "aws_api_gateway_deployment" "query_endpoints" {
  rest_api_id = module.api_gateway.rest_api_id

  # Trigger redeployment when query resources change
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.stats.id,
      aws_api_gateway_resource.stats_proxy.id,
      aws_api_gateway_method.stats_proxy_get.id,
      aws_api_gateway_integration.stats_proxy.id,
      aws_api_gateway_resource.runs.id,
      aws_api_gateway_method.runs_get.id,
      aws_api_gateway_integration.runs_get.id,
      aws_api_gateway_resource.runs_proxy.id,
      aws_api_gateway_method.runs_proxy_get.id,
      aws_api_gateway_integration.runs_proxy.id,
      aws_api_gateway_resource.sync_user.id,
      aws_api_gateway_method.sync_user_post.id,
      aws_api_gateway_integration.sync_user.id,
      aws_api_gateway_resource.auth.id,
      aws_api_gateway_resource.auth_store_tokens.id,
      aws_api_gateway_method.auth_store_tokens_post.id,
      aws_api_gateway_integration.auth_store_tokens.id,
      aws_api_gateway_resource.auth_login_url.id,
      aws_api_gateway_method.auth_login_url_get.id,
      aws_api_gateway_integration.auth_login_url.id,
      aws_api_gateway_resource.auth_callback.id,
      aws_api_gateway_method.auth_callback_post.id,
      aws_api_gateway_integration.auth_callback.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.stats_proxy,
    aws_api_gateway_integration.runs_get,
    aws_api_gateway_integration.runs_proxy,
    aws_api_gateway_integration.sync_user,
    aws_api_gateway_integration.auth_store_tokens,
    aws_api_gateway_integration.auth_login_url,
    aws_api_gateway_integration.auth_callback,
  ]
}

# Update the existing stage to use the new deployment with query endpoints
# This uses a null_resource to run AWS CLI command that updates the stage
resource "null_resource" "update_stage_deployment" {
  triggers = {
    deployment_id = aws_api_gateway_deployment.query_endpoints.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws apigateway update-stage \
        --rest-api-id ${module.api_gateway.rest_api_id} \
        --stage-name ${var.environment} \
        --patch-operations op=replace,path=/deploymentId,value=${aws_api_gateway_deployment.query_endpoints.id} \
        --region ${var.aws_region}
    EOT
  }

  depends_on = [
    module.api_gateway,
    aws_api_gateway_deployment.query_endpoints,
  ]
}
