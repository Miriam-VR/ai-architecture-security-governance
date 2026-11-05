variable "name" { type = string } # e.g. maintenance-ai/dev/app
variable "recovery_window_in_days" {
  type    = number
  default = 7
}

# Terraform creates only the secret CONTAINER. The value (OPENAI_API_KEY, DATABASE_URL, JWT_SECRET,
# MCP_SHARED_SECRET) is written out-of-band with scripts/seed_app_secret.py, so it never enters Terraform state.
resource "aws_secretsmanager_secret" "app" {
  name                    = var.name
  description             = "Runtime secrets for the maintenance AI app (value managed outside Terraform)"
  recovery_window_in_days = var.recovery_window_in_days
}

output "secret_arn" { value = aws_secretsmanager_secret.app.arn }
output "secret_name" { value = aws_secretsmanager_secret.app.name }
