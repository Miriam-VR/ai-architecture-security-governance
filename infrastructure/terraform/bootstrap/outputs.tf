output "state_bucket" { value = aws_s3_bucket.state.bucket }
output "plan_role_arn" { value = aws_iam_role.plan.arn }
output "apply_role_arn" { value = aws_iam_role.apply.arn }
output "build_role_arn" { value = aws_iam_role.build.arn }
output "deploy_role_arn" { value = aws_iam_role.deploy.arn }
output "account_id" { value = local.account_id }
output "next_steps" {
  value = <<-EOT
    1. Put these in GitHub (Settings > Secrets and variables > Actions > Variables): AWS_REGION, AWS_ACCOUNT_ID=${local.account_id},
       TF_STATE_BUCKET=${aws_s3_bucket.state.bucket}
    2. cd ../environments/<env> && cp backend.hcl.example backend.hcl (set bucket=${aws_s3_bucket.state.bucket}) && terraform init -backend-config=backend.hcl
  EOT
}
