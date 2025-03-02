data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.environment}-vpc"
  }
}

# Public Subnets in two AZs
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.environment}-public-${count.index + 1}"
  }
}

# Private Subnets in two AZs
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 2)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.environment}-private-${count.index + 1}"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.environment}-igw"
  }
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.environment}-public-rt"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.environment}-private-rt"
  }
}

# Add NAT Instance
resource "aws_instance" "nat" {
  ami                    = "ami-0fa399d9c130ec923" # Amazon Linux 2 NAT AMI for us-east-2
  instance_type          = "t3.nano"               # Changed from t4g.nano to t3.nano for x86_64 compatibility
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.nat.id]
  source_dest_check      = false                   # Required for NAT functionality
  
  user_data = <<-EOF
              #!/bin/bash
              sysctl -w net.ipv4.ip_forward=1
              /sbin/iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
              EOF
  
  tags = {
    Name = "${var.environment}-nat-instance"
  }
}

resource "aws_security_group" "nat" {
  name        = "${var.environment}-nat-sg"
  description = "Security group for NAT instance"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "${var.environment}-nat-sg"
  }
}

# Get the primary network interface ID of the NAT instance
data "aws_network_interface" "nat" {
  depends_on = [aws_instance.nat]
  
  filter {
    name   = "attachment.instance-id"
    values = [aws_instance.nat.id]
  }
  
  filter {
    name   = "attachment.device-index"
    values = ["0"]
  }
}

# Instead of creating a new route, modify the existing default route
# First, find all existing routes in the private route table
resource "null_resource" "update_route" {
  depends_on = [aws_route_table.private, aws_instance.nat, data.aws_network_interface.nat]

  # This will run every time the NAT instance or network interface changes
  triggers = {
    nat_instance_id = aws_instance.nat.id
    network_interface_id = data.aws_network_interface.nat.id
  }

  # Use local-exec to update the route using AWS CLI
  provisioner "local-exec" {
    command = <<-EOT
      # Delete any existing default route
      aws ec2 describe-route-tables --route-table-id ${aws_route_table.private.id} --query 'RouteTables[0].Routes[?DestinationCidrBlock==`0.0.0.0/0`]' --output text | grep -q '0.0.0.0/0' && \
      aws ec2 delete-route --route-table-id ${aws_route_table.private.id} --destination-cidr-block 0.0.0.0/0 || echo "No default route exists"
      
      # Create new route pointing to our NAT instance's network interface
      aws ec2 create-route --route-table-id ${aws_route_table.private.id} --destination-cidr-block 0.0.0.0/0 --network-interface-id ${data.aws_network_interface.nat.id}
    EOT
  }
}

# Route Table Associations
resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Comment out the CloudWatch Event Rules for now since we don't have the necessary permissions
# We can add these back later after setting up the proper IAM permissions

# resource "aws_cloudwatch_event_rule" "stop_nat_instance" {
#   name                = "stop-nat-instance"
#   description         = "Stop NAT instance during off-hours"
#   schedule_expression = "cron(0 20 ? * MON-FRI *)" # 8PM UTC weekdays
# }
# 
# resource "aws_cloudwatch_event_rule" "start_nat_instance" {
#   name                = "start-nat-instance"
#   description         = "Start NAT instance during business hours"
#   schedule_expression = "cron(0 8 ? * MON-FRI *)" # 8AM UTC weekdays
# }
# 
# resource "aws_cloudwatch_event_target" "stop_nat_instance" {
#   rule      = aws_cloudwatch_event_rule.stop_nat_instance.name
#   target_id = "stop_nat_instance"
#   arn       = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:automation-definition/AWS-StopEC2Instance"
#   
#   input = jsonencode({
#     InstanceId = [aws_instance.nat.id]
#   })
# }
# 
# resource "aws_cloudwatch_event_target" "start_nat_instance" {
#   rule      = aws_cloudwatch_event_rule.start_nat_instance.name
#   target_id = "start_nat_instance"
#   arn       = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:automation-definition/AWS-StartEC2Instance"
#   
#   input = jsonencode({
#     InstanceId = [aws_instance.nat.id]
#   })
# }

# Add this data source at the top of the file
data "aws_caller_identity" "current" {}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type = "Interface"
  
  subnet_ids = aws_subnet.private[*].id
  
  security_group_ids = [
    aws_security_group.vpc_endpoints.id
  ]
  
  private_dns_enabled = true
}

resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.environment}-vpc-endpoints-sg"
  description = "Security group for VPC endpoints"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ECR API Endpoint
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type = "Interface"
  subnet_ids        = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}

# ECR Docker Endpoint
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type = "Interface"
  subnet_ids        = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}

# Add S3 Gateway Endpoint (ECR uses S3 for layer storage)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
}

# Add CloudWatch Logs Endpoint (for Container Logs)
resource "aws_vpc_endpoint" "logs" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type = "Interface"
  subnet_ids        = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
} 