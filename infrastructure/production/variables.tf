# ============================================
# Variables for Production Infrastructure
# ============================================

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (production, staging, etc.)"
  type        = string
  default     = "production"
}

variable "alb_certificate_arn" {
  description = "ACM certificate ARN for ALB HTTPS listener"
  type        = string
  default     = ""  # Must be provided - e.g., arn:aws:acm:us-east-1:123456789012:certificate/abc123
}

variable "domain_name" {
  description = "Optional custom domain for the backend"
  type        = string
  default     = ""
}

variable "frontend_repository" {
  description = "GitHub repository for frontend"
  type        = string
  default     = "https://github.com/estanixx/horrocruxes"
}

variable "frontend_oauth_token" {
  description = "GitHub OAuth token for Amplify (set via environment or secret)"
  type        = string
  default     = ""
  sensitive   = true
}