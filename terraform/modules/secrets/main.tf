resource "aws_secretsmanager_secret" "django_secret" {
  name = "trazo/prod/django"
}

resource "aws_secretsmanager_secret_version" "django_secret_version" {
  secret_id = aws_secretsmanager_secret.django_secret.id
  secret_string = jsonencode({
    SECRET_KEY           = var.django_secret_key
    DATABASE_NAME        = var.db_name
    DATABASE_USER        = var.db_username
    DATABASE_PASSWORD    = var.db_password
    DATABASE_HOST        = var.db_host
    REDIS_ENDPOINT       = var.redis_endpoint
    SENDGRID_API_KEY     = var.sendgrid_api_key
    ALLOWED_HOSTS        = var.allowed_hosts
  })
} 