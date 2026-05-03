variable "aws_region" {
  description = "AWS region for the (now-minimal) AWS footprint — terraform state backend"
  type        = string
  default     = "us-east-2"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"
}
