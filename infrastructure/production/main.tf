# ============================================
# Horrocruxes Production Infrastructure
# Main entry point - includes backend (ECS) and frontend (Amplify)
# ============================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Include backend and frontend modules
module "backend" {
  source = "./backend"
  
  aws_region         = var.aws_region
  environment       = var.environment
  alb_certificate_arn = var.alb_certificate_arn
}

module "frontend" {
  source = "./frontend"
  
  aws_region   = var.aws_region
  environment  = var.environment
}

# Note: In production, split into separate modules
# This file is for reference - actual implementation uses backend.tf and frontend.tf directly