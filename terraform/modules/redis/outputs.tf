output "redis_endpoint" {
  # Extract the first endpoint from the list and format it for Django
  value = length(aws_elasticache_serverless_cache.redis.endpoint) > 0 ? replace(aws_elasticache_serverless_cache.redis.endpoint[0].address, "redis://", "") : ""
} 