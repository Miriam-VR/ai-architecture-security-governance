# Instalación y comandos en Windows

Esta guía es el equivalente para **Windows 10/11** de las secciones de instalación y de comandos del [README](../README.md). El resto (qué crea Terraform, orden de pasos, problemas conocidos) es igual en ambos sistemas y está en el README.

> ⚠️ **Esta guía no fue probada en Windows.** El proyecto se provisionó en Linux; aquí se traducen los comandos. Si algo falla, el README sigue siendo la referencia del flujo.

Usa **PowerShell** (no `cmd`). Abre una ventana nueva después de instalar cada herramienta para que se actualice el `PATH`.

## 1. Instalar las herramientas

Se puede con `winget` (viene con Windows 10/11), con Chocolatey, o descargando los instaladores. Elige una forma.

### Opción A · winget (recomendada)

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
winget install --id Amazon.AWSCLI -e
winget install --id Hashicorp.Terraform -e
winget install --id Docker.DockerDesktop -e
```

### Opción B · Chocolatey

Instala primero Chocolatey desde https://chocolatey.org/install y, en un PowerShell **como administrador**:

```powershell
choco install python312 git awscli terraform docker-desktop -y
```

### Opción C · Instaladores manuales

| Herramienta | Descarga |
|---|---|
| Python 3.12+ | https://www.python.org/downloads/ (marca **Add python.exe to PATH**) |
| Git | https://git-scm.com/download/win |
| AWS CLI v2 | https://awscli.amazonaws.com/AWSCLIV2.msi |
| Terraform | https://developer.hashicorp.com/terraform/install (zip: descomprime `terraform.exe` en una carpeta del `PATH`) |
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |

### Notas sobre Docker Desktop

- Necesita **WSL 2** (Windows Subsystem for Linux) o Hyper-V. El instalador te guía; puede pedir reiniciar.
- Abre Docker Desktop y espera a que indique que está ejecutándose **antes** de usar `docker`.

### Comprobar

```powershell
python --version      # >= 3.12
git --version
aws --version         # aws-cli/2.x
terraform version     # >= 1.10
docker --version
```

Si `terraform` o `aws` no se reconocen tras instalar, cierra y abre PowerShell. Si persiste, añade su carpeta al `PATH` desde *Configuración → Sistema → Acerca de → Configuración avanzada del sistema → Variables de entorno*.

## 2. Si PowerShell bloquea los scripts

La activación del entorno virtual puede fallar con *«la ejecución de scripts está deshabilitada»*. Permítelo solo para tu usuario:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 3. Ejecutar en local

En Windows el entorno virtual usa `.venv\Scripts\` en lugar de `.venv/bin/`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Con el entorno activado (`(.venv)` en el prompt), usa `python` directamente:

```powershell
python scripts\generate_dataset.py; python scripts\generate_eval_cases.py
python scripts\ingest.py
uvicorn app.api.main:app --reload
```

Para pasar variables **solo a un comando**, en PowerShell no existe la forma `VAR=valor comando` de Linux. Defínelas antes en la sesión:

```powershell
$env:DATABASE_URL = "postgresql://..."
python scripts\apply_migrations.py --seed
```

## 4. Cargar secretos sin dejarlos en el historial

El `read -s` de Linux se sustituye por `Read-Host -AsSecureString`, que no muestra lo que escribes. Como una variable de entorno necesita texto, hay que convertirlo:

```powershell
function Read-Secret($name, $prompt) {
    $s = Read-Host $prompt -AsSecureString
    $plain = [System.Net.NetworkCredential]::new("", $s).Password
    Set-Item -Path "Env:$name" -Value $plain
}

Read-Secret "SUPABASE_SERVICE_ROLE_KEY" "service role key"
Read-Secret "DEMO_PASSWORD" "demo password"
$env:SUPABASE_URL = "https://<ref>.supabase.co"
python scripts\create_demo_users.py
```

Comprueba que se cargó sin mostrarla:

```powershell
$env:SUPABASE_SERVICE_ROLE_KEY.Length
```

- La variable vive solo en esa ventana de PowerShell. Ejecuta el script en la misma.
- No escribas la clave directamente en el comando: quedaría en el historial (`Get-History` y el archivo de `PSReadLine`).
- `DEMO_PASSWORD` la inventas tú, igual que en Linux.

## 5. AWS

### Credenciales

```powershell
aws configure
aws sts get-caller-identity
```

Los valores son los mismos que en el README: llaves de acceso del usuario, región `us-east-1` y formato `json`. Las llaves se guardan en `%USERPROFILE%\.aws\credentials`.

> Al terminar `aws configure` puede ofrecerte configurar *skills* y un servidor MCP para agentes de IA. Es opcional y el proyecto no lo necesita.

### Bootstrap y entorno workshop

Los comandos de Terraform son idénticos; solo cambia cómo copias archivos y cómo te mueves:

```powershell
cd infrastructure\terraform\bootstrap
Copy-Item terraform.tfvars.example terraform.tfvars
# edita terraform.tfvars: github_repo = "<usuario>/<repo>"
aws iam list-open-id-connect-providers
terraform init
terraform plan
terraform apply
terraform output

