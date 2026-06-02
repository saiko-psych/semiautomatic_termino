# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    One-time Tier-2 setup: register Scheduled Tasks and create shortcuts
    so the daily user never sees a UAC prompt again.

.DESCRIPTION
    Tier 2 Part B for the Windows VPN integration. Run this once as
    Administrator and three Scheduled Tasks get registered with
    "Run with highest privileges". From then on, double-clicking the
    desktop shortcuts (or invoking `schtasks /run`) launches each task
    silently elevated — no UAC prompt.

    Three tasks get created:

      TerminoVPN-Up    -> python -m utils.auto_vpn_win up
      TerminoVPN-Down  -> python -m utils.auto_vpn_win down
      TerminoRun       -> python main.py

    Each task is configured as:
      - "Run only when user is logged on" (so the console is visible)
      - "Run with highest privileges" (so Wintun adapter creation works)
      - Triggered "On demand" only (no automatic schedule).

    For each task we also drop a .lnk shortcut on the Desktop AND in a
    Start Menu folder "Termino". The shortcut runs:

      cmd.exe /c "schtasks /run /tn <TaskName>"

    which fires the task without UAC.

.PARAMETER ProjectRoot
    Path to the termino_clean checkout. Defaults to the parent of this
    script's folder (so leaving it in tools\ works without arguments).

.PARAMETER PythonExe
    Path to python.exe. Defaults to whatever `python` resolves to in the
    current PATH.

.PARAMETER NoDesktop
    Don't create Desktop shortcuts. Start Menu shortcuts are still created.

.PARAMETER NoStartMenu
    Don't create Start Menu shortcuts. Desktop shortcuts are still created.

.NOTES
    Requires Administrator. Re-running the script is safe: existing
    tasks/shortcuts get updated, not duplicated. Use teardown-windows-tasks.ps1
    to remove everything.

    Verified on 2026-06-02 against the Tier-1 auto_vpn_win module.
#>

[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [string]$PythonExe,
    [switch]$NoDesktop,
    [switch]$NoStartMenu
)

# ---------- Pre-flight ---------------------------------------------------

function Test-IsAdmin {
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    Write-Host "ERROR: This script must run as Administrator." -ForegroundColor Red
    Write-Host "  Right-click 'setup-windows-tasks.ps1' -> 'Run with PowerShell as Administrator'"
    Write-Host "  Or open an Admin PowerShell and re-run:"
    Write-Host "    powershell -ExecutionPolicy Bypass -File .\tools\setup-windows-tasks.ps1"
    exit 1
}

# Resolve paths
if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
}
$ProjectRoot = $ProjectRoot.TrimEnd('\')

if (-not (Test-Path "$ProjectRoot\main.py")) {
    Write-Host "ERROR: main.py not found at $ProjectRoot\main.py" -ForegroundColor Red
    Write-Host "  Pass -ProjectRoot <path-to-termino_clean> if running from elsewhere."
    exit 1
}

if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) {
        Write-Host "ERROR: python not found in PATH and -PythonExe not given." -ForegroundColor Red
        exit 1
    }
    $PythonExe = $cmd.Source
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: python at $PythonExe does not exist." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Termino Windows Task Setup ===" -ForegroundColor Cyan
Write-Host "ProjectRoot : $ProjectRoot"
Write-Host "PythonExe   : $PythonExe"
Write-Host ""


# ---------- Task definitions --------------------------------------------

$tasks = @(
    @{
        Name        = "TerminoVPN-Up"
        Description = "Bring the Uni-Graz VPN up (auto_vpn_win)."
        Args        = "-m utils.auto_vpn_win up"
        ShortcutName = "Uni-VPN Up"
    },
    @{
        Name        = "TerminoVPN-Down"
        Description = "Tear down the Uni-Graz VPN and restart Cisco / Mullvad services."
        Args        = "-m utils.auto_vpn_win down"
        ShortcutName = "Uni-VPN Down"
    },
    @{
        Name        = "TerminoRun"
        Description = "Run the daily Termino workflow (auto_vpn handles VPN around it)."
        Args        = "main.py"
        ShortcutName = "Termino starten"
    }
)


# ---------- Register tasks ----------------------------------------------

foreach ($t in $tasks) {
    $taskName = $t.Name
    Write-Host "[$taskName] Registering Scheduled Task ..." -ForegroundColor Yellow

    # Remove any existing task with this name (re-running the setup is safe)
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "  removed existing task"
    }

    # Build the action. cmd.exe /c keeps the console visible after python
    # exits, so the user sees error messages instead of a window flashing.
    $cmdLine = "/c `"`"$PythonExe`" $($t.Args) & pause`""
    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument $cmdLine `
        -WorkingDirectory $ProjectRoot

    # Run only when the current user is logged on; highest privileges.
    $principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Highest

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 24)

    # No trigger - on-demand only.
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Description $t.Description `
        -Force | Out-Null

    Write-Host "  OK" -ForegroundColor Green
}


# ---------- Shortcut helper ---------------------------------------------

function New-TaskShortcut {
    param(
        [string]$ShortcutPath,
        [string]$TaskName,
        [string]$Description
    )

    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($ShortcutPath)
    # We invoke schtasks via cmd.exe /c so the prompt closes immediately
    # after firing the task. The actual elevated console comes from the
    # task itself.
    $sc.TargetPath = "$env:WINDIR\System32\cmd.exe"
    $sc.Arguments = "/c schtasks /run /tn `"$TaskName`""
    $sc.WorkingDirectory = $env:WINDIR
    $sc.Description = $Description
    # Inherit icon from cmd.exe; users can change it manually if they
    # prefer something fancier.
    $sc.WindowStyle = 7   # minimized (the launching cmd flashes briefly,
                          # the elevated console is what the user sees)
    $sc.Save()
}


# ---------- Create shortcuts -------------------------------------------

$desktop  = [Environment]::GetFolderPath('Desktop')
$startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) "Termino"

if (-not $NoStartMenu) {
    if (-not (Test-Path $startMenu)) {
        New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
    }
}

foreach ($t in $tasks) {
    $shortcutName = "$($t.ShortcutName).lnk"

    if (-not $NoDesktop) {
        $p = Join-Path $desktop $shortcutName
        New-TaskShortcut -ShortcutPath $p -TaskName $t.Name -Description $t.Description
        Write-Host "[shortcut] Desktop\$shortcutName" -ForegroundColor Green
    }
    if (-not $NoStartMenu) {
        $p = Join-Path $startMenu $shortcutName
        New-TaskShortcut -ShortcutPath $p -TaskName $t.Name -Description $t.Description
        Write-Host "[shortcut] Start Menu\Termino\$shortcutName" -ForegroundColor Green
    }
}


# ---------- Done --------------------------------------------------------

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Try it: double-click 'Uni-VPN Up' on your Desktop." -ForegroundColor White
Write-Host "       A black console window opens, runs auto_vpn_win up,"
Write-Host "       no UAC prompt this time."
Write-Host ""
Write-Host "To verify the tasks were created:"
Write-Host "  schtasks /query /tn TerminoVPN-Up /v /fo list | findstr 'TaskName Status'"
Write-Host ""
Write-Host "To remove everything: powershell -ExecutionPolicy Bypass -File .\tools\teardown-windows-tasks.ps1"
Write-Host ""
