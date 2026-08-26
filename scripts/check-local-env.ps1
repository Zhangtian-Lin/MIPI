$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $repositoryRoot "infra\containers\compose.yaml"

Set-Location $repositoryRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker engine is not ready."
}

$containerIds = docker compose -f $composeFile ps --quiet
if ($LASTEXITCODE -ne 0 -or -not $containerIds) {
    throw "MIPI infrastructure containers are not running. Run 'pnpm infra:up' first."
}

$tableCount = docker compose -f $composeFile exec -T postgres psql -U mipi -d mipi -tAc "select count(*) from information_schema.tables where table_schema = 'public';"
if ($LASTEXITCODE -ne 0 -or [int]$tableCount -lt 21) {
    throw "PostgreSQL is reachable, but the MIPI schema is missing."
}

$migrationCount = docker compose -f $composeFile exec -T postgres psql -U mipi -d mipi -tAc "select count(*) from schema_migrations;"
if ($LASTEXITCODE -ne 0 -or [int]$migrationCount -lt 5) {
    throw "PostgreSQL is reachable, but one or more MIPI migrations are missing."
}

$redisResult = docker compose -f $composeFile exec -T redis redis-cli ping
if ($LASTEXITCODE -ne 0 -or $redisResult.Trim() -ne "PONG") {
    throw "Redis health check failed."
}

$minioResponse = Invoke-WebRequest -Uri "http://localhost:9000/minio/health/live" -UseBasicParsing
if ($minioResponse.StatusCode -ne 200) {
    throw "MinIO health check failed."
}

Write-Output "Docker engine: ready"
Write-Output "PostgreSQL schema tables: $($tableCount.Trim())"
Write-Output "Database migrations: $($migrationCount.Trim())"
Write-Output "Redis: PONG"
Write-Output "MinIO: healthy"
Write-Output "MIPI local environment check passed."
