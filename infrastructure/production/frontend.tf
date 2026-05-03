# ============================================
# Horrocruxes Production Frontend - Amplify
# ============================================

# ============================================
# Amplify App with Docker-based build
# ============================================
resource "aws_amplify_app" "frontend" {
  name = "horrocruxes-${var.environment}"
  
  # Custom build spec for Docker-based deployment
  build_spec = <<-EOF
    version: 1
    backend:
      phases:
        build:
          commands:
            - echo "Building frontend container..."
            - docker build -t frontend:latest -f frontend/Dockerfile.prod frontend/
            - docker tag frontend:latest $IMAGE_URI
            - echo "Image built: $IMAGE_URI"
    frontend:
      phases:
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: dist
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
          - .npm
    EOF
  
  # Custom rewrite rules for SPA
  custom_rules {
    source = "/<*>"
    status = "200"
    condition = ""
    target = "/index.html"
  }
  
  # Environment variables from SSM
  environment_variables = [
    {
      name  = "VITE_API_URL"
      value = data.aws_ssm_parameter.vite_api_url.value
    }
  ]
  
  production_branch {
    branch = "prod"
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
  branch      = "prod"
  stage       = "PRODUCTION"
  
  enable_auto_build = true
  
  framework = "React"
  
  # Environment variables
  environment_variables = [
    {
      name  = "VITE_API_URL"
      value = data.aws_ssm_parameter.vite_api_url.value
    }
  ]
}

# ============================================
# Amplify Webhook for GitHub
# ============================================
resource "aws_amplify_webhook" "prod" {
  app_id      = aws_amplify_app.frontend.id
  branch_name = "prod"
  description = "Webhook for prod branch deployment"
}