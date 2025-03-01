terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version              = ">= 4.0.0"
      configuration_aliases = [aws.cert-region]
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9.1"
    }
  }
} 