cd ..\environments\workshop
Copy-Item backend.hcl.example backend.hcl
Copy-Item terraform.tfvars.example terraform.tfvars
# edita backend.hcl y terraform.tfvars (ver tabla del README, sección 5.4)
terraform init "-backend-config=backend.hcl"
```

En PowerShell conviene poner entre comillas `-backend-config=backend.hcl`, porque el punto y el signo `=` pueden interpretarse mal sin ellas.

Guarda los archivos `.tfvars` y `.hcl` con **codificación UTF-8 sin BOM**. Si usas el Bloc de notas antiguo, Terraform puede fallar al leerlos; VS Code los guarda bien.

### Imagen en ECR

Desde `environments\workshop`:

```powershell
terraform apply -target=module.ecr
```

Después, desde la **raíz del repositorio**:

```powershell
cd ..\..\..\..
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
$REGISTRY = "$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com"

aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $REGISTRY

docker build --provenance=false --sbom=false -f Dockerfile.lambda `
  -t "$REGISTRY/maintenance-ai-workshop:v1" .
docker push "$REGISTRY/maintenance-ai-workshop:v1"
```

- El acento grave `` ` `` al final de la línea es la continuación de línea de PowerShell (en Linux es `\`).
- `--provenance=false --sbom=false` es obligatorio, igual que en Linux (ver el README, problema 7.3).
- Copia el digest completo (`sha256:` y 64 caracteres) a `lambda_image_uri`, con tu número de cuenta, y sigue con `terraform plan` y `terraform apply`.

### Secretos en Secrets Manager

```powershell
.\.venv\Scripts\Activate.ps1
Read-Secret "OPENAI_API_KEY" "openai key (opcional)"
Read-Secret "DATABASE_URL" "database url (puerto 6543)"
Read-Secret "JWT_SECRET" "jwt secret"
python scripts\seed_app_secret.py --secret-id maintenance-ai/workshop/app --region us-east-1
```

(`Read-Secret` es la función de la sección 4; vuelve a definirla si abriste una ventana nueva.)

### Smoke test

```powershell
python scripts\smoke_test.py --base-url <API_URL> --api-key <KEY> `
  --secret-id maintenance-ai/workshop/app --route /diagnose/quick
```

Para obtener la API key:

```powershell
aws apigateway get-api-keys --include-values --query "items[].{name:name,value:value}" --output table
```

## 6. Problemas típicos en Windows

| Síntoma | Causa y solución |
|---|---|
| `aws` o `terraform` no se reconocen | No actualizaste el `PATH`: cierra y abre PowerShell. |
| `Activate.ps1 cannot be loaded ... running scripts is disabled` | Política de ejecución. Ver sección 2. |
| `docker: error during connect ... pipe/docker_engine` | Docker Desktop no está en marcha. Ábrelo y espera a que arranque. |
| `failed to read dockerfile: open Dockerfile.lambda` | Ejecutaste `docker build` fuera de la raíz del repo. |
| `terraform init` falla leyendo `backend.hcl` | El archivo tiene BOM o una codificación rara. Guárdalo en UTF-8 sin BOM. |
| Los saltos de línea rompen scripts `.sh` dentro de la imagen | Git convirtió `LF` en `CRLF`. Ejecuta `git config core.autocrlf input` y vuelve a clonar. |
| Las rutas con `/` o `\` fallan | PowerShell acepta ambas en la mayoría de comandos; si falla una, prueba la otra. |

El resto de errores (límite de concurrencia de Lambda, imagen rechazada, función *tainted*, etc.) son de AWS y se resuelven igual que en Linux: ver la sección 7 del [README](../README.md).

## 7. Alternativa: WSL 2

Si prefieres no traducir comandos, instala WSL con Ubuntu y sigue el [README](../README.md) tal cual:

```powershell
wsl --install -d Ubuntu
```

Dentro de Ubuntu, instala las herramientas con la sección 2 del README. Docker Desktop puede integrarse con WSL desde *Settings → Resources → WSL integration*.
