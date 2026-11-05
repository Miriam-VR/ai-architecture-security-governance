# Políticas IAM mínimas (V08)

Principio: **cada rol solo puede hacer lo que su código necesita**, sobre **recursos concretos** (ARN), nunca acciones comodín.
Los valores `ACCOUNT`, `REGION`, `ENV` se sustituyen por Terraform (`infrastructure/terraform/modules/iam`).

> Recordatorio: IAM protege recursos **de AWS**. No protege las filas de Supabase; eso lo hacen RLS + las comprobaciones del backend.

## 1. Rol de la Lambda API (`maintenance-ai-ENV-api`)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "Logs", "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:REGION:ACCOUNT:log-group:/aws/lambda/maintenance-ai-ENV-api:*" },
    { "Sid": "ReadAppSecret", "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:maintenance-ai/ENV/app-*" },
    { "Sid": "EnqueueApprovedActions", "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT:maintenance-ai-ENV-actions" }
  ]
}
```

## 2. Rol de la Lambda worker de acciones (`maintenance-ai-ENV-worker`)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "Logs", "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:REGION:ACCOUNT:log-group:/aws/lambda/maintenance-ai-ENV-worker:*" },
    { "Sid": "ReadAppSecret", "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:maintenance-ai/ENV/app-*" },
    { "Sid": "ConsumeQueue", "Effect": "Allow",
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT:maintenance-ai-ENV-actions" }
  ]
}
```

## 3. Rol de la instancia EC2 (`maintenance-ai-ENV-ec2`)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ReadAppSecret", "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:maintenance-ai/ENV/app-*" },
    { "Sid": "EnqueueApprovedActions", "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT:maintenance-ai-ENV-actions" },
    { "Sid": "PullImage", "Effect": "Allow",
      "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
      "Resource": "arn:aws:ecr:REGION:ACCOUNT:repository/maintenance-ai-ENV" },
    { "Sid": "EcrLogin", "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken"],
      "Resource": "*" },
    { "Sid": "Logs", "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:REGION:ACCOUNT:log-group:/maintenance-ai/ENV/ec2:*" }
  ]
}
```

Además se adjunta la política gestionada `AmazonSSMManagedInstanceCore` para que GitHub Actions despliegue vía SSM **sin abrir SSH**.

**Única excepción a "Resource concreto":** `ecr:GetAuthorizationToken` solo admite `"Resource": "*"` (limitación de AWS). Por eso `EcrLogin` es una sentencia separada y solo contiene esa acción.

## 4. Lo que NO tienen estos roles

| No pueden | Por qué |
|---|---|
| Leer otros secretos | El ARN del secreto está fijado (`maintenance-ai/ENV/app-*`). |
| Crear/modificar IAM, Lambdas o infraestructura | Eso lo hace Terraform con el rol de despliegue, no el runtime. |
| Leer/escribir S3 | La app no usa S3. |
| Borrar mensajes de la cola (API/EC2) | Solo el worker consume. |

## 5. Rol de GitHub Actions (OIDC)

Sin access keys. Dos roles con confianza limitada al repositorio y a ramas/entornos concretos (ver `SETUP.md` §5):
`maintenance-ai-gha-plan` (solo lectura + estado) y `maintenance-ai-gha-deploy` (actualizar Lambda, push a ECR, SSM SendCommand, leer el secreto para el smoke test).
