# Trazo Infrastructure Documentation

## Overview

This repository contains Terraform code that provisions and manages the AWS infrastructure for the Trazo application. The infrastructure is designed with a focus on security, scalability, and cost optimization.

## Infrastructure Components

### State Management

- **S3 Backend**: Terraform state is stored in an S3 bucket (`trazo-terraform-state`) with versioning enabled
- **Region**: All resources are primarily deployed in `us-east-2` (Ohio)

### Networking

- **VPC**: Custom VPC with public and private subnets across multiple availability zones
- **Subnets**:
  - Public subnets for internet-facing resources (ALB)
  - Private subnets for application components (ECS, RDS, Redis)
- **Security Groups**: Defined for each component with least privilege access

### Compute

- **ECS Fargate**: Serverless container orchestration for the Django application
  - Task Definition: 256 CPU units, 512MB memory
  - Fargate Spot: Used for cost optimization (up to 70% cheaper than on-demand)
  - Auto Scaling: Based on CPU utilization (target: 80%)
  - Scheduled Scaling:
    - Scale down to 0 at 8PM UTC on weekdays
    - Scale down to 0 at 12AM UTC on weekends
    - Scale up to 1-2 instances at 8AM UTC on weekdays
    - Scale up to 1 instance at 10AM UTC on weekends

### Database

- **RDS PostgreSQL**: Managed relational database
- **Credentials**: Stored in AWS Secrets Manager

### Caching

- **ElastiCache Redis**: In-memory caching (currently commented out in some places)

### Storage

- **S3 Buckets**:
  - Static files bucket: For Django static assets
  - Media bucket: For user-uploaded content
  - ALB logs bucket: For load balancer access logs

### Content Delivery

- **CloudFront**: CDN for static content delivery
  - Custom domain: `static.trazo.io`
  - Security headers: Strict security headers configured
  - Origin Access Identity: Secure access to S3 bucket

### Load Balancing

- **Application Load Balancer (ALB)**:
  - Name: `prod-alb`
  - Listeners: HTTP (port 80) and HTTPS (port 443)
  - Target Group: Routes to ECS service
  - Health Check: Path `/health/` with HTTPS protocol

### DNS Management

- **Route53**: DNS management for `trazo.io` domain
  - `api.trazo.io`: Points to the ALB
  - `static.trazo.io`: Points to CloudFront distribution

### SSL/TLS

- **ACM Certificates**:
  - Certificate for `api.trazo.io` in us-east-2 (for ALB)
  - Certificate for `*.trazo.io` in us-east-1 (for CloudFront)

### Security

- **IAM Roles and Policies**:
  - ECS Task Execution Role: Permissions for ECS to pull images, write logs
  - ECS Task Role: Permissions for the application to access AWS services
  - Secrets Manager access: Controlled access to database credentials
  - S3 access: Permissions to read/write to S3 buckets

### Monitoring and Logging

- **CloudWatch Logs**: Container logs from ECS tasks
- **ALB Access Logs**: Stored in S3 (currently disabled)

## Cost Optimization Features

1. **Fargate Spot**: Uses spot pricing for ECS tasks
2. **Scheduled Scaling**: Scales down to zero during off-hours
3. **Auto Scaling**: Dynamically adjusts capacity based on demand
4. **Resource Sizing**: Minimal CPU/memory allocation for ECS tasks

## Deployment Architecture

User Request → Route53 → ALB → ECS Fargate (Django) → RDS PostgreSQL
→ Redis (Cache)
→ S3 (Media Storage)

Static Content: User → CloudFront → S3 (Static Bucket)

## Security Considerations

1. **Network Isolation**: Private subnets for sensitive components
2. **TLS Everywhere**: HTTPS for all external communication
3. **Least Privilege**: IAM roles with minimal permissions
4. **Security Headers**: Strict security headers via CloudFront
5. **Secrets Management**: Credentials stored in AWS Secrets Manager

## Terraform Modules

- **alb**: Application Load Balancer configuration
- **cloudfront**: CDN for static content delivery
- **dns**: Route53 DNS configuration
- **ecs**: ECS cluster, service, and task definitions
- **iam**: IAM roles and policies
- **networking**: VPC, subnets, and network ACLs
- **rds**: PostgreSQL database
- **redis**: ElastiCache Redis cluster
- **s3**: S3 buckets for static files and media
- **security**: Security groups and related resources

## Environment Management

The infrastructure is organized to support multiple environments:

- **Production**: Currently deployed environment
- **Staging**: Can be deployed using the same modules with different variables

## Maintenance and Operations

- **State Management**: Terraform state is stored in S3 with versioning enabled
- **Deployment**: Apply changes using Terraform CLI or CI/CD pipeline
- **Monitoring**: CloudWatch for logs and metrics
- **Scaling**: Automatic scaling based on demand and scheduled scaling for cost optimization

---

This infrastructure is designed to be secure, scalable, and cost-effective for the Trazo application, with particular attention to minimizing costs during off-hours while maintaining high availability during business hours.
