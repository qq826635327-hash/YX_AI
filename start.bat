@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM  AI Drama Studio - Start
REM  Double-click to run: opens a new PowerShell window
REM ============================================================
pushd "%~dp0"
start "AI Drama Studio" powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\restart.ps1"
popd
