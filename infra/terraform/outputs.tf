output "aws_region" {
  value       = var.aws_region
  description = "Deployment region."
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.backend.repository_url
  description = "ECR repository URL for backend image pushes."
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.main.name
  description = "ECS cluster name."
}

output "ecs_task_definition_arn" {
  value       = aws_ecs_task_definition.backend.arn
  description = "Task definition ARN."
}

output "ecs_service_name" {
  value       = try(aws_ecs_service.backend[0].name, null)
  description = "ECS service name when deploy_service=true."
}

