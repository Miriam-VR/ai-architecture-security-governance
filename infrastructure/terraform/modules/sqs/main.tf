variable "name" { type = string }
variable "worker_timeout_seconds" {
  type    = number
  default = 30
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-actions-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "actions" {
  name                       = "${var.name}-actions"
  visibility_timeout_seconds = var.worker_timeout_seconds * 6 # AWS guidance for Lambda event sources
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}

output "queue_url" { value = aws_sqs_queue.actions.url }
output "queue_arn" { value = aws_sqs_queue.actions.arn }
output "queue_name" { value = aws_sqs_queue.actions.name }
output "dlq_name" { value = aws_sqs_queue.dlq.name }
