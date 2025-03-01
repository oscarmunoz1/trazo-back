output "certificate_arn" {
  description = "ARN of the SSL certificate"
  value       = var.certificate_arn
}

output "domain_name" {
  description = "Domain name"
  value       = var.domain_name
}

output "nameservers" {
  description = "Nameservers for the domain"
  value       = data.aws_route53_zone.main.name_servers
}

output "zone_id" {
  description = "Route53 Zone ID"
  value       = data.aws_route53_zone.main.zone_id
}

output "cert_validation_records" {
  value = aws_route53_record.cert_validation
} 