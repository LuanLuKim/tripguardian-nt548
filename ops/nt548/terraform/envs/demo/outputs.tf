output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "security_group_ids" {
  description = "alb / app / ops, for the modules still to come (#22, #24, #25)."
  value = {
    alb = module.network.sg_alb_id
    app = module.network.sg_app_id
    ops = module.network.sg_ops_id
  }
}

# ---------- contract with the deploy workflow (design §7.1) ----------

output "alb_dns_name" {
  description = "The app is http://<alb_dns_name>/."
  value       = module.alb.alb_dns_name
}

output "target_group_arn_blue" {
  value = module.alb.target_group_arns["blue"]
}

output "target_group_arn_green" {
  value = module.alb.target_group_arns["green"]
}

output "weight_blue" {
  description = "The input echoed back: ops/nt548/deploy_aws.sh reads the live color from the state (#50)."
  value       = var.weight_blue
}
