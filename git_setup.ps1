# git_setup.ps1 - Einmaliges Git-Setup fuer termino_clean
#
# Warum dieses Skript: Die Claude-Sandbox kann auf dem virtiofs/FUSE-Mount
# keine .git-Files zuverlaessig schreiben/loeschen. Daher muss git init
# nativ von Windows-PowerShell laufen, nicht aus dem Sandbox-Bash.
#
# Ausfuehrung:  cd in den Projektordner, dann:  .\git_setup.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1) Korruptes .git/ von vorherigem Sandbox-Versuch entfernen (falls da)
if (Test-Path ".git") {
    Write-Host "[INFO] Loesche vorhandenes .git/ (vom Sandbox-Init beschaedigt)..."
    Remove-Item -Recurse -Force .git
}

# 2) Frisch initialisieren
Write-Host "[1/4] git init -b main ..."
git init -b main | Out-Null

# 3) Identity setzen (lokal, nur fuer dieses Repo)
Write-Host "[2/4] User-Identity setzen ..."
git config user.email "your-mail@your-uni.at"
git config user.name "Your Name"

# 4) Erster Commit mit dem aktuellen Stand
Write-Host "[3/4] alles staging ..."
git add .

Write-Host "[4/4] initial commit ..."
git commit -m "Initial commit - termino_clean nach EWS/uniCLOUD/Kalender-Refactor + 90 Unit-Tests" | Out-Null

Write-Host ""
Write-Host "[OK] Repository initialisiert." -ForegroundColor Green
Write-Host ""
Write-Host "Aktueller Stand:"
git log --oneline -n 5
Write-Host ""
Write-Host "Tipp: Vor jeder Aenderung am Code: git status / git diff"
Write-Host "      Nach jedem stabilen Stand:   git add -A; git commit -m 'beschreibung'"
Write-Host "      Wenn was kaputt geht:        git reset --hard HEAD"
