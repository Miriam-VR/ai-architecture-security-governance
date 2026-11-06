data "aws_caller_identity" "current" {}

locals {
  name         = "${var.project}-${var.environment}"
  ecr_registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"

  # NON-secret runtime configuration. Secrets (OPENAI_API_KEY, DATABASE_URL, JWT_SECRET, MCP_SHARED_SECRET) are read
  # from Secrets Manager by the app at runtime.
  app_config = {
    LLM_MODE       = var.llm_mode
    EMBEDDING_MODE = var.embedding_mode
    STORE_MODE     = var.store_mode
    JWT_ISSUER     = var.jwt_issuer
    JWT_JWKS_URL   = var.jwt_jwks_url
    JWT_AUDIENCE   = var.jwt_audience
    DB_POOL_MAX    = "1"
    LOG_LEVEL      = "INFO"
  }
}

module "ecr" {
  source = "../../modules/ecr"
  name   = local.name
}

module "secrets" {
  source                  = "../../modules/secrets"
  name                    = "${var.project}/${var.environment}/app"
  recovery_window_in_days = var.secret_recovery_window_days
}

module "sqs" {
  source                 = "../../modules/sqs"
  name                   = local.name
  worker_timeout_seconds = 30
}

module "observability" {
  source               = "../../modules/observability"
  name                 = local.name
  environment          = var.environment
  alarm_email          = var.alarm_email
  api_function_name    = "${local.name}-api"
  worker_function_name = "${local.name}-worker"
  dlq_name             = module.sqs.dlq_name
}

module "iam" {
  source               = "../../modules/iam"
  name                 = local.name
  secret_arn           = module.secrets.secret_arn
  queue_arn            = module.sqs.queue_arn
  ecr_repository_arn   = module.ecr.repository_arn
  api_log_group_arn    = module.observability.api_log_group_arn
  worker_log_group_arn = module.observability.worker_log_group_arn
  ec2_log_group_arn    = module.observability.ec2_log_group_arn
  enable_ec2           = var.enable_ec2
}

module "lambda_api" {
  source                         = "../../modules/lambda"
  function_name                  = "${local.name}-api"
  role_arn                       = module.iam.api_role_arn
  image_uri                      = var.lambda_image_uri
  log_group_name                 = module.observability.api_log_group
  memory_size                    = 1024
  timeout                        = 29 # API Gateway REST integration limit
  reserved_concurrent_executions = var.api_reserved_concurrency
  environment_variables = merge(local.app_config, {
    APP_ENV           = var.environment
    SECRETS_BACKEND   = "aws"
    APP_SECRET_ID     = module.secrets.secret_name
    ACTION_QUEUE_MODE = "sqs"
    ACTION_QUEUE_URL  = module.sqs.queue_url
  })
}

module "lambda_worker" {
  source                         = "../../modules/lambda"
  function_name                  = "${local.name}-worker"
  role_arn                       = module.iam.worker_role_arn
  image_uri                      = var.lambda_image_uri
  log_group_name                 = module.observability.worker_log_group
  command                        = ["handlers.lambda_worker.handler"]
  memory_size                    = 512
  timeout                        = 30
  reserved_concurrent_executions = var.worker_reserved_concurrency
  environment_variables = merge(local.app_config, {
    APP_ENV           = var.environment
    SECRETS_BACKEND   = "aws"
    APP_SECRET_ID     = module.secrets.secret_name
    ACTION_QUEUE_MODE = "sqs"
    ACTION_QUEUE_URL  = module.sqs.queue_url
  })
}

resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn        = module.sqs.queue_arn
  function_name           = module.lambda_worker.function_arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
}

# The worker's role needs sqs:Receive/Delete (granted in modules/iam). The mapping above uses the worker role.

module "ec2" {
  count                 = var.enable_ec2 ? 1 : 0
  source                = "../../modules/ec2"
  name                  = local.name
  environment           = var.environment
  instance_type         = var.ec2_instance_type
  instance_profile_name = module.iam.ec2_instance_profile_name
  app_secret_id         = module.secrets.secret_name
  queue_url             = module.sqs.queue_url
  ecr_registry          = local.ecr_registry
  log_group_name        = module.observability.ec2_log_group
  region                = var.region
  app_env_vars          = local.app_config
}

module "api_gateway" {
  source               = "../../modules/api_gateway"
  name                 = local.name
  stage_name           = var.environment
  lambda_invoke_arn    = module.lambda_api.invoke_arn
  lambda_function_name = module.lambda_api.function_name
  extended_backend_url = var.enable_ec2 ? module.ec2[0].backend_url : ""
}
