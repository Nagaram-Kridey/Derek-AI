terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  # Use encrypted remote state for a shared deployment. State contains the Redis password.
}

provider "aws" { region = var.region }
variable "region" { default = "ap-south-1" }
variable "domain" {
  type = string
  validation {
    condition = can(regex("^[a-z0-9][a-z0-9.-]+\\.[a-z]{2,}$", var.domain))
    error_message = "Set a lowercase DNS hostname without schemes, ports or whitespace."
  }
}
variable "instance_type" { default = "t3.medium" }
variable "budget_usd" { type = number }
variable "budget_email" { type = string }

data "aws_availability_zones" "available" { state = "available" }
data "aws_ami" "ubuntu" {
  most_recent = true
  owners = ["099720109477"]
  filter {
    name = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name = "architecture"
    values = ["x86_64"]
  }
}
resource "aws_vpc" "main" {
  cidr_block = "10.73.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support = true
  tags = { Name = "lilyleo" }
}
resource "aws_internet_gateway" "main" { vpc_id = aws_vpc.main.id }
resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id
  cidr_block = "10.73.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}
resource "aws_route_table_association" "public" {
  subnet_id = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
resource "aws_subnet" "private" {
  count = 2
  vpc_id = aws_vpc.main.id
  cidr_block = "10.73.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
}
resource "aws_security_group" "app" {
  name_prefix = "lilyleo-app-"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "data" {
  name_prefix = "lilyleo-data-"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port = 5432
    to_port = 5432
    protocol = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  ingress {
    from_port = 6379
    to_port = 6379
    protocol = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}
resource "aws_db_subnet_group" "main" { subnet_ids = aws_subnet.private[*].id }
resource "aws_db_instance" "main" {
  identifier = "lilyleo"
  engine = "postgres"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  max_allocated_storage = 50
  db_name = "lilyleo"
  username = "lily"
  manage_master_user_password = true
  storage_encrypted = true
  publicly_accessible = false
  vpc_security_group_ids = [aws_security_group.data.id]
  db_subnet_group_name = aws_db_subnet_group.main.name
  backup_retention_period = 7
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "lilyleo-final"
}
resource "random_password" "redis" {
  length = 48
  special = false
}
resource "aws_secretsmanager_secret" "redis" { name_prefix = "lilyleo-redis-" }
resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id
  secret_string = jsonencode({ password = random_password.redis.result })
}
resource "aws_elasticache_subnet_group" "main" {
  name = "lilyleo"
  subnet_ids = aws_subnet.private[*].id
}
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "lilyleo"
  description = "Lily-Leo private task queue"
  node_type = "cache.t3.micro"
  num_cache_clusters = 1
  engine = "redis"
  engine_version = "7.1"
  port = 6379
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token = random_password.redis.result
  security_group_ids = [aws_security_group.data.id]
  subnet_group_name = aws_elasticache_subnet_group.main.name
  snapshot_retention_limit = 3
}
resource "random_id" "bucket" { byte_length = 4 }
resource "aws_s3_bucket" "reports" { bucket = "lilyleo-reports-${random_id.bucket.hex}" }
resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    id = "remove-deleted-versions"
    status = "Enabled"
    filter { prefix = "" }
    noncurrent_version_expiration { noncurrent_days = 7 }
  }
}
resource "aws_secretsmanager_secret" "app" { name_prefix = "lilyleo-app-" }
resource "aws_ecr_repository" "app" {
  name = "lilyleo"
  image_scanning_configuration { scan_on_push = true }
}
resource "aws_cloudwatch_log_group" "app" {
  name = "/lilyleo/app"
  retention_in_days = 14
}
resource "aws_iam_role" "app" {
  name_prefix = "lilyleo-"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy" "app" {
  role = aws_iam_role.app.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = [aws_secretsmanager_secret.app.arn, aws_secretsmanager_secret.redis.arn, aws_db_instance.main.master_user_secret[0].secret_arn] },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.reports.arn}/*" },
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.reports.arn },
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = aws_ecr_repository.app.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }
  ] })
}
resource "aws_iam_instance_profile" "app" { role = aws_iam_role.app.name }
resource "aws_instance" "app" {
  ami = data.aws_ami.ubuntu.id
  instance_type = var.instance_type
  subnet_id = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile = aws_iam_instance_profile.app.name
  metadata_options {
    http_tokens = "required"
    http_put_response_hop_limit = 2
  }
  root_block_device {
    volume_size = 30
    encrypted = true
  }
  user_data = templatefile("${path.module}/bootstrap.sh.tftpl", {
    region = var.region, domain = var.domain,
    app_secret = aws_secretsmanager_secret.app.arn,
    db_secret = aws_db_instance.main.master_user_secret[0].secret_arn,
    redis_secret = aws_secretsmanager_secret.redis.arn,
    db_host = aws_db_instance.main.address,
    redis_host = aws_elasticache_replication_group.main.primary_endpoint_address,
    bucket = aws_s3_bucket.reports.id
  })
  tags = { Name = "lilyleo" }
}
resource "aws_eip" "app" {
  domain = "vpc"
  instance = aws_instance.app.id
}
resource "aws_cloudwatch_metric_alarm" "status" {
  alarm_name = "lilyleo-instance-health"
  namespace = "AWS/EC2"
  metric_name = "StatusCheckFailed"
  dimensions = { InstanceId = aws_instance.app.id }
  statistic = "Maximum"
  period = 60
  evaluation_periods = 2
  threshold = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
}
resource "aws_budgets_budget" "monthly" {
  name = "lilyleo-monthly"
  budget_type = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit = "USD"
  time_unit = "MONTHLY"
  notification {
    comparison_operator = "GREATER_THAN"
    threshold = 80
    threshold_type = "PERCENTAGE"
    notification_type = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
output "instance_id" { value = aws_instance.app.id }
output "public_ip" { value = aws_eip.app.public_ip }
output "repository_url" { value = aws_ecr_repository.app.repository_url }
output "app_secret_arn" { value = aws_secretsmanager_secret.app.arn }
output "domain" { value = var.domain }
output "region" { value = var.region }
