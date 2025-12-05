# ==============================================================================
# IAM Module - Roles and Policies for Lambda
# ==============================================================================
# This module creates the IAM execution role for Lambda with permissions to:
# - Read/write S3 (DuckDB database)
# - Read Secrets Manager (SmashRun OAuth tokens)
# - Write CloudWatch Logs (monitoring)
#
# Key Concepts:
# - Trust Policy: Who can assume this role (Lambda service)
# - Permission Policy: What the role can do (S3, Secrets, Logs)
# - Principle of Least Privilege: Only grant minimum required permissions
#
# Learning Points:
# - IAM roles vs users
# - Trust relationships (assume role policy)
# - Inline vs managed policies
# - ARN wildcards and specificity
# ==============================================================================

# ------------------------------------------------------------------------------
# Lambda Execution Role
# ------------------------------------------------------------------------------
# This role is assumed by Lambda when it runs
# Think of it as the Lambda's "identity" in AWS

resource "aws_iam_role" "lambda_execution" {
  name        = "${var.project_name}-lambda-execution-${var.environment}"
  description = "Execution role for MyRunStreak sync Lambda function"

  # Trust Policy - Defines WHO can assume this role
  # Only the Lambda service can use this role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAssumeRole"
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        # Optional: Add condition to restrict to specific Lambda functions
        # Condition = {
        #   StringEquals = {
        #     "aws:SourceAccount" = var.account_id
        #   }
        # }
      }
    ]
  })

  # Prevent accidental deletion
  # Comment this out in production after initial setup
  force_detach_policies = var.environment == "dev" ? true : false

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-lambda-execution"
    }
  )
}

# ------------------------------------------------------------------------------
# CloudWatch Logs Policy
# ------------------------------------------------------------------------------
# Lambda needs to create log groups and write logs
# This is a managed AWS policy that grants standard logging permissions

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# What does AWSLambdaBasicExecutionRole include?
# - logs:CreateLogGroup
# - logs:CreateLogStream
# - logs:PutLogEvents
#
# This is a "managed policy" maintained by AWS
# Alternative: Create custom policy with exactly these permissions

# ------------------------------------------------------------------------------
# S3 Access Policy
# ------------------------------------------------------------------------------
# Grant Lambda permission to read/write the DuckDB database in S3
# Using inline policy for fine-grained control

resource "aws_iam_role_policy" "s3_access" {
  name = "s3-database-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListDatabaseBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning"
        ]
        Resource = var.s3_bucket_arn
      },
      {
        Sid    = "ReadWriteDatabaseObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:DeleteObject" # For cleanup if needed
        ]
        Resource = "${var.s3_bucket_arn}/*"
        # Note: "/*" means all objects in the bucket
        # Without it, you can only access the bucket metadata, not objects
      }
    ]
  })
}

# Why separate statements for bucket vs objects?
# - s3:ListBucket operates on the bucket (arn:aws:s3:::bucket-name)
# - s3:GetObject operates on objects (arn:aws:s3:::bucket-name/*)
# - Using the wrong Resource format causes permission errors

# ------------------------------------------------------------------------------
# Secrets Manager Access Policy
# ------------------------------------------------------------------------------
# Grant Lambda permission to read SmashRun OAuth credentials
# Scoped to only secrets with specific prefix

resource "aws_iam_role_policy" "secrets_access" {
  name = "secrets-manager-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ManageSmashRunSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
          "secretsmanager:CreateSecret",
          "secretsmanager:UpdateSecret",
          "secretsmanager:PutSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.project_name}/*"
        ]
        # This grants access to any secret starting with "myrunstreak/"
        # Lambda needs write permissions to:
        # - Refresh OAuth tokens (UpdateSecret)
        # - Create sync state secret (CreateSecret)
        # Example: myrunstreak/dev/smashrun/oauth, myrunstreak/dev/sync-state
      }
    ]
  })
}

# Why not GetSecretValue on all secrets?
# - Principle of Least Privilege
# - If Lambda is compromised, attacker can't read unrelated secrets
# - Limits blast radius of security incidents

# ------------------------------------------------------------------------------
# VPC Access Policy (Optional)
# ------------------------------------------------------------------------------
# If Lambda needs to access resources in a VPC (databases, etc.)
# We don't need this for MyRunStreak since we only access public APIs

# Uncomment if you add VPC access later:
# resource "aws_iam_role_policy_attachment" "lambda_vpc" {
#   count      = var.enable_vpc_access ? 1 : 0
#   role       = aws_iam_role.lambda_execution.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
# }

# What does AWSLambdaVPCAccessExecutionRole include?
# - ec2:CreateNetworkInterface
# - ec2:DescribeNetworkInterfaces
# - ec2:DeleteNetworkInterface
# - ec2:AssignPrivateIpAddresses
# - ec2:UnassignPrivateIpAddresses

# ------------------------------------------------------------------------------
# Custom CloudWatch Metrics Policy (Optional)
# ------------------------------------------------------------------------------
# If we want to publish custom metrics from Lambda

resource "aws_iam_role_policy" "cloudwatch_metrics" {
  count = var.enable_custom_metrics ? 1 : 0
  name  = "cloudwatch-metrics-access"
  role  = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PutCustomMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = var.project_name
          }
        }
      }
    ]
  })
}

# Why Resource = "*" with a Condition?
# - PutMetricData doesn't support resource-level permissions
# - Condition restricts to our namespace only
# - Without condition, could publish to any namespace

# ------------------------------------------------------------------------------
# ECR Access Policy
# ------------------------------------------------------------------------------
# Lambda needs permission to pull container images from ECR

resource "aws_iam_role_policy" "ecr_access" {
  name = "ecr-pull-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRGetAuthToken"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Sid    = "ECRPullImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability"
        ]
        Resource = "arn:aws:ecr:${var.aws_region}:${var.account_id}:repository/${var.project_name}-*"
      }
    ]
  })
}

# Note: Lambda service also needs repository-based permissions
# which are configured in the ECR module's repository policy

# ------------------------------------------------------------------------------
# API Gateway Invocation Role (Optional)
# ------------------------------------------------------------------------------
# API Gateway needs permission to invoke Lambda
# This is handled by lambda_permission resource in the Lambda module
# But included here for reference

# Not needed as a separate role - API Gateway uses resource-based policies
# on the Lambda function itself (aws_lambda_permission)
