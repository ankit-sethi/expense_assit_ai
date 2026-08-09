# launch.ps1 — one-click startup for Expense Dashboard
# Run this script (or use the desktop shortcut) to start everything and open the browser.

Set-Location $PSScriptRoot
$ErrorActionPreference = "Stop"

function Step($n, $msg) { Write-Host "[Step $n/6] $msg" -ForegroundColor Cyan }
function Fail($msg)      { Write-Host "ERROR: $msg" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }
function OK($msg)        { Write-Host "  OK: $msg" -ForegroundColor Green }

# ── Step 1: Check Docker is installed ────────────────────────────────────────
Step 1 "Checking Docker..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop and try again."
}
OK "Docker found."

# ── Step 2: Start PostgreSQL container if not running ─────────────────────────
Step 2 "Starting PostgreSQL (docker-compose)..."
$running = docker ps --filter "name=expense_postgres" --format "{{.Names}}" 2>$null
if ($running -match "expense_postgres") {
    OK "PostgreSQL already running."
} else {
    Write-Host "  Starting containers..."
    $result = docker-compose up -d 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host $result -ForegroundColor Yellow
        Fail "docker-compose failed. Check docker-compose.yml and run 'docker-compose up -d' manually."
    }
    OK "Containers started."
}

# ── Step 3: Wait for PostgreSQL to be ready ───────────────────────────────────
Step 3 "Waiting for PostgreSQL to be ready..."
$pgReady = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 1
    $check = docker exec expense_postgres pg_isready -U expense_user 2>$null
    if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
    Write-Host "  ... ($i/20)" -ForegroundColor DarkGray
}
if (-not $pgReady) {
    Fail "PostgreSQL did not become ready in time. Check Docker Desktop logs for the expense_postgres container."
}
OK "PostgreSQL is ready."

# ── Step 4: Start FastAPI server in a new window ──────────────────────────────
Step 4 "Starting FastAPI server..."
$port = 8000

# Find a Python interpreter that has the app's dependencies installed.
# Plain "python" may resolve to a pyenv shim or another install without fastapi.
$pythonExe = $null
$candidates = @("C:\Python314\python.exe", "python", "py")
foreach ($cand in $candidates) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) {
        & $cand -c "import uvicorn, fastapi" 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonExe = $cand; break }
    }
}
if (-not $pythonExe) {
    Fail "No Python with fastapi/uvicorn found. Run: C:\Python314\python.exe -m pip install -r app\requirements.txt"
}
OK "Using Python: $pythonExe"

# Check if port already in use by a listening server (ignore TIME_WAIT etc.)
$portInUse = netstat -ano 2>$null | Select-String "LISTENING" | Select-String ":$port\s"
if ($portInUse) {
    OK "Port $port already in use - assuming server is already running."
} else {
    # Run from inside app/ — the app's imports (ai.*, storage.*) resolve relative to app/
    $serverCmd = "Set-Location '$PSScriptRoot\app'; & '$pythonExe' -m uvicorn main_nlp_interface:app --host 0.0.0.0 --port $port"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $serverCmd -WindowStyle Normal
    OK "Server process launched (check the new window for logs)."
}

# ── Step 5: Wait for server to respond ───────────────────────────────────────
Step 5 "Waiting for server to respond..."
$serverReady = $false
$maxTries = 45   # first start can take 30s+ (imports openai, sqlalchemy, etc.)
for ($i = 1; $i -le $maxTries; $i++) {
    Start-Sleep -Seconds 1
    try {
        # Use 127.0.0.1 (not localhost) — localhost resolves to IPv6 ::1 first, where uvicorn isn't listening
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/dashboard" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $serverReady = $true; break }
    } catch {}
    Write-Host "  ... ($i/$maxTries)" -ForegroundColor DarkGray
}
if ($serverReady) {
    OK "Server is responding."
} else {
    Write-Host "WARNING: Server did not respond in time. The browser will open anyway - check the server window for errors." -ForegroundColor Yellow
}

# ── Step 6: Open browser ─────────────────────────────────────────────────────
Step 6 "Opening browser..."
$url = "http://localhost:$port/dashboard"

# The default browser (Chrome) install on this machine is broken (missing version
# folder -> "side-by-side configuration is incorrect"). Detect a working browser
# explicitly instead of relying on the default URL handler.
$browsers = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)
$opened = $false
foreach ($b in $browsers) {
    # A working Chrome/Edge install has a versioned subfolder (e.g. 122.0.6261.95)
    # next to the exe; if it's missing the exe fails with a side-by-side error.
    $appDir = Split-Path $b
    if ((Test-Path $b) -and (Get-ChildItem $appDir -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d+\.' })) {
        Start-Process $b $url
        $opened = $true
        break
    }
}
if (-not $opened) {
    # Last resort: default handler
    Start-Process $url
}
OK "Done. Dashboard opened at $url"
