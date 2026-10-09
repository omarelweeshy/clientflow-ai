$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Assert-Command {
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
}
if (-not (Test-Path -LiteralPath '.env')) {
    python scripts/configure.py
    Assert-Command
}
docker compose up --build -d --wait --wait-timeout 180
Assert-Command
docker compose exec -T api python -m app.seed
Assert-Command
docker compose exec -T n8n n8n import:workflow --separate --input=/workflows
Assert-Command
foreach ($workflowId in @('clientflow01','clientflow02','clientflow03','clientflow04','clientflow05')) {
    docker compose exec -T n8n n8n publish:workflow "--id=$workflowId"
    Assert-Command
}
docker compose restart n8n
Assert-Command
Write-Host 'Demo ready: http://localhost:3010/login'
Write-Host 'Read your generated password from local-secrets/admin-password.txt.'
