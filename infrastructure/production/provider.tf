# ============================================
# AWS Provider Configuration
# ============================================

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "horrocruxes"
      Environment = var.environment
    }
  }
}

# Optional: Configure AWS SSO if using AWS SSO
# provider "aws" {
#   region = "us-east-1"
#   alias  = "sso"
#   
#   use_sso = true
#   sso_session = "my-sso"
#   sso_account_id = "123456789012"
#   sso_role_name  = "Administrator"
# }

# Alias for alternate region if needed
# provider "aws" {
#   region = "us-west-2"
#   alias  = "alternate"
# }