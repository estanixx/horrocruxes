# ============================================
# Horrocruxes Production Frontend - Amplify
# ============================================

# Data source for GitHub access token from SSM
data "aws_ssm_parameter" "github_token" {
  name = "/horrocruxes/${var.environment}/github-access-token"
}

# ============================================
# Amplify App with React (builds from GitHub)
# ============================================
resource "aws_amplify_app" "frontend" {
  name       = "horrocruxes-${var.environment}"
  repository = var.frontend_repository
  
  # GitHub personal access token (from SSM)
  access_token = data.aws_ssm_parameter.github_token.value
  
  # Custom rewrite rules for SPA
  custom_rule {
    source = "/<*>"
    status = "200"
    target = "/index.html"
  }
  
  # Environment variables as map
  environment_variables = {
    VITE_API_URL = data.aws_ssm_parameter.vite_api_url.value
  }
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

# ============================================
# Amplify Branch (Production)
# ============================================
resource "aws_amplify_branch" "prod" {
  app_id      = aws_amplify_app.frontend.id
  branch_name = "prod"
  stage       = "PRODUCTION"
  
  enable_auto_build = true
  
  framework = "React"
  
  # Environment variables as map
  environment_variables = {
    VITE_API_URL = data.aws_ssm_parameter.vite_api_url.value
  }
}

# Note: Webhooks are created automatically by Amplify when connected to GitHub
# No need to create manually