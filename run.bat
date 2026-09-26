@echo off
setlocal
rem This file is intentionally ASCII-only: a UTF-8 .bat shows mojibake on a GBK console,
rem and switching codepage mid-file (chcp 65001) makes cmd fail to parse the rest.
rem The Chinese product name is printed by server.py instead (Windows console output
rem goes through WriteConsoleW, so it is correct under any codepage).
cd /d "%~dp0"

rem ===== editable config =====
rem Override python path if needed, e.g.:  set "PYTHON=C:\Python\python.exe"
if not defined PYTHON (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON=py -3"
)
if not defined PYTHON set "PYTHON=python"

rem 0.0.0.0 = LAN + local (friends can reach it); 127.0.0.1 = local only
if not defined HOST set "HOST=0.0.0.0"
if not defined PORT set "PORT=8090"
rem ============================

echo ================================================
echo   MiniMAX H3 Ref2VA/I2VA Video Quality Optimizer 2.0
echo   Local UI : http://127.0.0.1:%PORT%/
echo   LAN      : http://your-ip:%PORT%/   (HOST=0.0.0.0)
echo   Stop     : press Ctrl+C
echo ================================================

rem open the browser a moment after the server starts
start "" powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:%PORT%/'"

rem run the server in the foreground
"%PYTHON%" -u server.py

echo.
echo [closed]
pause
endlocal
