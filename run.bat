@echo off
setlocal
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
echo   Ref2VA H3 v1.1
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
