# Create GitHub repo and push (requires: gh auth login OR $env:GH_TOKEN)
$ErrorActionPreference = "Stop"
$Gh = "C:\Program Files\GitHub CLI\gh.exe"
if (-not (Test-Path $Gh)) { $Gh = "gh" }

$RepoName = "dubai-realty-telegram-bot"
$Visibility = "public"

Set-Location (Join-Path $PSScriptRoot "..")

& $Gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub CLI is not signed in. Run in a terminal:`n  & '$Gh' auth login -h github.com -p https -w`nOr set GH_TOKEN to a classic PAT with repo scope, then re-run this script."
    exit 1
}

$existing = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Remote origin already set: $existing"
    git push -u origin main
    exit $LASTEXITCODE
}

& $Gh repo create $RepoName --$Visibility --source=. --remote=origin --push --description "Dubai realty Telegram bot: PF/Bayut lookup, Trakheesi, owner resolve"
$login = & $Gh api user -q .login 2>$null
if (-not $login) { $login = "emeraluna" }
Write-Host "Done: https://github.com/$login/$RepoName"