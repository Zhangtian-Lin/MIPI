$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $repositoryRoot "infra\containers\compose.yaml"
$environmentFile = Join-Path $repositoryRoot ".env"
$environmentExample = Join-Path $repositoryRoot ".env.example"

Set-Location $repositoryRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install Docker Desktop, restart Windows if WSL was just enabled, and start Docker Desktop."
}

if (-not (Test-Path -LiteralPath $environmentFile)) {
    Copy-Item -LiteralPath $environmentExample -Destination $environmentFile
    Write-Output "Created .env from .env.example"
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but its Linux engine is not ready. Start Docker Desktop and retry."
}

docker compose -f $composeFile up -d --wait postgres redis minio
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose could not start the local infrastructure."
}

docker compose -f $composeFile run --rm minio-init
if ($LASTEXITCODE -ne 0) {
    throw "MinIO is running, but the local object-storage bucket could not be initialized."
}

docker compose -f $composeFile ps
Write-Output "MIPI local infrastructure is ready."
