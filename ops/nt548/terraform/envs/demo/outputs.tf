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
