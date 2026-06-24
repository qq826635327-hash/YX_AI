# ============================================================
#  AI Drama Studio - Force Restart
#  Called by start.bat, or directly: powershell -File scripts\restart.ps1
#  Flow: kill ports -> start backend -> health check -> start frontend -> health check
#  Note: all output in English to avoid encoding issues on Windows
# ============================================================

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
$BackendPort = 8000
$FrontendPort = 5173
$LogDir = Join-Path $Root "logs"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

$Ts = Get-Date -Format "yyyyMMdd-HHmmss"
$BeLog = Join-Path $LogDir "backend-$Ts.log"
$FeLog = Join-Path $LogDir "frontend-$Ts.log"

Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "  |     AI Drama Studio - Restart                 |" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
#  1. Force kill ports
# ============================================================
function Kill-Port([int]$Port) {
    $maxTries = 5
    for ($i = 1; $i -le $maxTries; $i++) {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $conns) {
            Write-Host "  [ok] Port $Port is free" -ForegroundColor Green
            return
        }
        foreach ($conn in $conns) {
            $procId = $conn.OwningProcess
            Write-Host "  [..] Killing port $Port PID=$procId (attempt $i)" -ForegroundColor Yellow
            try {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" -ErrorAction SilentlyContinue |
                    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            } catch {}
        }
        Start-Sleep -Milliseconds 600
    }
    $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($still) {
        Write-Host "  [WARN] Port $Port still occupied after $maxTries attempts" -ForegroundColor Red
    }
}

Write-Host "[1/4] Force killing ports $BackendPort / $FrontendPort ..." -ForegroundColor White
Kill-Port $BackendPort
Kill-Port $FrontendPort

# ============================================================
#  2. Environment check
# ============================================================
Write-Host ""
Write-Host "[2/4] Environment check..." -ForegroundColor White

$venvPython = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  [X] Backend venv not found: $venvPython" -ForegroundColor Red
    Write-Host "      Run scripts\init-backend.bat first" -ForegroundColor Red
    Write-Host "  Press any key to close..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
Write-Host "  [ok] Backend venv" -ForegroundColor Green

$nodeModules = Join-Path $Root "frontend\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "  [..] Frontend deps missing, running npm install..." -ForegroundColor Yellow
    Push-Location (Join-Path $Root "frontend")
    npm install --silent 2>&1 | Out-Null
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [X] npm install failed" -ForegroundColor Red
        Write-Host "  Press any key to close..." -ForegroundColor DarkGray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}
Write-Host "  [ok] Frontend deps" -ForegroundColor Green

# ============================================================
#  3. Start backend
# ============================================================
Write-Host ""
Write-Host "[3/4] Starting backend FastAPI (http://127.0.0.1:$BackendPort)..." -ForegroundColor White
Write-Host "      Log: $BeLog" -ForegroundColor Gray

$backendDir = Join-Path $Root "backend"
$beProc = Start-Process -FilePath $venvPython -ArgumentList @(
    "-m", "uvicorn", "app.main:app",
    "--host", "127.0.0.1", "--port", $BackendPort,
    "--log-level", "info"
) -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $BeLog -RedirectStandardError (Join-Path $LogDir "backend-err-$Ts.log")

$beOk = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            $beOk = $true
            Write-Host "  [ok] Backend ready ($i s)" -ForegroundColor Green
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $beOk) {
    Write-Host "  [X] Backend not ready within 30s" -ForegroundColor Red
    Write-Host "      ---- Last 30 lines of log ----" -ForegroundColor Red
    if (Test-Path $BeLog) { Get-Content $BeLog -Tail 30 } else { Write-Host "      (no log file)" }
    Write-Host "      --------------------------------" -ForegroundColor Red
    Write-Host "      Common causes: syntax error / port occupied / missing deps" -ForegroundColor Red
    if (-not $beProc.HasExited) { Stop-Process -Id $beProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "  Press any key to close..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# ============================================================
#  4. Start frontend
# ============================================================
Write-Host ""
Write-Host "[4/4] Starting frontend Vite (http://127.0.0.1:$FrontendPort)..." -ForegroundColor White
Write-Host "      Log: $FeLog" -ForegroundColor Gray

$frontendDir = Join-Path $Root "frontend"
$feProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/c", "npx vite --host 127.0.0.1 --port $FrontendPort --strictPort"
) -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $FeLog -RedirectStandardError (Join-Path $LogDir "frontend-err-$Ts.log")

$feOk = $false
for ($i = 1; $i -le 25; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) {
            $feOk = $true
            Write-Host "  [ok] Frontend ready ($i s)" -ForegroundColor Green
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $feOk) {
    Write-Host "  [X] Frontend not ready within 25s" -ForegroundColor Red
    Write-Host "      ---- Last 30 lines of log ----" -ForegroundColor Red
    if (Test-Path $FeLog) { Get-Content $FeLog -Tail 30 } else { Write-Host "      (no log file)" }
    Write-Host "      --------------------------------" -ForegroundColor Red
    if (-not $beProc.HasExited) { Stop-Process -Id $beProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "  Press any key to close..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# ============================================================
#  Done
# ============================================================
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Green
Write-Host "  |  Frontend:  http://127.0.0.1:$FrontendPort              |" -ForegroundColor Green
Write-Host "  |  Backend:   http://127.0.0.1:$BackendPort               |" -ForegroundColor Green
Write-Host "  |  API Docs:  http://127.0.0.1:$BackendPort/docs          |" -ForegroundColor Green
Write-Host "  |                                                |" -ForegroundColor Green
Write-Host "  |  Live logs:                                    |" -ForegroundColor Green
Write-Host "  |    Backend: Get-Content '$BeLog' -Wait -Tail  |" -ForegroundColor Green
Write-Host "  |    Frontend: Get-Content '$FeLog' -Wait -Tail |" -ForegroundColor Green
Write-Host "  |                                                |" -ForegroundColor Green
Write-Host "  |  Stop: run stop.bat                            |" -ForegroundColor Green
Write-Host "  ================================================" -ForegroundColor Green
Write-Host ""

Start-Process "http://127.0.0.1:$FrontendPort/"

Write-Host "  Press any key to close this window..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
