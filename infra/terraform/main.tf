terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "JobCopilot"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# 1. High-Availability VPC & Subnets
resource "aws_vpc" "jobcopilot_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "jobcopilot-vpc-${var.environment}"
  }
}

resource "aws_subnet" "public_1" {
  vpc_id            = aws_vpc.jobcopilot_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "jobcopilot-pub-subnet-1-${var.environment}"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_subnet" "public_2" {
  vpc_id            = aws_vpc.jobcopilot_vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "jobcopilot-pub-subnet-2-${var.environment}"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_subnet" "private_1" {
  vpc_id            = aws_vpc.jobcopilot_vpc.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "jobcopilot-priv-subnet-1-${var.environment}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.jobcopilot_vpc.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "${var.aws_region}b"

  tags = {
    Name = "jobcopilot-priv-subnet-2-${var.environment}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

# 2. Database Subnet Group & Multi-AZ RDS PostgreSQL
resource "aws_db_subnet_group" "db_subnets" {
  name       = "jobcopilot-db-subnets-${var.environment}"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]
}

resource "aws_security_group" "rds_sg" {
  name        = "jobcopilot-rds-sg-${var.environment}"
  description = "Controls database ingress from Kubernetes worker nodes"
  vpc_id      = aws_vpc.jobcopilot_vpc.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    cidr_blocks     = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "jobcopilot-db-${var.environment}"
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = var.db_instance_class
  allocated_storage      = 50
  max_allocated_storage  = 200
  storage_type           = "gp3"
  multi_az               = true
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.db_subnets.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  db_name  = "jobcopilot"
  username = "jobcopilot_admin"
  password = "CHANGE_ME_SECURE_PASSWORD_IN_SECRETS_MANAGER"

  backup_retention_period   = 14
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:30-Mon:05:30"
  auto_minor_version_upgrade = true
  deletion_protection       = true
  storage_encrypted         = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "jobcopilot-db-final-snapshot"
}

# 3. ElastiCache Redis Subnet Group & Replication Group
resource "aws_elasticache_subnet_group" "redis_subnets" {
  name       = "jobcopilot-redis-subnets-${var.environment}"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]
}

resource "aws_security_group" "redis_sg" {
  name        = "jobcopilot-redis-sg-${var.environment}"
  description = "Controls Redis access from application and worker pods"
  vpc_id      = aws_vpc.jobcopilot_vpc.id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id          = "jobcopilot-redis-${var.environment}"
  description                   = "Redis cluster for Celery queues and multi-tier tenant caching"
  node_type                     = var.redis_node_type
  num_cache_clusters            = 2
  parameter_group_name          = "default.redis7"
  port                          = 6379
  subnet_group_name             = aws_elasticache_subnet_group.redis_subnets.name
  security_group_ids            = [aws_security_group.redis_sg.id]
  automatic_failover_enabled    = true
  multi_az_enabled              = true
  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
}

# 4. S3 Bucket for Multi-Tenant Storage & Encrypted Resumes
resource "aws_s3_bucket" "documents" {
  bucket = "jobcopilot-docs-${var.environment}-${var.aws_region}"
}

resource "aws_s3_bucket_versioning" "docs_versioning" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "docs_encryption" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "docs_block_public" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
