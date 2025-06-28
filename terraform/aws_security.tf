# AWS Security Infrastructure for Trazo
# Implements secure key management using KMS and Secrets Manager
# Addresses CRITICAL security vulnerabilities in blockchain and API key management

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "trazo"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "key_rotation_days" {
  description = "Number of days before key rotation is required"
  type        = number
  default     = 90
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local values
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "carbon-verification-security"
  }
  
  secret_names = {
    blockchain_key = "${var.project_name}/blockchain/private_key"
    usda_keys     = "${var.project_name}/usda/api_keys"
    multisig_signers = "${var.project_name}/blockchain/multisig_signers"
  }
}

# KMS Key for encryption
resource "aws_kms_key" "trazo_security" {
  description              = "Trazo Carbon Verification Security Key"
  deletion_window_in_days  = 30
  key_usage               = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Trazo Application Access"
        Effect = "Allow"
        Principal = {
          AWS = [
            aws_iam_role.trazo_app_role.arn,
            aws_iam_role.trazo_key_rotation_role.arn
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
  
  tags = merge(local.common_tags, {
    Name = "trazo-security-key"
  })
}

# KMS Key Alias
resource "aws_kms_alias" "trazo_security" {
  name          = "alias/${var.project_name}-security-${var.environment}"
  target_key_id = aws_kms_key.trazo_security.key_id
}

# Secrets Manager Secrets
resource "aws_secretsmanager_secret" "blockchain_private_key" {
  name                    = local.secret_names.blockchain_key
  description            = "Blockchain private key for Trazo carbon verification"
  kms_key_id             = aws_kms_key.trazo_security.arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  
  tags = merge(local.common_tags, {
    Name        = "trazo-blockchain-key"
    SecretType  = "blockchain-key"
    Rotation    = "manual"
  })
}

resource "aws_secretsmanager_secret" "usda_api_keys" {
  name                    = local.secret_names.usda_keys
  description            = "USDA API keys for carbon calculation services"
  kms_key_id             = aws_kms_key.trazo_security.arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  
  tags = merge(local.common_tags, {
    Name        = "trazo-usda-keys"
    SecretType  = "api-keys"
    Rotation    = "automatic"
  })
}

resource "aws_secretsmanager_secret" "multisig_signers" {
  name                    = local.secret_names.multisig_signers
  description            = "Multi-signature authorized signers for Trazo"
  kms_key_id             = aws_kms_key.trazo_security.arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  
  tags = merge(local.common_tags, {
    Name        = "trazo-multisig-signers"
    SecretType  = "configuration"
    Rotation    = "manual"
  })
}

# Initial secret values (will be updated by application)
resource "aws_secretsmanager_secret_version" "multisig_signers_initial" {
  secret_id = aws_secretsmanager_secret.multisig_signers.id
  secret_string = jsonencode({
    signers = [
      {
        address    = "0x742d35Cc6634C0532925a3b8d1c8b2b8b1f6E8B4"
        role       = "admin"
        name       = "Primary Admin"
        created_at = formatdate("YYYY-MM-DD hh:mm:ss", timestamp())
      },
      {
        address    = "0x8ba1f109551bD432803012645Hac136c02142AC8"
        role       = "operator"
        name       = "Operations Manager"
        created_at = formatdate("YYYY-MM-DD hh:mm:ss", timestamp())
      }
    ]
    created_at = formatdate("YYYY-MM-DD hh:mm:ss", timestamp())
    configuration = {
      required_signatures = 2
      max_signers        = 5
    }
  })
  
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# IAM Role for Trazo Application
resource "aws_iam_role" "trazo_app_role" {
  name = "${var.project_name}-app-role-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      },
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# IAM Policy for Secrets Manager Access
resource "aws_iam_policy" "trazo_secrets_policy" {
  name        = "${var.project_name}-secrets-policy-${var.environment}"
  description = "Policy for Trazo application to access secrets"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:PutSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.blockchain_private_key.arn,
          aws_secretsmanager_secret.usda_api_keys.arn,
          aws_secretsmanager_secret.multisig_signers.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:ListSecrets"
        ]
        Resource = "*"
        Condition = {
          StringLike = {
            "secretsmanager:ResourceTag/Project" = var.project_name
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.trazo_security.arn
      }
    ]
  })
  
  tags = local.common_tags
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "trazo_secrets_attachment" {
  role       = aws_iam_role.trazo_app_role.name
  policy_arn = aws_iam_policy.trazo_secrets_policy.arn
}

# IAM Role for Key Rotation
resource "aws_iam_role" "trazo_key_rotation_role" {
  name = "${var.project_name}-key-rotation-role-${var.environment}"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# IAM Policy for Key Rotation
resource "aws_iam_policy" "trazo_key_rotation_policy" {
  name        = "${var.project_name}-key-rotation-policy-${var.environment}"
  description = "Policy for automated key rotation"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:RotateSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:UpdateSecretVersionStage",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.usda_api_keys.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.trazo_security.arn
      }
    ]
  })
  
  tags = local.common_tags
}

# Attach rotation policy to role
resource "aws_iam_role_policy_attachment" "trazo_key_rotation_attachment" {
  role       = aws_iam_role.trazo_key_rotation_role.name
  policy_arn = aws_iam_policy.trazo_key_rotation_policy.arn
}

# CloudWatch Log Group for Security Events
resource "aws_cloudwatch_log_group" "trazo_security_logs" {
  name              = "/aws/${var.project_name}/security/${var.environment}"
  retention_in_days = var.environment == "prod" ? 365 : 30
  kms_key_id        = aws_kms_key.trazo_security.arn
  
  tags = merge(local.common_tags, {
    Name = "trazo-security-logs"
  })
}

