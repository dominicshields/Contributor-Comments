output "db_endpoint" {
  value       = aws_db_instance.postgres.address
  description = "RDS endpoint"
}

output "log_bucket_name" {
  value       = aws_s3_bucket.app_logs.bucket
  description = "S3 bucket name for application logs"
}
