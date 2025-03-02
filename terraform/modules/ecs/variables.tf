variable "environment" {
  description = "Environment (prod/staging)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "database_host" {
  description = "RDS endpoint"
  type        = string
}

# Comment out or remove the Redis endpoint variable
# variable "redis_endpoint" {
#   description = "Redis endpoint"
#   type        = string
# }

variable "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository"
  type        = string
}

variable "secrets_arn" {
  description = "ARN of the Secrets Manager secret"
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the ALB"
  type        = string
}

variable "target_group_arn" {
  description = "ARN of the target group"
  type        = string
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "s3_bucket_name" {
  type = string
}

variable "cloudfront_domain" {
  type = string
}

variable "domain_name" {
  description = "Base domain name for the application"
  type        = string
}

variable "ecs_exec_role_arn" {
  description = "ARN of the ECS exec role"
  type        = string
} 