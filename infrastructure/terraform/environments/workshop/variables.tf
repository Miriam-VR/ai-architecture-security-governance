variable "project" {
  type    = string
  default = "maintenance-ai"
}
variable "environment" {
  type    = string
  default = "workshop"
}
variable "region" {
  type    = string
  default = "us-east-1"
}
variable "lambda_image_uri" {
  type        = string
  description = "BOOTSTRAP image only (<acct>.dkr.ecr.<region>.amazonaws.com/<repo>@sha256:...). After creation the CI/CD pipeline owns the version (ignore_changes)."
}
variable "enable_ec2" {
  type        = bool
  default     = true
  description = "Create the EC2 Docker host that serves /diagnose/extended. false = Lambda serves both routes."
}
variable "ec2_instance_type" {
  type    = string
  default = "t3.small"
}
variable "llm_mode" {
  type    = string
  default = "mock"
}
variable "embedding_mode" {
  type    = string
  default = "mock"
}
variable "store_mode" {
  type        = string
  default     = "supabase"
  description = "supabase (needs DATABASE_URL in the secret) or memory (stateless demo)"
}
variable "jwt_issuer" {
  type        = string
  default     = ""
  description = "e.g. https://<project-ref>.supabase.co/auth/v1"
}
variable "jwt_jwks_url" {
  type        = string
  default     = ""
  description = "e.g. https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json (empty = HS256 JWT_SECRET from the secret)"
}
variable "jwt_audience" {
  type    = string
  default = "authenticated"
}
variable "alarm_email" {
  type    = string
  default = ""
}
variable "api_reserved_concurrency" {
  type        = number
  default     = 5
  description = "Caps simultaneous Lambda containers => caps Supabase DB connections. -1 = unreserved."
}
variable "secret_recovery_window_days" {
  type    = number
  default = 0 # delete immediately on destroy so the workshop can be re-created with the same name
}
