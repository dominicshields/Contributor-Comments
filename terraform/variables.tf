variable "project_name" {
  type        = string
  description = "Project name used for resource naming"
  default     = "contributor-comments"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "dev"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "eu-west-2"
}

variable "account_id" {
  type        = string
  description = "AWS account ID for globally unique naming"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where resources are created"
}

variable "db_subnet_ids" {
  type        = list(string)
  description = "Subnets used by RDS"
}

variable "app_security_group_id" {
  type        = string
  description = "Security group ID for the application runtime"
}

variable "db_name" {
  type        = string
  default     = "contributor_comments"
}

variable "db_username" {
  type        = string
  default     = "contrib_app"
}

variable "db_password" {
  type        = string
  sensitive   = true
}
