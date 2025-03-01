variable "domain_name" {
  description = "Domain name for the application"
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the ALB"
  type        = string
  default     = ""
}

variable "alb_zone_id" {
  description = "Zone ID of the ALB"
  type        = string
  default     = ""
} 

variable "cf_domain_name" {
  description = "Domain name of the CloudFront distribution"
  type        = string
}

variable "cf_zone_id" {
  description = "Zone ID of the CloudFront distribution"
  type        = string
}

variable "certificate_arn" {
  type = string
}

variable "certificate_domain_validation" {
  type = any
}

variable "cloudfront_certificate_arn" {
  type = string
}

variable "cloudfront_certificate_domain_validation" {
  type = any
}