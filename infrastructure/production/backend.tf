# ============================================
# Horrocruxes Production Backend - ECS Fargate + ALB
# ============================================


# ============================================
# Data: SSM Parameters for Secrets
# ============================================
data "aws_ssm_parameter" "google_api_key" {
  name = "/horrocruxes/production/GOOGLE_API_KEY"
}

data "aws_ssm_parameter" "pinecone_api_key" {
  name = "/horrocruxes/production/PINECONE_API_KEY"
}

data "aws_ssm_parameter" "vite_api_url" {
  name = "/horrocruxes/production/VITE_API_URL"
}

# ============================================
# VPC and Networking
# ============================================
# Use default VPC if no custom VPC provided
data "aws_vpc" "default" {
  default = true
}

# Get all subnets in default VPC
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ============================================
# ECR Repository for Backend - use existing from CloudFormation
# ============================================
data "aws_ecr_repository" "backend" {
  name = "horrocruxes-backend"
}

# ============================================
# CloudWatch Log Group
# ============================================
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/horrocruxes/backend/${var.environment}"
  retention_in_days = 7
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

# ============================================
# ECS Cluster
# ============================================
resource "aws_ecs_cluster" "backend" {
  name = "horrocruxes-backend-${var.environment}"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

# ============================================
# ECS Task Definition
# ============================================
resource "aws_ecs_task_definition" "backend" {
  family                   = "horrocruxes-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  
  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${data.aws_ecr_repository.backend.repository_url}:latest"
      essential = true
      
      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]
      
      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]
      
      # Read secrets from SSM
      secrets = [
        {
          name      = "GOOGLE_API_KEY"
          valueFrom = data.aws_ssm_parameter.google_api_key.arn
        },
        {
          name      = "PINECONE_API_KEY"
          valueFrom = data.aws_ssm_parameter.pinecone_api_key.arn
        },
        {
          name      = "VITE_API_URL"
          valueFrom = data.aws_ssm_parameter.vite_api_url.arn
        }
      ]
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

# ============================================
# IAM Roles for ECS
# ============================================
resource "aws_iam_role" "ecs_task_execution" {
  name = "horrocruxes-ecs-task-execution-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# Attach managed policy using resource (not deprecated)
resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# SSM access for execution role (to pull secrets at startup)
resource "aws_iam_role_policy" "ecs_execution_ssm" {
  name = "ExecutionRoleSSM-${var.environment}"
  role = aws_iam_role.ecs_task_execution.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameters",
          "ssm:GetParameter"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/horrocruxes/production/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "ecs_task_role" {
  name = "horrocruxes-ecs-task-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

# Custom policy for accessing SSM parameters (replaces deprecated inline_policy)
resource "aws_iam_role_policy" "ecs_task_ssm" {
  name = "SSMReadPolicy-${var.environment}"
  role = aws_iam_role.ecs_task_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameters",
          "ssm:GetParameter"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/horrocruxes/production/*"
        ]
      }
    ]
  })
}

data "aws_caller_identity" "current" {}

# ============================================
# Security Group for ECS Tasks
# ============================================
resource "aws_security_group" "ecs_tasks" {
  name        = "horrocruxes-ecs-tasks-${var.environment}"
  description = "Security group for ECS tasks"
  vpc_id      = data.aws_vpc.default.id
  
  # Allow traffic from ALB on container port
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  
  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

# ============================================
# Application Load Balancer
# ============================================
resource "aws_lb" "backend" {
  name               = "horrocruxes-backend-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids
  idle_timeout = 300
  enable_deletion_protection = false
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

resource "aws_security_group" "alb" {
  name        = "horrocruxes-alb-${var.environment}"
  description = "Security group for ALB"
  vpc_id      = data.aws_vpc.default.id
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "backend" {
  name     = "horrocruxes-backend-${var.environment}"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id
  
  lifecycle {
    create_before_destroy = true
  }
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }
  
  target_type = "ip"
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

# HTTP listener (required - no certificate needed for HTTP)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.backend.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# HTTPS listener (only if certificate provided)
resource "aws_lb_listener" "https" {
  count = var.alb_certificate_arn != "" ? 1 : 0
  
  load_balancer_arn = aws_lb.backend.arn
  port              = "443"
  protocol          = "HTTPS"
  
  ssl_policy      = "ELBSecurityPolicy-2016-08"
  certificate_arn = var.alb_certificate_arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# Redirect HTTP to HTTPS (only if certificate exists)
resource "aws_lb_listener" "http_redirect" {
  count = var.alb_certificate_arn != "" ? 1 : 0
  
  load_balancer_arn = aws_lb.backend.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# ============================================
# ECS Service
# ============================================
resource "aws_ecs_service" "backend" {
  name            = "horrocruxes-backend-${var.environment}"
  cluster         = aws_ecs_cluster.backend.arn
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = 2
  launch_type     = "FARGATE"
  
  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true  # Use public subnets
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8080
  }
  
  depends_on = [aws_lb_listener.http]
  
  # Auto-scaling
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  
  tags = {
    Project     = "horrocruxes"
    Environment = var.environment
  }
}

# ============================================
# Auto Scaling - Basic target without policy
# ============================================
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 4
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.backend.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Basic auto-scaling role
resource "aws_iam_role" "ecs_autoscaling" {
  name = "horrocruxes-ecs-autoscaling-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "application-autoscaling.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_autoscale_policy" {
  role       = aws_iam_role.ecs_autoscaling.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceAutoscaleRole"
}