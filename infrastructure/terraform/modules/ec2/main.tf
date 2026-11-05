variable "name" { type = string }
variable "environment" { type = string }
variable "instance_type" {
  type    = string
  default = "t3.small"
}
variable "instance_profile_name" { type = string }
variable "app_secret_id" { type = string }
variable "queue_url" { type = string }
variable "ecr_registry" { type = string } # <account>.dkr.ecr.<region>.amazonaws.com
variable "log_group_name" { type = string }
variable "region" { type = string }
variable "app_env_vars" {
  type        = map(string)
  default     = {}
  description = "NON-secret configuration passed to the container (secrets come from Secrets Manager at runtime)"
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# NOTE: API Gateway (REST, regional) has no fixed source IPs, so the port is open to the internet.
# Every request is still JWT-authenticated by the app. Traffic API GW -> EC2 is plain HTTP: for production put
# an ALB with TLS (or a VPC link + private NLB) in front. See SETUP.md "Known limitations".
resource "aws_security_group" "app" {
  name_prefix = "${var.name}-ec2-"
  description = "Maintenance AI app (no SSH; deploys go through SSM)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "App port"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Outbound (ECR, Secrets Manager, Supabase, OpenAI)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

locals {
  env_file = join("\n", concat(
    ["APP_ENV=${var.environment}", "SECRETS_BACKEND=aws", "APP_SECRET_ID=${var.app_secret_id}", "ACTION_QUEUE_MODE=sqs", "ACTION_QUEUE_URL=${var.queue_url}", "AWS_REGION=${var.region}"],
    [for k, v in var.app_env_vars : "${k}=${v}"]
  ))
}

resource "aws_instance" "app" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnets.default.ids[0]
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = var.instance_profile_name
  associate_public_ip_address = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # lets the container reach the instance role
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euo pipefail
    dnf install -y docker
    systemctl enable --now docker
    install -d -m 0755 /etc/maintenance-ai
    cat > /etc/maintenance-ai/app.env <<'ENVEOF'
    ${local.env_file}
    ENVEOF
    chmod 0640 /etc/maintenance-ai/app.env

    # Deploy (and roll back) by IMMUTABLE image digest. Called by GitHub Actions through SSM.
    cat > /usr/local/bin/deploy-app.sh <<'DEPLOYEOF'
    #!/bin/bash
    set -uo pipefail
    IMAGE="$1"                                   # <registry>/<repo>@sha256:...
    REGISTRY="${var.ecr_registry}"
    STATE=/etc/maintenance-ai/current-image
    PREVIOUS="$(cat "$STATE" 2>/dev/null || true)"
    aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin "$REGISTRY" || exit 1
    docker pull "$IMAGE" || exit 1
    docker rm -f maint-app 2>/dev/null || true
    run() { docker run -d --name maint-app --restart unless-stopped -p 8000:8000 --env-file /etc/maintenance-ai/app.env \
              --log-driver awslogs --log-opt awslogs-region=${var.region} --log-opt awslogs-group=${var.log_group_name} --log-opt awslogs-create-group=false "$1"; }
    run "$IMAGE" || true
    for i in $(seq 1 20); do
      if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then echo "$IMAGE" > "$STATE"; echo "deployed $IMAGE"; exit 0; fi
      sleep 3
    done
    echo "health check failed for $IMAGE" >&2
    docker rm -f maint-app 2>/dev/null || true
    if [ -n "$PREVIOUS" ]; then echo "rolling back to $PREVIOUS" >&2; docker pull "$PREVIOUS" && run "$PREVIOUS"; fi
    exit 1
    DEPLOYEOF
    chmod 0755 /usr/local/bin/deploy-app.sh
  EOT

  tags = {
    Name       = "${var.name}-app"
    Deployment = var.name # SSM SendCommand from GitHub Actions is scoped to this tag
  }

  lifecycle {
    ignore_changes = [ami] # do not replace the host when a newer AMI is published
  }
}

output "instance_id" { value = aws_instance.app.id }
output "public_dns" { value = aws_instance.app.public_dns }
output "backend_url" { value = "http://${aws_instance.app.public_dns}:8000" }
