resource "aws_ecs_cluster" "main" {
  name = "${var.environment}-cluster"
}

resource "aws_ecs_task_definition" "django" {
  family                   = "${var.environment}-django"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                     = "256"
  memory                  = "512"
  execution_role_arn      = var.ecs_exec_role_arn
  task_role_arn           = var.ecs_task_role_arn
  
  # Add task definition retention
  lifecycle {
    create_before_destroy = true
    ignore_changes       = [container_definitions]  # Prevent unnecessary updates
  }

  container_definitions = jsonencode([
    {
      name      = "django"
      image     = "${var.ecr_repository_url}:latest"
      essential = true
      
      environment = [
        { name = "DEBUG", value = "False" },
        { name = "DJANGO_SETTINGS_MODULE", value = "backend.settings.prod" },
        { name = "ALLOWED_HOSTS", value = "api.trazo.io,${var.alb_dns_name}" },
        { name = "AWS_S3_REGION_NAME", value = var.aws_region },
        { name = "DATABASE_PORT", value = "5432" },
        { name = "AWS_STORAGE_BUCKET_NAME", value = var.s3_bucket_name },
        { name = "AWS_S3_CUSTOM_DOMAIN", value = var.cloudfront_domain },
        { name = "STATIC_URL", value = "https://static.${var.domain_name}/" }
      ]

      secrets = [
        { name = "SECRET_KEY", valueFrom = "${var.secrets_arn}:SECRET_KEY::" },
        { name = "DATABASE_NAME", valueFrom = "${var.secrets_arn}:DATABASE_NAME::" },
        { name = "DATABASE_USER", valueFrom = "${var.secrets_arn}:DATABASE_USER::" },
        { name = "DATABASE_PASSWORD", valueFrom = "${var.secrets_arn}:DATABASE_PASSWORD::" },
        { name = "DATABASE_HOST", valueFrom = "${var.secrets_arn}:DATABASE_HOST::" },
        { name = "SENDGRID_API_KEY", valueFrom = "${var.secrets_arn}:SENDGRID_API_KEY::" }
      ]

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = "/ecs/${var.environment}"
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "django"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "django" {
  name                   = "${var.environment}-django"
  cluster               = aws_ecs_cluster.main.id
  task_definition       = aws_ecs_task_definition.django.arn
  desired_count         = 1
  force_new_deployment = true
  
  health_check_grace_period_seconds = 60

  network_configuration {
    security_groups  = [var.ecs_security_group_id]
    subnets         = var.private_subnet_ids
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "django"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_controller {
    type = "ECS"
  }

  enable_execute_command = true

  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}

resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 2
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.django.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_policy_cpu" {
  name               = "${var.environment}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 80.0
  }
}

resource "aws_iam_role_policy" "cloudfront_permissions" {
  name = "${var.environment}-cloudfront-permissions"
  role = split("/", var.ecs_execution_role_arn)[1]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "cloudfront:CreateCloudFrontOriginAccessIdentity",
        "cloudfront:CreateDistribution",
        "cloudfront:CreateResponseHeadersPolicy",
        "cloudfront:UpdateDistribution"
      ]
      Resource = "*"
    }]
  })
}

# resource "aws_elasticache_serverless_cache" "redis" {
#   engine               = "redis"
#   name                 = "${var.environment}-redis-serverless"
#   description          = "Redis serverless cache for Django"
#   security_group_ids   = [var.redis_security_group_id]
#   subnet_group_name    = aws_elasticache_subnet_group.main.name
#   
#   daily_snapshot_time  = "05:00"
#   
#   cache_usage_limits {
#     data_storage {
#       maximum = 1  # 1 GB
#       unit    = "GB"
#     }
#     
#     ecpu_per_second {
#       maximum = 1000  # 1000 eCPU
#     }
#   }
#   
#   tags = {
#     Environment = var.environment
#   }
# } 