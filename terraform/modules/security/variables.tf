variable "environment" {
  description = "The environment (prod/staging)"
  type        = string
}

variable "vpc_id" {
  description = "The VPC ID"
  type        = string
}

variable "container_port" {
  description = "Port exposed by the docker image"
  type        = number
  default     = 8000
} 