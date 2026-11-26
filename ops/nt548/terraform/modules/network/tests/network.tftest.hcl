# terraform -chdir=ops/nt548/terraform/modules/network init -backend=false && terraform -chdir=... test
# Mocked provider: no AWS account or credentials needed. `apply` runs against the mock, so ids are known.

mock_provider "aws" {}

variables {
  name_prefix = "nt548"
}

run "two_public_subnets_in_two_azs_behind_one_igw" {
  command = apply

  assert {
    condition     = length(aws_subnet.public) == 2 && aws_subnet.public[0].availability_zone != aws_subnet.public[1].availability_zone
    error_message = "one public subnet in each of two AZs"
  }

  assert {
    condition     = [for s in aws_subnet.public : s.cidr_block] == ["10.48.0.0/24", "10.48.1.0/24"]
    error_message = "subnets are the /24s of the VPC CIDR"
  }

  assert {
    condition     = alltrue([for s in aws_subnet.public : s.map_public_ip_on_launch])
    error_message = "no NAT: instances need a public IP"
  }

  assert {
    condition     = aws_route.internet.destination_cidr_block == "0.0.0.0/0" && aws_route.internet.gateway_id == aws_internet_gateway.this.id
    error_message = "the default route goes to the internet gateway"
  }

  assert {
    condition     = length(aws_route_table_association.public) == 2
    error_message = "both subnets use the public route table"
  }
}

run "each_tier_only_accepts_the_one_in_front" {
  command = apply

  assert {
    condition     = aws_vpc_security_group_ingress_rule.alb_http.from_port == 80 && aws_vpc_security_group_ingress_rule.alb_http.cidr_ipv4 == "0.0.0.0/0"
    error_message = "ALB takes HTTP from the internet"
  }

  assert {
    condition = (aws_vpc_security_group_ingress_rule.app_from_alb.from_port == 8080
      && aws_vpc_security_group_ingress_rule.app_from_alb.referenced_security_group_id == aws_security_group.alb.id
    && aws_vpc_security_group_ingress_rule.app_from_alb.cidr_ipv4 == null)
    error_message = "app takes 8080 from the ALB security group only"
  }

  assert {
    condition = (aws_vpc_security_group_ingress_rule.ops_postgres_from_app.from_port == 5432
    && aws_vpc_security_group_ingress_rule.ops_postgres_from_app.referenced_security_group_id == aws_security_group.app.id)
    error_message = "ops takes Postgres from the app security group only"
  }

  assert {
    condition = alltrue([for r in [aws_vpc_security_group_ingress_rule.alb_http, aws_vpc_security_group_ingress_rule.app_from_alb,
    aws_vpc_security_group_ingress_rule.ops_postgres_from_app] : !(r.from_port <= 22 && r.to_port >= 22)])
    error_message = "no SSH: use SSM or EC2 Instance Connect"
  }
}

run "every_resource_is_tagged_and_prefixed" {
  command = apply

  variables {
    name_prefix = "nt548-dl"
    tags        = { owner = "dinhlong06" }
  }

  assert {
    condition = alltrue([for t in [aws_vpc.this.tags, aws_internet_gateway.this.tags, aws_subnet.public[0].tags,
      aws_route_table.public.tags, aws_security_group.alb.tags, aws_security_group.ops.tags,
    aws_vpc_security_group_ingress_rule.app_from_alb.tags] : t["project"] == "nt548" && t["owner"] == "dinhlong06"])
    error_message = "project = nt548 and the extra tags reach every resource"
  }

  assert {
    condition     = aws_security_group.app.name == "nt548-dl-app" && aws_vpc.this.tags["Name"] == "nt548-dl-vpc"
    error_message = "names start with name_prefix, so two labs never clash"
  }
}

run "one_az_is_rejected" {
  command = plan

  variables {
    azs = ["us-east-1a"]
  }

  expect_failures = [var.azs]
}
