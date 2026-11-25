# Network (#23): one VPC, a public subnet in each of two AZs, an internet gateway, and the three security groups of
# the design (docs/plans/2026-11-20-nt548-devops-design.md §5). No NAT gateway: instances get a public IP and the
# security groups are the only way in. No SSH anywhere: machines are reached through SSM or EC2 Instance Connect.
#
#   internet --80--> alb --8080--> app --5432--> ops (Postgres container, self-hosted runner)

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  tags = merge(var.tags, { project = "nt548" })
}

resource "aws_vpc" "this" {
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_subnet" "public" {
  count = length(var.azs)

  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.azs[count.index]
  cidr_block              = cidrsubnet(var.cidr, 8, count.index) # /24 per AZ: 10.48.0.0/24, 10.48.1.0/24
  map_public_ip_on_launch = true                                 # no NAT: instances pull images over their own IP
  tags                    = merge(local.tags, { Name = "${var.name_prefix}-public-${var.azs[count.index]}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${var.name_prefix}-public" })
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count = length(var.azs)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ---------- security groups: each one only accepts the tier in front of it ----------

resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb"
  description = "ALB: HTTP from the internet"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.tags, { Name = "${var.name_prefix}-alb" })
}

resource "aws_security_group" "app" {
  name        = "${var.name_prefix}-app"
  description = "App instances: the app port from the ALB only"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.tags, { Name = "${var.name_prefix}-app" })
}

resource "aws_security_group" "ops" {
  name        = "${var.name_prefix}-ops"
  description = "Ops machine: Postgres from the app instances only"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.tags, { Name = "${var.name_prefix}-ops" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from the internet"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  security_group_id            = aws_security_group.app.id
  description                  = "App port from the ALB"
  ip_protocol                  = "tcp"
  from_port                    = var.app_port
  to_port                      = var.app_port
  referenced_security_group_id = aws_security_group.alb.id
  tags                         = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "ops_postgres_from_app" {
  security_group_id            = aws_security_group.ops.id
  description                  = "Postgres from the app instances"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = aws_security_group.app.id
  tags                         = local.tags
}

# Outbound is open on every tier: the ALB reaches its targets, app instances pull images from GHCR, the ops machine
# talks to GitHub (runner) and AWS APIs. There is no NAT to filter it anyway.
resource "aws_vpc_security_group_egress_rule" "all" {
  for_each = {
    alb = aws_security_group.alb.id
    app = aws_security_group.app.id
    ops = aws_security_group.ops.id
  }

  security_group_id = each.value
  description       = "All outbound"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  tags              = local.tags
}
