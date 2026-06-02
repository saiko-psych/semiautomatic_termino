@echo off
REM tools/vpn-down.cmd
REM
REM Tear down any running openconnect.exe tunnel and restart the
REM coexisting VPN services (Cisco Secure Client + Mullvad) that
REM auto_vpn_win temporarily stopped.
REM
REM Administrator is required because taskkill /F on openconnect.exe
REM and net start on the services both need elevation.

setlocal
set "PROJECT_ROOT=%~dp0.."

echo Spawning elevated python (UAC prompt incoming)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '-m','utils.auto_vpn_win','down' -WorkingDirectory '%PROJECT_ROOT%' -Verb RunAs -Wait"

echo.
echo Done. Press any key to close.
pause >nul

endlocal
