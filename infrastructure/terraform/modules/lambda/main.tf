variable "function_name" { type = string }
variable "role_arn" { type = string }
variable "image_uri" { type = string }
variable "log_group_name" { type = string }
variable "environment_variables" {
  type    = map(string)
  default = {}
}
variable "command" {
  type    = list(string)
  default = null # null = use the image's CMD (handlers.lambda_api.handler)
}
variable "memory_size" {
  type    = number
  default = 1024
}
variable "timeout" {
  type    = number
  default = 30
}
variable "reserved_concurrent_executions" {
  type    = number
  default = -1 # -1 = unreserved. Set a small number to cap simultaneous DB connections.
}

resource "aws_lambda_function" "this" {
  function_name                  = var.function_name
  role                           = var.role_arn
  package_type                   = "Image"
  image_uri                      = var.image_uri
  memory_size                    = var.memory_size
  timeout                        = var.timeout
  reserved_concurrent_executions = var.reserved_concurrent_executions
  architectures                  = ["x86_64"]

  dynamic "image_config" {
    for_each = var.command == null ? [] : [1]
    content {
      command = var.command
    }
  }

  environment {
    variables = var.environment_variables
  }

  logging_config {
    log_format = "Text"
    log_group  = var.log_group_name
  }

  # OWNERSHIP: Terraform owns the function's configuration; the CI/CD pipeline owns the image version.
  # Without this, the next `terraform apply` would roll production back to the bootstrap image.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

output "function_name" { value = aws_lambda_function.this.function_name }
output "function_arn" { value = aws_lambda_function.this.arn }
output "invoke_arn" { value = aws_lambda_function.this.invoke_arn }
