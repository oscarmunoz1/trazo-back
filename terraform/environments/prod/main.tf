terraform {
  required_version = ">= 1.0.0"
  
  backend "s3" {
    bucket = "trazo-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-2"
    encrypt = true
  }
}

provider "aws" {
  region = "us-east-2"
}

provider "aws" {
  alias  = "us-east-1"
  region = "us-east-1"
}

# Add this data source to reference your existing Route53 zone
data "aws_route53_zone" "main" {
  name = var.domain_name
}

# Move certificate resource before module declarations
resource "aws_acm_certificate" "main" {
  domain_name       = "api.${var.domain_name}"
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}

# First, create the certificate
resource "aws_acm_certificate" "cloudfront" {
  provider          = aws.us-east-1
  domain_name       = "*.${var.domain_name}"
  validation_method = "DNS"
  
  lifecycle {
    create_before_destroy = true
  }
}

# Create the validation records directly (not through DNS module)
resource "aws_route53_record" "cloudfront_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cloudfront.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

# For the primary certificate, need to add validation records and wait
resource "aws_route53_record" "main_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

# Add validation resource back (with timeout)
resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.main_validation : record.fqdn]
  timeouts {
    create = "30m"
  }
}

# Also add back CloudFront validation with timeout
resource "aws_acm_certificate_validation" "cloudfront" {
  provider                = aws.us-east-1
  certificate_arn         = aws_acm_certificate.cloudfront.arn
  validation_record_fqdns = [for record in aws_route53_record.cloudfront_validation : record.fqdn]
  timeouts {
    create = "30m"
  }
}

module "networking" {
  source = "../../modules/networking"
  
  environment = "prod"
  vpc_cidr    = "10.0.0.0/16"
  aws_region  = "us-east-2"
  
  public_subnets  = ["10.0.1.0/24"]
  private_subnets = ["10.0.3.0/24"]
  availability_zones = ["us-east-2a"]
}

module "security" {
  source = "../../modules/security"
  
  environment    = "prod"
  vpc_id         = module.networking.vpc_id
  container_port = 8000
}

# Now use the validated certificate in CloudFront
module "cloudfront" {
  source          = "../../modules/cloudfront"
  domain_name     = var.domain_name
  certificate_arn = aws_acm_certificate_validation.cloudfront.certificate_arn
  s3_bucket_id = module.s3.media_bucket_id
  s3_bucket_regional_domain = module.s3.media_bucket_regional_domain
}

# Finally, set up DNS records
module "dns" {
  source = "../../modules/dns"
  
  providers = {
    aws.cert-region = aws.us-east-1
  }
  domain_name                  = var.domain_name
  certificate_arn              = aws_acm_certificate.main.arn
  certificate_domain_validation = aws_acm_certificate.main.domain_validation_options
  cloudfront_certificate_arn   = aws_acm_certificate.cloudfront.arn
  cloudfront_certificate_domain_validation = aws_acm_certificate.cloudfront.domain_validation_options
  
  alb_dns_name  = module.alb.dns_name
  alb_zone_id   = module.alb.zone_id
  cf_domain_name = module.cloudfront.cf_domain_name
  cf_zone_id     = module.cloudfront.cf_hosted_zone_id
  depends_on = [module.cloudfront]
}

# Add explicit dependency for ALB
module "alb" {
  source = "../../modules/alb"
  
  environment          = "prod"
  vpc_id              = module.networking.vpc_id
  public_subnet_ids   = module.networking.public_subnet_ids
  alb_security_group_id = module.security.alb_security_group_id
  certificate_arn     = aws_acm_certificate_validation.main.certificate_arn
  depends_on      = []
}

module "rds" {
  source = "../../modules/rds"
  
  environment           = "prod"
  private_subnet_ids   = module.networking.private_subnet_ids
  rds_security_group_id = module.security.rds_security_group_id
  
  database_name     = "trazo"
  database_user     = "trazo_admin"
  database_password = var.database_password
  instance_class    = "db.t3.micro"
}

# Comment out or remove the Redis module completely
# module "redis" {
#   source = "../../modules/redis"
#   
#   environment            = "prod"
#   private_subnet_ids    = module.networking.private_subnet_ids
#   redis_security_group_id = module.security.redis_security_group_id
#   node_type             = "cache.t3.micro"
# }

module "ecs" {
  source = "../../modules/ecs"
  
  environment = "prod"
  region     = "us-east-2"
  aws_region = "us-east-2"
  
