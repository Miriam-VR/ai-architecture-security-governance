variable "project" {
  type    = string
  default = "maintenance-ai"
}
variable "region" {
  type    = string
  default = "us-east-1"
}
variable "github_repo" {
  type        = string
  description = "GitHub repository allowed to assume the CI roles, as owner/name (e.g. richardyantas/ai-architecture-security-governance)"
}
variable "environments" {
  type        = list(string)
  default     = ["dev", "workshop"]
  description = "Environment names. Each gets GitHub Environments <env>-infra (terraform apply) and <env>-deploy (release)"
}
variable "create_github_oidc_provider" {
  type        = bool
  default     = true
  description = "Set false if the account already has the token.actions.githubusercontent.com OIDC provider (only one is allowed per account)"
}
