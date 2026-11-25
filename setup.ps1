# One-shot setup for Windows (copy entire project folder, then run: .\setup.ps1)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python --version | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Python 3.11+ required on PATH" }
python scripts/bootstrap_local.py
Write-Host ""
Write-Host "Next: edit .env (TELEGRAM_BOT_TOKEN, optional Apify/DLD tokens), then:"
Write-Host "  python -m bot.main"
Write-Host "  python -m cli resolve-owner `"<PF URL>`""
Write-Host "  python scripts/resolve_dld_phone.py `"<+9715...>`""