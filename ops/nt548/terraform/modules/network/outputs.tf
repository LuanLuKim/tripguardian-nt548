output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "One per AZ, in the order of var.azs (ALB and ASGs use all of them)."
  value       = aws_subnet.public[*].id
}

output "sg_alb_id" {
  value = aws_security_group.alb.id
}

output "sg_app_id" {
  value = aws_security_group.app.id
}

output "sg_ops_id" {
  value = aws_security_group.ops.id
}