# CloudWatch Alarms for Security Monitoring
resource "aws_cloudwatch_metric_alarm" "secret_access_failures" {
  alarm_name          = "${var.project_name}-secret-access-failures-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/SecretsManager"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors failed secret access attempts"
  
  alarm_actions = [aws_sns_topic.security_alerts.arn]
  
  dimensions = {
    SecretArn = aws_secretsmanager_secret.blockchain_private_key.arn
  }
  
  tags = local.common_tags
}

# SNS Topic for Security Alerts
resource "aws_sns_topic" "security_alerts" {
  name              = "${var.project_name}-security-alerts-${var.environment}"
  kms_master_key_id = aws_kms_key.trazo_security.arn
  
  tags = merge(local.common_tags, {
    Name = "trazo-security-alerts"
  })
}

# Lambda Function for Key Rotation Monitoring
resource "aws_lambda_function" "key_rotation_monitor" {
  count = var.environment == "prod" ? 1 : 0
  
  filename         = "key_rotation_monitor.zip"
  function_name    = "${var.project_name}-key-rotation-monitor-${var.environment}"
  role            = aws_iam_role.trazo_key_rotation_role.arn
  handler         = "index.handler"
  source_code_hash = data.archive_file.key_rotation_monitor[0].output_base64sha256
  runtime         = "python3.9"
  timeout         = 300
  
  environment {
    variables = {
      SECRET_NAMES = jsonencode([
        local.secret_names.blockchain_key,
        local.secret_names.usda_keys
      ])
      ROTATION_DAYS = var.key_rotation_days
      SNS_TOPIC_ARN = aws_sns_topic.security_alerts.arn
    }
  }
  
  tags = local.common_tags
}

# Lambda deployment package
data "archive_file" "key_rotation_monitor" {
  count = var.environment == "prod" ? 1 : 0
  
  type        = "zip"
  output_path = "key_rotation_monitor.zip"
  
  source {
    content = <<EOF
import json
import boto3
import os
from datetime import datetime, timedelta

def handler(event, context):
    secrets_client = boto3.client('secretsmanager')
    sns_client = boto3.client('sns')
    
    secret_names = json.loads(os.environ['SECRET_NAMES'])
    rotation_days = int(os.environ['ROTATION_DAYS'])
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    
    alerts = []
    
    for secret_name in secret_names:
        try:
            response = secrets_client.describe_secret(SecretId=secret_name)
            last_changed = response.get('LastChangedDate')
            
            if last_changed:
                days_old = (datetime.now(last_changed.tzinfo) - last_changed).days
                
                if days_old > rotation_days:
                    alerts.append(f"Secret {secret_name} is {days_old} days old and requires rotation")
                elif days_old > (rotation_days - 7):
                    alerts.append(f"Secret {secret_name} will require rotation in {rotation_days - days_old} days")
            
        except Exception as e:
            alerts.append(f"Error checking secret {secret_name}: {str(e)}")
    
    if alerts:
        message = "Trazo Security Alert - Key Rotation Required:\\n\\n" + "\\n".join(alerts)
        
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject="Trazo Key Rotation Alert"
        )
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Checked {len(secret_names)} secrets, {len(alerts)} alerts sent')
    }
EOF
    filename = "index.py"
  }
}

# EventBridge Rule for Daily Key Rotation Check
resource "aws_cloudwatch_event_rule" "daily_key_rotation_check" {
  count = var.environment == "prod" ? 1 : 0
  
  name                = "${var.project_name}-daily-key-rotation-check-${var.environment}"
  description         = "Trigger key rotation monitoring daily"
  schedule_expression = "cron(0 9 * * ? *)"  # 9 AM UTC daily
  
  tags = local.common_tags
}

# EventBridge Target
resource "aws_cloudwatch_event_target" "key_rotation_monitor_target" {
  count = var.environment == "prod" ? 1 : 0
  
  rule      = aws_cloudwatch_event_rule.daily_key_rotation_check[0].name
  target_id = "KeyRotationMonitorTarget"
  arn       = aws_lambda_function.key_rotation_monitor[0].arn
}

# Lambda Permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge" {
  count = var.environment == "prod" ? 1 : 0
  
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.key_rotation_monitor[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_key_rotation_check[0].arn
}

# Instance Profile for EC2 instances
resource "aws_iam_instance_profile" "trazo_app_profile" {
  name = "${var.project_name}-app-profile-${var.environment}"
  role = aws_iam_role.trazo_app_role.name
  
  tags = local.common_tags
}

# Outputs
output "kms_key_id" {
  description = "KMS Key ID for Trazo security"
  value       = aws_kms_key.trazo_security.id
}

output "kms_key_arn" {
  description = "KMS Key ARN for Trazo security"
  value       = aws_kms_key.trazo_security.arn
}

output "secrets" {
  description = "Secret ARNs for Trazo application"
  value = {
    blockchain_key   = aws_secretsmanager_secret.blockchain_private_key.arn
    usda_keys       = aws_secretsmanager_secret.usda_api_keys.arn
    multisig_signers = aws_secretsmanager_secret.multisig_signers.arn
  }
}

output "iam_role_arn" {
  description = "IAM Role ARN for Trazo application"
  value       = aws_iam_role.trazo_app_role.arn
}

output "instance_profile_name" {
  description = "Instance Profile name for EC2 instances"
  value       = aws_iam_instance_profile.trazo_app_profile.name
}

output "security_log_group" {
  description = "CloudWatch Log Group for security events"
  value       = aws_cloudwatch_log_group.trazo_security_logs.name
}

output "sns_topic_arn" {
  description = "SNS Topic ARN for security alerts"
  value       = aws_sns_topic.security_alerts.arn
}