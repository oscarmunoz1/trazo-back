resource "aws_cloudfront_distribution" "static" {
  origin {
    domain_name = var.s3_bucket_regional_domain
    origin_id   = "S3-${var.s3_bucket_id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.static.cloudfront_access_identity_path
    }
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${var.s3_bucket_id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 86400    # 1 day
    default_ttl            = 604800   # 1 week
    max_ttl                = 31536000 # 1 year
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
  }

  price_class = "PriceClass_100"

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn = var.certificate_arn
    ssl_support_method  = "sni-only"
  }

  aliases = ["static.${var.domain_name}"]
}

resource "aws_cloudfront_origin_access_identity" "static" {
  comment = "OAI for static content"
}

resource "aws_cloudfront_response_headers_policy" "security" {
  name = "security-headers"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override       = true
    }
    xss_protection {
      mode_block  = true
      protection  = true
      override    = true
    }
    strict_transport_security {
      access_control_max_age_sec = 63072000  # 2 years
      include_subdomains          = true
      preload                     = true
      override                    = true
    }
  }
} 