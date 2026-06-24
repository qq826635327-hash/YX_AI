@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM ============================================================
REM  AI Drama Studio - Stop
REM  Double-click to stop all services
REM ============================================================

echo.
echo  Stopping AI Drama Studio...
echo.

set "FOUND=0"

REM 1. Kill by process name
for /f "tokens=2 delims=," %%a in ('tasklist /fo csv /nh 2^>nul ^| findstr /I "uvicorn node vite"') do (
    taskkill /T /F /PID %%~a >nul 2>&1
    set "FOUND=1"
)

REM 2. Kill by port (8000 / 5173)
call :kill_port 8000
call :kill_port 5173

if "!FOUND!"=="0" (
    echo   [i] No running services found
) else (
    echo   [ok] Services stopped
)
echo.
pause
exit /b 0

:kill_port
set "KP_PORT=%~1"
set "KP_TRIES=0"
:kp_loop
netstat -ano | findstr ":%KP_PORT% " | findstr "LISTENING" >nul 2>&1
if !ERRORLEVEL! neq 0 goto :eof
set /A KP_TRIES+=1
if !KP_TRIES! gtr 3 goto :eof
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%KP_PORT% " ^| findstr "LISTENING"') do (
    taskkill /T /F /PID %%p >nul 2>&1
    set "FOUND=1"
    echo   [ok] Port %KP_PORT% PID %%p killed
)
powershell -NoProfile -Command "Start-Sleep -Milliseconds 500" >nul 2>&1
goto :kp_loop
