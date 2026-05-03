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
  
  backend "s3" {
    bucket = "central-tfstate-estanix-871696174477"
    key    = "horrocruxes/production/terraform.tfstate"
    region = "us-east-1"
  }
}

# All resources are defined in backend.tf and frontend.tf
# No modules needed - files are included directly