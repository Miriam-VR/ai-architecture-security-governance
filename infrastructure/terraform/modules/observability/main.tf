variable "name" { type = string }
variable "environment" { type = string }
variable "retention_days" {
  type    = number
  default = 30
}
variable "alarm_email" {
  type    = string
  default = ""
}
variable "api_function_name" { type = string }
variable "worker_function_name" { type = string }
variable "dlq_name" { type = string }

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.name}-api"
  retention_in_days = var.retention_days
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${var.name}-worker"
  retention_in_days = var.retention_days
}

resource "aws_cloudwatch_log_group" "ec2" {
  name              = "/maintenance-ai/${var.environment}/ec2"
  retention_in_days = var.retention_days
}

resource "aws_sns_topic" "alarms" {
  name = "${var.name}-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${var.name}-api-errors"
  alarm_description   = "Lambda API reported errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = var.api_function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "${var.name}-api-latency-p95"
  alarm_description   = "Lambda API p95 duration above 20s"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  dimensions          = { FunctionName = var.api_function_name }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = 20000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "worker_errors" {
  alarm_name          = "${var.name}-worker-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = var.worker_function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${var.name}-actions-dlq-not-empty"
  alarm_description   = "An approved action failed 3 times and landed in the DLQ - needs a human"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = var.dlq_name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

output "api_log_group" { value = aws_cloudwatch_log_group.api.name }
output "worker_log_group" { value = aws_cloudwatch_log_group.worker.name }
output "ec2_log_group" { value = aws_cloudwatch_log_group.ec2.name }
output "api_log_group_arn" { value = aws_cloudwatch_log_group.api.arn }
output "worker_log_group_arn" { value = aws_cloudwatch_log_group.worker.arn }
output "ec2_log_group_arn" { value = aws_cloudwatch_log_group.ec2.arn }
output "alarm_topic_arn" { value = aws_sns_topic.alarms.arn }
