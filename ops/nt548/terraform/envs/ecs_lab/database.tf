resource "aws_db_subnet_group" "harness" {
  name       = "nt548-ecs-lab-postgres"
  subnet_ids = module.network.public_subnet_ids
}

resource "aws_db_instance" "harness" {
  identifier                  = "nt548-ecs-lab-postgres"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = "db.t3.micro"
  allocated_storage           = 20
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "tripguardian"
  username                    = "lab_admin"
  manage_master_user_password = true

  db_subnet_group_name    = aws_db_subnet_group.harness.name
  vpc_security_group_ids  = [module.network.sg_ops_id]
  publicly_accessible     = false
  multi_az                = false
  backup_retention_period = 1
  skip_final_snapshot     = true # The lab holds synthetic data only.
}
