variable "project" {
  description = "Project name"
  type        = string
  default     = "mob"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "mob"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "mob_admin"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ for RDS"
  type        = bool
  default     = false
}

variable "db_backup_retention" {
  description = "RDS backup retention period in days"
  type        = number
  default     = 7
}

variable "db_skip_final_snapshot" {
  description = "Skip final snapshot on RDS deletion"
  type        = bool
  default     = false
}

variable "eks_node_instance_type" {
  description = "EKS node instance type"
  type        = string
  default     = "t3.medium"
}

variable "eks_desired_capacity" {
  description = "Desired number of EKS worker nodes"
  type        = number
  default     = 2
}

variable "eks_min_size" {
  description = "Minimum number of EKS worker nodes"
  type        = number
  default     = 1
}

variable "eks_max_size" {
  description = "Maximum number of EKS worker nodes"
  type        = number
  default     = 4
}

variable "api_replicas" {
  description = "Number of API replicas"
  type        = number
  default     = 2
}
