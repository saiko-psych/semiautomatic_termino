@echo off
REM tools/vpn-up.cmd
REM
REM One-click "bring the Uni-Graz VPN up" wrapper.
REM
REM Double-click this file from Explorer or run from CMD/PowerShell.
REM Windows shows a UAC prompt - openconnect.exe needs Administrator
REM to create the Wintun network adapter (Windows-Kernel-Policy).
REM
REM The actual work is done by `python -m utils.auto_vpn_win up`,
REM the same auto_vpn_session_win() context that main.py uses, just
REM without the Termino workflow attached. The elevated python
REM process runs in its own console window. Close it (or press
REM Strg-C in it) to tear down the tunnel.

setlocal
set "PROJECT_ROOT=%~dp0.."

echo Spawning elevated python (UAC prompt incoming)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '-m','utils.auto_vpn_win','up' -WorkingDirectory '%PROJECT_ROOT%' -Verb RunAs -Wait"

echo.
echo This launcher window is done. The tunnel ran in the other window.
echo Press any key to close this window.
pause >nul

endlocal
