resource "aws_db_subnet_group" "main" {
  name       = "${var.environment}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.environment}-db-subnet-group"
  }
}

resource "aws_db_instance" "main" {
  identifier = "${var.environment}-postgres"
  
  engine         = "postgres"
  engine_version = "17.4"
  instance_class = "db.t3.micro"
  
  allocated_storage     = 20
  storage_type         = "gp3"
  max_allocated_storage = 0
  
  db_name  = var.database_name
  username = var.database_user
  password = var.database_password
  
  vpc_security_group_ids = [var.rds_security_group_id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  multi_az               = false
  publicly_accessible    = false
  
  performance_insights_enabled = false
  monitoring_interval         = 0
  
  backup_retention_period = 1
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"
  
  auto_minor_version_upgrade = true
  deletion_protection       = false
  skip_final_snapshot       = true
  final_snapshot_identifier = "${var.environment}-postgres-final-snapshot"
  
  storage_encrypted      = true
  copy_tags_to_snapshot  = true
  
  tags = {
    Name = "${var.environment}-postgres"
  }
}

resource "aws_iam_role" "rds_monitoring_role" {
  name = "${var.environment}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring_policy" {
  role       = aws_iam_role.rds_monitoring_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
} 