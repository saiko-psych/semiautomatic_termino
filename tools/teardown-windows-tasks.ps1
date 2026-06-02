# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    Remove the Scheduled Tasks + shortcuts that setup-windows-tasks.ps1
    created. Doesn't touch openconnect-gui, openconnect-sso, or any
    config / keyring entries - just the Tier-2 Part B convenience layer.

.NOTES
    Requires Administrator (to unregister Scheduled Tasks).
#>

[CmdletBinding()]
param()

function Test-IsAdmin {
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "ERROR: This script must run as Administrator." -ForegroundColor Red
    exit 1
}

$tasks = @(
    @{ Name = "TerminoVPN-Up";   ShortcutName = "Uni-VPN Up" },
    @{ Name = "TerminoVPN-Down"; ShortcutName = "Uni-VPN Down" },
    @{ Name = "TerminoRun";      ShortcutName = "Termino starten" }
)

Write-Host ""
Write-Host "=== Termino Windows Task Teardown ===" -ForegroundColor Cyan
Write-Host ""

# 1. Remove Scheduled Tasks
foreach ($t in $tasks) {
    $existing = Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false
        Write-Host "[task] removed: $($t.Name)" -ForegroundColor Yellow
    } else {
        Write-Host "[task] not present: $($t.Name)"
    }
}

# 2. Remove shortcuts
$desktop  = [Environment]::GetFolderPath('Desktop')
$startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) "Termino"

foreach ($t in $tasks) {
    $shortcutName = "$($t.ShortcutName).lnk"

    $d = Join-Path $desktop $shortcutName
    if (Test-Path $d) {
        Remove-Item $d -Force
        Write-Host "[shortcut] removed: Desktop\$shortcutName" -ForegroundColor Yellow
    }

    $s = Join-Path $startMenu $shortcutName
    if (Test-Path $s) {
        Remove-Item $s -Force
        Write-Host "[shortcut] removed: Start Menu\Termino\$shortcutName" -ForegroundColor Yellow
    }
}

# 3. Remove Start Menu folder if empty
if ((Test-Path $startMenu) -and -not (Get-ChildItem $startMenu -Force)) {
    Remove-Item $startMenu -Force
    Write-Host "[folder] removed empty Start Menu\Termino" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Teardown complete ===" -ForegroundColor Cyan
Write-Host ""
