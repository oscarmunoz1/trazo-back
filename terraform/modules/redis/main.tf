resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.environment}-redis-subnet-group"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_parameter_group" "main" {
  family = "redis7"
  name   = "${var.environment}-redis-params-${random_id.suffix.hex}"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}

# Remove the existing Redis cluster to migrate to serverless
resource "aws_elasticache_serverless_cache" "redis" {
  engine       = "redis"
  name         = "${var.environment}-redis-serverless"
  description  = "Redis serverless cache for Django"
  
  security_group_ids = [var.redis_security_group_id]
  subnet_ids         = var.private_subnet_ids  # Use subnet_ids directly
  
  daily_snapshot_time = "05:00"
  
  cache_usage_limits {
    data_storage {
      maximum = 1  # 1 GB
      unit    = "GB"
    }
    
    ecpu_per_second {
      maximum = 1000  # 1000 eCPU
    }
  }
  
  tags = {
    Environment = var.environment
  }
}

# Update the output to reference the serverless endpoint
output "endpoint" {
  value = aws_elasticache_serverless_cache.redis.endpoint
} 