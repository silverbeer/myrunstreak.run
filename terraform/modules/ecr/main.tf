# ==============================================================================
# ECR Module - Container Registry for Lambda Functions
# ==============================================================================
# This module creates ECR repositories for Lambda container images.
#
# Why ECR?
# - Private container registry integrated with AWS IAM
# - Automatic image scanning for vulnerabilities
# - Lifecycle policies to manage image retention
# - Cross-region replication (if needed)
#
# ECR Pricing:
# - $0.10 per GB-month of storage
# - $0.09 per GB for data transfer out
# - Our estimated cost: <$1/month (small images, minimal pulls)
# ==============================================================================

# ------------------------------------------------------------------------------
# ECR Repository for Sync Lambda
# ------------------------------------------------------------------------------

resource "aws_ecr_repository" "sync" {
  name                 = "${var.project_name}-sync-${var.environment}"
  image_tag_mutability = "MUTABLE" # Allow overwriting :latest tag

  # Enable image scanning on push
  image_scanning_configuration {
    scan_on_push = true
  }

  # Encryption (default AES-256, or use KMS for extra control)
  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-sync-${var.environment}"
    }
  )
}

# ------------------------------------------------------------------------------
# ECR Repository for Query Lambda
# ------------------------------------------------------------------------------

resource "aws_ecr_repository" "query" {
  name                 = "${var.project_name}-query-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-query-${var.environment}"
    }
  )
}

# ------------------------------------------------------------------------------
# Lifecycle Policy - Sync Repository
# ------------------------------------------------------------------------------
# Keep only recent images to control storage costs

resource "aws_ecr_lifecycle_policy" "sync" {
  repository = aws_ecr_repository.sync.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.image_retention_count} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# Lifecycle Policy - Query Repository
# ------------------------------------------------------------------------------

resource "aws_ecr_lifecycle_policy" "query" {
  repository = aws_ecr_repository.query.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.image_retention_count} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# Repository Policy - Allow Lambda to pull images
# ------------------------------------------------------------------------------
# Lambda needs permission to pull images from ECR

resource "aws_ecr_repository_policy" "sync" {
  repository = aws_ecr_repository.sync.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaPull"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })
}

resource "aws_ecr_repository_policy" "query" {
  repository = aws_ecr_repository.query.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaPull"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# ECR Repository for Publish Status Lambda
# ------------------------------------------------------------------------------

resource "aws_ecr_repository" "publish_status" {
  name                 = "${var.project_name}-publish-status-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-publish-status-${var.environment}"
    }
  )
}

# ------------------------------------------------------------------------------
# Lifecycle Policy - Publish Status Repository
# ------------------------------------------------------------------------------

resource "aws_ecr_lifecycle_policy" "publish_status" {
  repository = aws_ecr_repository.publish_status.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.image_retention_count} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecr_repository_policy" "publish_status" {
  repository = aws_ecr_repository.publish_status.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaPull"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })
}
