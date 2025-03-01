variable "database_password" {
  description = "Password for the RDS database"
  type        = string
  sensitive   = true
}

variable "django_secret_key" {
  description = "Secret key for Django application"
  type        = string
  sensitive   = true
}

variable "sendgrid_api_key" {
  description = "API key for SendGrid email service"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "trazo.io"
} 