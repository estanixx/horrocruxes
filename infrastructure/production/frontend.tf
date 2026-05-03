# ============================================
# Horrocruxes Production Frontend - Amplify
# ============================================

# ============================================
# Amplify App with React (builds from GitHub)
# ============================================
resource "aws_amplify_app" "frontend" {
  name = "horrocruxes-${var.environment}"
  
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
  
  # Note: Production branch will be created automatically when GitHub is connected
  # OR use aws_amplify_branch resource to create manually
  
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