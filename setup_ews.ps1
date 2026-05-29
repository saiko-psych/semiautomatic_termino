# setup_ews.ps1
# ==============
# Switches the Termino script to Uni-Graz EWS, resets the daily status
# so all tasks run again, ensures the Uni login password is in the
# Windows Credential Manager, and finally runs main.py.
#
# Usage:
#     .\setup_ews.ps1
#
# Re-runnable. Skips steps that are already done.

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir

Write-Host ""
Write-Host "================================================================"
Write-Host " Termino - switch to Uni-Graz EWS"
Write-Host "================================================================"
Write-Host ""

# --- 1) Sanity: where are we, which python ----------------------------
$python = (Get-Command python).Source
Write-Host "Project dir : $ProjectDir"
Write-Host "Python      : $python"
Write-Host ""

# --- 2) Check / set mail_provider in config.json ----------------------
$configPath = Join-Path $ProjectDir "config.json"
if (-not (Test-Path $configPath)) {
    Write-Host "ERROR: config.json not found at $configPath" -ForegroundColor Red
    exit 1
}
$cfg = Get-Content $configPath -Raw | ConvertFrom-Json
$currentProvider = $cfg.mail_provider.type
$currentUser     = $cfg.mail_provider.username

if ($currentProvider -ne "uni-graz-ews") {
    Write-Host "Updating config.json: mail_provider -> uni-graz-ews" -ForegroundColor Yellow
    if (-not $cfg.PSObject.Properties.Match("mail_provider").Count) {
        $cfg | Add-Member -NotePropertyName "mail_provider" -NotePropertyValue ([pscustomobject]@{})
    }
    $cfg.mail_provider = [pscustomobject]@{
        type     = "uni-graz-ews"
        username = "your-mail@your-uni.at"
    }
    $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $configPath -Encoding utf8
    Write-Host "  config.json updated."
} else {
    Write-Host "config.json: mail_provider is already 'uni-graz-ews' (user: $currentUser)"
}
Write-Host ""

# --- 3) Reset daily status so tasks rerun -----------------------------
$statusPath = Join-Path $ProjectDir "status.json"
if (Test-Path $statusPath) {
    $backupName = "status.json.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    Copy-Item $statusPath -Destination $backupName
    Remove-Item $statusPath
    Write-Host "status.json reset (backup: $backupName)"
} else {
    Write-Host "status.json was not present - nothing to reset"
}
Write-Host ""

# --- 4) Make sure Uni login password is in the keyring -----------------
# `secrets set` is idempotent: it shows "already set" and prompts only for
# missing values. Always running it is more reliable than trying to detect
# the state ourselves via a sub-process — Windows Credential Manager via
# python-keyring's ChainerBackend has odd edge cases there.
$mail = "your-mail@your-uni.at"
Write-Host "Ensuring Uni-Graz credentials are in the keyring (interactive)..."
Write-Host "(Press Enter on any prompt to keep an existing value.)"
Write-Host ""
& $python -m utils.secrets set --email $mail --vpn
Write-Host ""

# --- 5) Show keyring overview ------------------------------------------
& $python -m utils.secrets list
Write-Host ""

# --- 6) VPN check (informative only) ----------------------------------
Write-Host "Checking that Cisco VPN tunnel reaches webmail.uni-graz.at ..."
$webmailReachable = $false
try {
    $tcp = Test-NetConnection -ComputerName "webmail.uni-graz.at" -Port 443 `
                              -WarningAction SilentlyContinue
    $webmailReachable = $tcp.TcpTestSucceeded
} catch {
    $webmailReachable = $false
}
if ($webmailReachable) {
    Write-Host "  webmail.uni-graz.at:443  reachable" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  webmail.uni-graz.at:443  NOT reachable" -ForegroundColor Red
    Write-Host "  Connect Cisco AnyConnect to the Uni VPN, then re-run this script." -ForegroundColor Red
    Write-Host ""
    exit 1
}
Write-Host ""

# --- 7) Run main.py ----------------------------------------------------
Write-Host "================================================================"
Write-Host " Running main.py"
Write-Host "================================================================"
Write-Host ""
& $python main.py
$exit = $LASTEXITCODE
Write-Host ""
if ($exit -eq 0) {
    Write-Host "Done. main.py exited 0." -ForegroundColor Green
} else {
    Write-Host "main.py exited with code $exit" -ForegroundColor Red
}
exit $exit
