# ==============================================================================
# S3 Module - DuckDB Database Storage
# ==============================================================================
# This module creates an S3 bucket to store the DuckDB database file.
#
# Key Features:
# - Versioning enabled (keep last 30 versions for rollback)
# - Server-side encryption (AES-256)
# - Public access blocked (Lambda only)
# - Lifecycle policy to manage old versions
# - CORS configuration for potential web access
#
# Learning Points:
# - S3 bucket naming (must be globally unique)
# - Versioning for data protection
# - Encryption at rest
# - Lifecycle rules for cost optimization
# ==============================================================================

# ------------------------------------------------------------------------------
# S3 Bucket - Main Database Storage
# ------------------------------------------------------------------------------
# This bucket stores the runs.duckdb file that Lambda reads/writes
# Naming: myrunstreak-data-{environment}-{account_id}
# Example: myrunstreak-data-dev-123456789012

resource "aws_s3_bucket" "database" {
  bucket = "${var.project_name}-data-${var.environment}-${var.account_id}"

  # Prevent accidental deletion of the bucket
  # Set to false in production after testing
  force_destroy = var.environment == "dev" ? true : false

  tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-database"
      Description = "DuckDB database storage for running activities"
    }
  )
}

# ------------------------------------------------------------------------------
# Versioning Configuration
# ------------------------------------------------------------------------------
# Keep multiple versions of the database file for:
# - Rollback capability if sync corrupts data
# - Audit trail of changes
# - Point-in-time recovery

resource "aws_s3_bucket_versioning" "database" {
  bucket = aws_s3_bucket.database.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ------------------------------------------------------------------------------
# Server-Side Encryption
# ------------------------------------------------------------------------------
# Encrypt all objects at rest using AES-256
# This is free and automatic - no KMS key needed

resource "aws_s3_bucket_server_side_encryption_configuration" "database" {
  bucket = aws_s3_bucket.database.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# ------------------------------------------------------------------------------
# Block Public Access
# ------------------------------------------------------------------------------
# Ensure the bucket is completely private
# Only Lambda function can access via IAM role

resource "aws_s3_bucket_public_access_block" "database" {
  bucket = aws_s3_bucket.database.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ------------------------------------------------------------------------------
# Lifecycle Policy
# ------------------------------------------------------------------------------
# Delete old versions after 30 days to save costs
# Current version is never deleted by this rule

resource "aws_s3_bucket_lifecycle_configuration" "database" {
  bucket = aws_s3_bucket.database.id

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    filter {} # Apply to all objects

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    noncurrent_version_transition {
      noncurrent_days = 7
      storage_class   = "GLACIER_IR" # Cheaper storage for old versions
    }
  }

  rule {
    id     = "cleanup-incomplete-uploads"
    status = "Enabled"

    filter {} # Apply to all objects

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ------------------------------------------------------------------------------
# CORS Configuration (Optional)
# ------------------------------------------------------------------------------
# Allow web browsers to access the bucket if we build a web UI later
# Currently not needed but good to have for future expansion

resource "aws_s3_bucket_cors_configuration" "database" {
  count  = var.enable_cors ? 1 : 0
  bucket = aws_s3_bucket.database.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = var.cors_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# ------------------------------------------------------------------------------
# Bucket Policy - Lambda Access Only
# ------------------------------------------------------------------------------
# Restrict access to only the Lambda execution role
# No other AWS principals can access this bucket

resource "aws_s3_bucket_policy" "database" {
  bucket = aws_s3_bucket.database.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAccess"
        Effect = "Allow"
        Principal = {
          AWS = var.lambda_execution_role_arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.database.arn,
          "${aws_s3_bucket.database.arn}/*"
        ]
      },
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.database.arn,
          "${aws_s3_bucket.database.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Metric Alarm - Bucket Size
# ------------------------------------------------------------------------------
# Alert if bucket grows unexpectedly large (possible issue with Lambda)

resource "aws_cloudwatch_metric_alarm" "bucket_size" {
  count = var.enable_monitoring ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-bucket-size"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BucketSizeBytes"
  namespace           = "AWS/S3"
  period              = "86400" # Daily check
  statistic           = "Average"
  threshold           = var.max_bucket_size_bytes
  alarm_description   = "S3 bucket size exceeds threshold - possible issue"
  treat_missing_data  = "notBreaching"

  dimensions = {
    BucketName  = aws_s3_bucket.database.id
    StorageType = "StandardStorage"
  }

  alarm_actions = var.alarm_sns_topic_arn != null ? [var.alarm_sns_topic_arn] : []
}
