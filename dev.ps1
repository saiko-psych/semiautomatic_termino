# dev.ps1 - One-stop dev workflow fuer termino_clean.
#
# Usage:
#   .\dev.ps1                  - status + diff + Tests (kein Commit)
#   .\dev.ps1 test             - nur Tests, verbose
#   .\dev.ps1 commit           - Tests, bei gruen committen mit NEXT_COMMIT.md
#   .\dev.ps1 commit "msg"     - Tests + commit mit gegebener Message
#   .\dev.ps1 rollback         - git reset --hard HEAD

param([string]$Action = "status", [string]$Message = "")

# WICHTIG: KEIN $ErrorActionPreference = "Stop" - unittest schreibt auf stderr
# und PowerShell macht daraus "NativeCommandError". Wir checken Exit-Codes
# explizit per $LASTEXITCODE.
Set-Location $PSScriptRoot

function Run-PythonTests {
    Write-Host ""
    Write-Host "===== TESTS =====" -ForegroundColor Cyan
    # Aus 2>&1 kommt das Zeug aus stderr+stdout. Wir leiten nach Out-String
    # um, damit PowerShell das nicht als "NativeCommandError" bewertet.
    # No -v: we only care about the final "Ran N tests" / "OK|FAIL" line.
    # The per-test verbose stream + the test bodies' print()s are noise.
    $output = & python -m unittest discover -s tests 2>&1 | Out-String
    $exit = $LASTEXITCODE
    # Extract the last 3 lines (Ran/OK/FAIL block) for a clean summary.
    $tail = ($output -split "`n" | Select-Object -Last 5) -join "`n"
    Write-Host $tail.Trim()
    if ($exit -ne 0) {
        Write-Host "[FAIL] unittest exit code = $exit" -ForegroundColor Red
        return $false
    }
    Write-Host "[OK] alle Tests gruen." -ForegroundColor Green
    return $true
}

function Show-Status {
    Write-Host ""
    Write-Host "===== GIT STATUS =====" -ForegroundColor Cyan
    & git status --short
    $changeCount = (& git status --porcelain | Measure-Object -Line).Lines
    if ($changeCount -eq 0) {
        Write-Host "  (keine Aenderungen)" -ForegroundColor Green
        return $false
    }
    Write-Host ""
    Write-Host "===== DIFF SUMMARY =====" -ForegroundColor Cyan
    & git diff --stat
    return $true
}

function Get-CommitMessage([string]$override) {
    if ($override) { return $override }
    if (Test-Path "NEXT_COMMIT.md") {
        $msg = (Get-Content "NEXT_COMMIT.md" -Raw).Trim()
        if ($msg) {
            Write-Host ""
            Write-Host "Commit-Message aus NEXT_COMMIT.md:" -ForegroundColor Yellow
            Write-Host "---"
            Write-Host $msg
            Write-Host "---"
            return $msg
        }
    }
    return ""
}

switch ($Action) {
    "status" {
        $hasChanges = Show-Status
        if ($hasChanges) {
            Run-PythonTests | Out-Null
            Write-Host ""
            Write-Host "Wenn alles passt:" -ForegroundColor Yellow
            Write-Host "  .\dev.ps1 commit"
        }
    }

    "test" {
        Run-PythonTests | Out-Null
    }

    "commit" {
        $hasChanges = Show-Status
        if (-not $hasChanges) { exit 0 }

        $testsOk = Run-PythonTests
        if (-not $testsOk) {
            Write-Host ""
            Write-Host "Tests sind rot - kein Commit. Erst fixen." -ForegroundColor Red
            exit 1
        }

        $msg = Get-CommitMessage $Message
        if (-not $msg) {
            $msg = Read-Host "`nCommit-Message (oder leer fuer Abbruch)"
            if (-not $msg) { Write-Host "Abgebrochen."; exit 0 }
        }

        Write-Host ""
        Write-Host "===== COMMIT =====" -ForegroundColor Cyan
        & git add -A
        # Use -F <file> instead of -m "<msg>" so PowerShell quoting/escaping
        # cannot mangle the commit message (no risk of quotes / colons being
        # interpreted as path arguments). The message file is the canonical
        # source of truth - what's in NEXT_COMMIT.md is exactly what lands
        # in the commit. If $override was passed, write it temporarily.
        $msgFile = "NEXT_COMMIT.md"
        $useTmp = $false
        if ($Message) {
            $msgFile = "NEXT_COMMIT.tmp"
            Set-Content -Path $msgFile -Value $Message -Encoding UTF8
            $useTmp = $true
        }
        & git commit -F $msgFile
        if ($useTmp) {
            Remove-Item $msgFile -ErrorAction SilentlyContinue
        }
        Write-Host ""
        Write-Host "[OK] committed:" -ForegroundColor Green
        & git log --oneline -1

        if (-not $useTmp -and (Test-Path "NEXT_COMMIT.md")) {
            "" | Set-Content "NEXT_COMMIT.md"
        }
    }

    "rollback" {
        Write-Host ""
        Write-Host "===== ROLLBACK =====" -ForegroundColor Cyan
        & git status --short
        $confirm = Read-Host "`nWirklich ALLE Aenderungen verwerfen? (j/N)"
        if ($confirm -match "^(j|y|ja|yes)") {
            & git reset --hard HEAD
            Write-Host "[OK] zurueckgesetzt." -ForegroundColor Green
        } else {
            Write-Host "Abgebrochen."
        }
    }

    default {
        Write-Host "Unbekannte Action: $Action"
        Write-Host "Verfuegbar: status (default), test, commit, rollback"
    }
}
