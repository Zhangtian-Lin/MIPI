$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $repositoryRoot "infra\containers\compose.yaml"
$migrationDirectory = Join-Path $repositoryRoot "infra\database\migrations"

Set-Location $repositoryRoot

$migrationBootstrap = @"
SET client_min_messages TO warning;
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_migrations (filename)
SELECT '0001_initial.sql'
WHERE to_regclass('public.sources') IS NOT NULL
ON CONFLICT (filename) DO NOTHING;
"@

$migrationBootstrap | docker compose -f $composeFile exec -T postgres `
    psql -U mipi -d mipi -v ON_ERROR_STOP=1 -f - *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Could not initialize the database migration ledger."
}

$applied = @(
    docker compose -f $composeFile exec -T postgres `
        psql -U mipi -d mipi -tAc "SELECT filename FROM schema_migrations ORDER BY filename;"
)

foreach ($migration in Get-ChildItem -LiteralPath $migrationDirectory -File -Filter "*.sql" | Sort-Object Name) {
    if ($applied -contains $migration.Name) {
        Write-Output "Already applied: $($migration.Name)"
        continue
    }

    Write-Output "Applying migration: $($migration.Name)"
    Get-Content -Raw -LiteralPath $migration.FullName | docker compose -f $composeFile exec -T postgres `
        psql -U mipi -d mipi -v ON_ERROR_STOP=1 -f -
    if ($LASTEXITCODE -ne 0) {
        throw "Migration failed: $($migration.Name)"
    }

    $escapedName = $migration.Name.Replace("'", "''")
    docker compose -f $composeFile exec -T postgres psql -U mipi -d mipi -v ON_ERROR_STOP=1 `
        -c "INSERT INTO schema_migrations (filename) VALUES ('$escapedName') ON CONFLICT DO NOTHING;" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not record migration: $($migration.Name)"
    }
}

Write-Output "Database migrations are current."
