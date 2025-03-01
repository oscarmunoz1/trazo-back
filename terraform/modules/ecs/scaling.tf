resource "aws_appautoscaling_scheduled_action" "scale_down" {
  name               = "scale-down-evening"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.django.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule           = "cron(0 20 ? * MON-FRI *)"  # 8PM UTC weekdays (earlier shutdown)
  
  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }
}

# Add weekend scaling to 0
resource "aws_appautoscaling_scheduled_action" "scale_down_weekend" {
  name               = "scale-down-weekend"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.django.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule           = "cron(0 0 ? * SAT-SUN *)"  # 12AM UTC weekends
  
  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }
}

resource "aws_appautoscaling_scheduled_action" "scale_up_weekend" {
  name               = "scale-up-weekend"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.django.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule           = "cron(0 10 ? * SAT-SUN *)"  # 10AM UTC weekends
  
  scalable_target_action {
    min_capacity = 1
    max_capacity = 1  # Lower max capacity on weekends
  }
}

resource "aws_appautoscaling_scheduled_action" "scale_up" {
  name               = "scale-up-morning"
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.django.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  schedule           = "cron(0 8 ? * MON-FRI *)"  # 8AM UTC weekdays
  
  scalable_target_action {
    min_capacity = 1
    max_capacity = 2
  }
} 