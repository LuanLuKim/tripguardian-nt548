output "state_bucket" {
  description = "Bucket of the envs/demo state (terraform init -backend-config=bucket=<this>)."
  value       = aws_s3_bucket.state.bucket
}

output "ops_instance_id" {
  description = "aws-down stops it, aws-up starts it."
  value       = aws_instance.ops.id
}

output "ops_private_ip" {
  value = aws_instance.ops.private_ip
}

output "database_url_parameter" {
  description = "SSM parameter holding the database URL of the app instances."
  value       = aws_ssm_parameter.database_url.name
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}
