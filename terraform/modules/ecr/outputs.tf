# ==============================================================================
# ECR Module Outputs
# ==============================================================================

output "sync_repository_url" {
  description = "URL of the sync Lambda ECR repository"
  value       = aws_ecr_repository.sync.repository_url
}

output "sync_repository_arn" {
  description = "ARN of the sync Lambda ECR repository"
  value       = aws_ecr_repository.sync.arn
}

output "sync_repository_name" {
  description = "Name of the sync Lambda ECR repository"
  value       = aws_ecr_repository.sync.name
}

output "query_repository_url" {
  description = "URL of the query Lambda ECR repository"
  value       = aws_ecr_repository.query.repository_url
}

output "query_repository_arn" {
  description = "ARN of the query Lambda ECR repository"
  value       = aws_ecr_repository.query.arn
}

output "query_repository_name" {
  description = "Name of the query Lambda ECR repository"
  value       = aws_ecr_repository.query.name
}

output "publish_status_repository_url" {
  description = "URL of the publish status Lambda ECR repository"
  value       = aws_ecr_repository.publish_status.repository_url
}

output "publish_status_repository_arn" {
  description = "ARN of the publish status Lambda ECR repository"
  value       = aws_ecr_repository.publish_status.arn
}

output "publish_status_repository_name" {
  description = "Name of the publish status Lambda ECR repository"
  value       = aws_ecr_repository.publish_status.name
}

output "authorizer_repository_url" {
  description = "URL of the JWT authorizer Lambda ECR repository"
  value       = aws_ecr_repository.authorizer.repository_url
}

output "authorizer_repository_name" {
  description = "Name of the JWT authorizer Lambda ECR repository"
  value       = aws_ecr_repository.authorizer.name
}

output "registry_id" {
  description = "The registry ID where the repositories are created"
  value       = aws_ecr_repository.sync.registry_id
}
