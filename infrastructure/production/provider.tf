# ============================================
# AWS Provider Configuration
# ============================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket       = "central-tfstate-estanix-871696174477"
    key          = "horrocruxes/production/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true  # S3 conditional writes - no DynamoDB needed
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "horrocruxes"
      Environment = var.environment
    }
  }
}