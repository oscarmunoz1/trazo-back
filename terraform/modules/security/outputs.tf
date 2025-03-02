output "alb_security_group_id" {
  value = aws_security_group.alb.id
}

output "ecs_tasks_security_group_id" {
  value = aws_security_group.ecs_tasks.id
}

output "rds_security_group_id" {
  value = aws_security_group.rds.id
}

# Comment out or remove the Redis security group output
# output "redis_security_group_id" {
#   value = aws_security_group.redis.id
# } 