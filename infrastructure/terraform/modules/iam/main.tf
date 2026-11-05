variable "name" { type = string }
variable "secret_arn" { type = string }
variable "queue_arn" { type = string }
variable "ecr_repository_arn" { type = string }
variable "api_log_group_arn" { type = string }
variable "worker_log_group_arn" { type = string }
variable "ec2_log_group_arn" { type = string }
variable "enable_ec2" {
  type    = bool
  default = true
}

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# ---- API Lambda
resource "aws_iam_role" "api" {
  name               = "${var.name}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "api" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${var.api_log_group_arn}:*"]
  }
  statement {
    sid       = "ReadAppSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.secret_arn]
  }
  statement {
    sid       = "EnqueueApprovedActions"
    actions   = ["sqs:SendMessage"]
    resources = [var.queue_arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "least-privilege"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

# ---- Worker Lambda
resource "aws_iam_role" "worker" {
  name               = "${var.name}-worker"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${var.worker_log_group_arn}:*"]
  }
  statement {
    sid       = "ReadAppSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.secret_arn]
  }
  statement {
    sid       = "ConsumeQueue"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [var.queue_arn]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "least-privilege"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

# ---- EC2 instance
resource "aws_iam_role" "ec2" {
  count              = var.enable_ec2 ? 1 : 0
  name               = "${var.name}-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

data "aws_iam_policy_document" "ec2" {
  statement {
    sid       = "ReadAppSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.secret_arn]
  }
  statement {
    sid       = "EnqueueApprovedActions"
    actions   = ["sqs:SendMessage"]
    resources = [var.queue_arn]
  }
  statement {
    sid       = "PullImage"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [var.ecr_repository_arn]
  }
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # AWS does not support resource-level scoping for this single action
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${var.ec2_log_group_arn}:*"]
  }
}

resource "aws_iam_role_policy" "ec2" {
  count  = var.enable_ec2 ? 1 : 0
  name   = "least-privilege"
  role   = aws_iam_role.ec2[0].id
  policy = data.aws_iam_policy_document.ec2.json
}

# SSM lets GitHub Actions deploy to the instance WITHOUT opening SSH
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  count      = var.enable_ec2 ? 1 : 0
  role       = aws_iam_role.ec2[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2" {
  count = var.enable_ec2 ? 1 : 0
  name  = "${var.name}-ec2"
  role  = aws_iam_role.ec2[0].name
}

output "api_role_arn" { value = aws_iam_role.api.arn }
output "worker_role_arn" { value = aws_iam_role.worker.arn }
output "ec2_instance_profile_name" { value = var.enable_ec2 ? aws_iam_instance_profile.ec2[0].name : "" }
