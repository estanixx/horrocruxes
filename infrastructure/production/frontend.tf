# ============================================
# Horrocruxes Production Frontend - Amplify
# ============================================

# Data source for GitHub access token from SSM
data "aws_ssm_parameter" "github_token" {
  name = "/horrocruxes/${var.environment}/github-access-token"
}

# ============================================
# Amplify App with React (builds from GitHub via Amplify GitHub App)
# ============================================
resource "aws_amplify_app" "frontend" {
  name       = "horrocruxes-${var.environment}"
  repository = var.frontend_repository
  
  # Token needed for initial creation - Amplify GitHub App handles deployments
  access_token = data.aws_ssm_parameter.github_token.value
  
  # Monorepo diff deployment - ignores backend changes
  environment_variables = {
    AMPLIFY_DIFF_DEPLOY = "true"
    VITE_API_URL        = data.aws_ssm_parameter.vite_api_url.value
  }
  
# Build spec for frontend
  build_spec = <<-EOT
version: 1
applications:
  - appRoot: frontend
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: dist
        files:
          - '**/*'
      cache:
        paths:
          - frontend/node_modules/**/*
EOT

  # Custom rewrite rules for SPA
  custom_rule {
    source = "/<*>"
    status = "200"
    target = "/index.html"
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
  
  enable_auto_build = false
  
  framework = "React"
  
  # Environment variables as map
  environment_variables = {
    AMPLIFY_DIFF_DEPLOY = "true"
    VITE_API_URL        = data.aws_ssm_parameter.vite_api_url.value
  }
}