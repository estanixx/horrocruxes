# ============================================
# Outputs for Production Infrastructure
# ============================================

output "backend_alb_dns_name" {
  description = "DNS name of the backend ALB"
  value       = aws_lb.backend.dns_name
}

output "backend_url" {
  description = "Full URL of the backend"
  value       = "http://${aws_lb.backend.dns_name}:8080"
}

output "backend_ecr_repository_url" {
  description = "ECR repository URL for backend"
  value       = data.aws_ecr_repository.backend.repository_url
}

output "frontend_url" {
  description = "Amplify frontend URL"
  value       = "https://${aws_amplify_app.frontend.default_domain}"
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.backend.name
}

output "backend_ecs_service_name" {
  description = "Backend ECS service name"
  value       = aws_ecs_service.backend.name
}