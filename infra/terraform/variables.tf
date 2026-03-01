variable "aws_region" {
  type        = string
  description = "AWS region for MVP bootstrap resources."
  default     = "us-east-1"
}

variable "app_name" {
  type        = string
  description = "Resource name prefix for phase-0 deployment."
  default     = "voice-bot-mvp"
}

variable "image_tag" {
  type        = string
  description = "Container image tag to deploy."
  default     = "latest"
}

variable "container_port" {
  type        = number
  description = "Container listening port."
  default     = 8000
}

variable "cpu" {
  type        = number
  description = "Fargate task CPU units."
  default     = 256
}

variable "memory" {
  type        = number
  description = "Fargate task memory (MiB)."
  default     = 512
}

variable "deploy_service" {
  type        = bool
  description = "Create ECS service when networking inputs are provided."
  default     = false
}

variable "desired_count" {
  type        = number
  description = "Desired ECS task count when deploy_service is true."
  default     = 1
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnets for ECS service ENIs."
  default     = []
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security groups for ECS service ENIs."
  default     = []
}

variable "task_role_arn" {
  type        = string
  description = "Optional existing task role; defaults to execution role when empty."
  default     = ""
}

