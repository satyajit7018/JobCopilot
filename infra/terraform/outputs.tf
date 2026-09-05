output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.jobcopilot_vpc.id
}

output "rds_endpoint" {
  description = "Connection endpoint for PostgreSQL database"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_port" {
  description = "Port for PostgreSQL database"
  value       = aws_db_instance.postgres.port
}

output "redis_primary_endpoint" {
  description = "Primary endpoint address for ElastiCache Redis replication group"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "s3_bucket_name" {
  description = "Name of the S3 storage bucket"
  value       = aws_s3_bucket.documents.id
}

output "eks_cluster_endpoint" {
  description = "Endpoint for EKS Kubernetes API"
  value       = aws_eks_cluster.main.endpoint
}

output "eks_cluster_name" {
  description = "Kubernetes cluster name"
  value       = aws_eks_cluster.main.name
}
