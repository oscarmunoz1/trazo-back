output "cf_oai_arn" {
  value = aws_cloudfront_origin_access_identity.static.iam_arn
}

output "cf_domain_name" {
  value = aws_cloudfront_distribution.static.domain_name
}

output "cf_hosted_zone_id" {
  value = aws_cloudfront_distribution.static.hosted_zone_id
}