  database_host = module.rds.endpoint
  # Comment out this line to match the commented out variable in the module
  # redis_endpoint = module.redis.redis_endpoint
  
  ecs_exec_role_arn = aws_iam_role.ecs_execution_role.arn
  ecs_execution_role_arn = aws_iam_role.ecs_execution_role.arn
  ecs_task_role_arn = aws_iam_role.ecs_task_role.arn
  
  ecr_repository_url = aws_ecr_repository.main.repository_url
  secrets_arn        = aws_secretsmanager_secret.main.arn
  
  alb_dns_name     = module.alb.dns_name
  target_group_arn = module.alb.target_group_arn
  
  ecs_security_group_id = module.security.ecs_tasks_security_group_id
  private_subnet_ids    = module.networking.private_subnet_ids
  s3_bucket_name    = module.s3.media_bucket_id
  cloudfront_domain = module.cloudfront.cf_domain_name
  domain_name      = var.domain_name
}

module "s3" {
  source = "../../modules/s3"
  environment = "prod"
  domain_name = var.domain_name
  cf_oai_arn  = module.cloudfront.cf_oai_arn
}

# ECS Execution Role
resource "aws_iam_role" "ecs_execution_role" {
  name = "prod-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECS Task Role
resource "aws_iam_role" "ecs_task_role" {
  name = "prod-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# ECR Repository
resource "aws_ecr_repository" "main" {
  name = "trazo/backend"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Secrets Manager
resource "aws_secretsmanager_secret" "main" {
  name = "prod/trazo/backend"
}

resource "aws_secretsmanager_secret_version" "main" {
  secret_id = aws_secretsmanager_secret.main.id
  
  secret_string = jsonencode({
    SECRET_KEY        = var.django_secret_key
    DATABASE_NAME     = "trazo"
    DATABASE_USER     = "trazo_admin"
    DATABASE_PASSWORD = var.database_password
    DATABASE_HOST     = module.rds.endpoint
    SENDGRID_API_KEY  = var.sendgrid_api_key
    ALLOWED_HOSTS     = "api.trazo.io,${module.alb.dns_name}"
  })
}

# CloudWatch Log Group for ECS
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/prod"
  retention_in_days = 7

  tags = {
    Environment = "prod"
    Application = "trazo"
  }
}

resource "aws_iam_role_policy" "ecs_task_secrets" {
  name = "prod-ecs-task-secrets"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [aws_secretsmanager_secret.main.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy" "cloudfront_permissions" {
  name = "prod-cloudfront-permissions"
  role = aws_iam_role.ecs_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudfront:CreateCloudFrontOriginAccessIdentity",
          "cloudfront:CreateDistribution",
          "cloudfront:CreateResponseHeadersPolicy",
          "cloudfront:UpdateDistribution"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "terraform_permissions" {
  user       = "aws-cli"  # Your IAM user name
  policy_arn = aws_iam_policy.terraform_full_access.arn
}

resource "aws_iam_policy" "terraform_full_access" {
  name        = "TerraformManagedPolicy"
  description = "Permissions for Terraform deployments"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:*",
          "ecs:*",
          "rds:*",
          "s3:*",
          "iam:CreateRole",
          "iam:PutRolePolicy",
          "iam:PassRole",
          "route53:*",
          "acm:*",
          "cloudfront:*"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "cloudfront_admin" {
  user       = "aws-cli"  # Your terraform user
  policy_arn = "arn:aws:iam::aws:policy/CloudFrontFullAccess"
}

# resource "aws_acm_certificate_validation" "alb" {
#   certificate_arn         = aws_acm_certificate.main.arn
#   validation_record_fqdns = [for record in module.dns.cert_validation_records : record.fqdn]
# }

# Comment out or remove the budget resource since permissions are missing
# resource "aws_budgets_budget" "monthly" {
#   name         = "trazo-monthly-budget"
#   budget_type  = "COST"
#   limit_amount = "50"
#   limit_unit   = "USD"
#   time_unit    = "MONTHLY"
#   
#   notification {
#     comparison_operator        = "GREATER_THAN"
#     threshold                  = 80
#     threshold_type             = "PERCENTAGE"
#     notification_type          = "ACTUAL"
#     subscriber_email_addresses = ["your-email@example.com"]
#   }
# }

# Add this to trazo-back/terraform/environments/prod/main.tf
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "prod-ecs-execution-secrets"
  role = aws_iam_role.ecs_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = ["${aws_secretsmanager_secret.main.arn}*"]
      }
    ]
  })
}
