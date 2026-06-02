@echo off
REM tools/run-termino.cmd
REM
REM One-click "run the daily termino workflow with the VPN handled
REM automatically".
REM
REM This is the entry point intended for the 5-10 non-IT users we want
REM to distribute the tool to. They:
REM   1. Double-click this file (or a Desktop shortcut pointing here).
REM   2. Approve the UAC prompt once.
REM   3. Watch the workflow run in the new window; auto_vpn brings the
REM      VPN up and back down automatically around the workflow.
REM
REM auto_vpn.enabled must be true in config.json (otherwise the script
REM still runs but the VPN-PRE-FLIGHT-WARNING tells the user to start
REM Cisco manually).

setlocal
set "PROJECT_ROOT=%~dp0.."

echo Spawning elevated python (UAC prompt incoming)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList 'main.py' -WorkingDirectory '%PROJECT_ROOT%' -Verb RunAs -Wait"

echo.
echo Workflow finished. Press any key to close.
pause >nul

endlocal
