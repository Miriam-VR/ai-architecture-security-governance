variable "name" { type = string }
variable "stage_name" { type = string }
variable "lambda_invoke_arn" { type = string }
variable "lambda_function_name" { type = string }
variable "extended_backend_url" {
  type        = string
  default     = ""
  description = "http(s)://host:port of the EC2 service. Empty = /diagnose/extended is served by the Lambda too."
}
variable "throttle_rate" {
  type    = number
  default = 10
}
variable "throttle_burst" {
  type    = number
  default = 20
}
variable "quota_per_day" {
  type    = number
  default = 2000
}

resource "aws_api_gateway_rest_api" "this" {
  name                         = var.name
  description                  = "Maintenance AI API (REST API: supports API keys + usage plans)"
  disable_execute_api_endpoint = false

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# ---- explicit routes (API Gateway never guesses which queries are long) -----------------------------
resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_resource" "diagnose" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "diagnose"
}

resource "aws_api_gateway_resource" "quick" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.diagnose.id
  path_part   = "quick"
}

resource "aws_api_gateway_resource" "extended" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.diagnose.id
  path_part   = "extended"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "{proxy+}"
}

locals {
  use_ec2 = var.extended_backend_url != ""
  lambda_routes = {
    health   = { resource_id = aws_api_gateway_resource.health.id, http_method = "GET", key_required = false }
    diagnose = { resource_id = aws_api_gateway_resource.diagnose.id, http_method = "POST", key_required = true }
    quick    = { resource_id = aws_api_gateway_resource.quick.id, http_method = "POST", key_required = true }
    proxy    = { resource_id = aws_api_gateway_resource.proxy.id, http_method = "ANY", key_required = true }
  }
}

# JWT is validated INSIDE the app (identity + plant scope). The API key only identifies the client / usage plan.
resource "aws_api_gateway_method" "lambda" {
  for_each         = local.lambda_routes
  rest_api_id      = aws_api_gateway_rest_api.this.id
  resource_id      = each.value.resource_id
  http_method      = each.value.http_method
  authorization    = "NONE"
  api_key_required = each.value.key_required
}

resource "aws_api_gateway_integration" "lambda" {
  for_each                = local.lambda_routes
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.lambda[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

resource "aws_api_gateway_method" "extended" {
  rest_api_id      = aws_api_gateway_rest_api.this.id
  resource_id      = aws_api_gateway_resource.extended.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "extended_lambda" {
  count                   = local.use_ec2 ? 0 : 1
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.extended.id
  http_method             = aws_api_gateway_method.extended.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

resource "aws_api_gateway_integration" "extended_ec2" {
  count                   = local.use_ec2 ? 1 : 0
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.extended.id
  http_method             = aws_api_gateway_method.extended.http_method
  integration_http_method = "POST"
  type                    = "HTTP_PROXY"
  uri                     = "${var.extended_backend_url}/diagnose/extended"
  timeout_milliseconds    = 29000
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.this.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.health.id, aws_api_gateway_resource.diagnose.id, aws_api_gateway_resource.quick.id,
      aws_api_gateway_resource.extended.id, aws_api_gateway_resource.proxy.id,
      [for m in aws_api_gateway_method.lambda : m.id], aws_api_gateway_method.extended.id,
      [for i in aws_api_gateway_integration.lambda : i.id],
      [for i in aws_api_gateway_integration.extended_lambda : i.id],
      [for i in aws_api_gateway_integration.extended_ec2 : i.id],
      var.extended_backend_url,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [aws_api_gateway_integration.lambda, aws_api_gateway_integration.extended_lambda, aws_api_gateway_integration.extended_ec2]
}

resource "aws_api_gateway_stage" "this" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  deployment_id = aws_api_gateway_deployment.this.id
  stage_name    = var.stage_name
}

resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  stage_name  = aws_api_gateway_stage.this.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled        = true
    throttling_rate_limit  = var.throttle_rate
    throttling_burst_limit = var.throttle_burst
  }
}

# Usage plan only. The API KEY itself is created with the AWS CLI (SETUP.md) so its value never enters Terraform state.
resource "aws_api_gateway_usage_plan" "this" {
  name = "${var.name}-standard"

  api_stages {
    api_id = aws_api_gateway_rest_api.this.id
    stage  = aws_api_gateway_stage.this.stage_name
  }

  throttle_settings {
    rate_limit  = var.throttle_rate
    burst_limit = var.throttle_burst
  }

  quota_settings {
    limit  = var.quota_per_day
    period = "DAY"
  }
}

output "invoke_url" { value = aws_api_gateway_stage.this.invoke_url }
output "rest_api_id" { value = aws_api_gateway_rest_api.this.id }
output "usage_plan_id" { value = aws_api_gateway_usage_plan.this.id }
