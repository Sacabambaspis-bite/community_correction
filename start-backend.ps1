# ============================================================
# start-backend.ps1 - FastAPI backend startup (PowerShell 5+)
# Usage: .\start-backend.ps1   (from project root)
# Design: keep env vars in current PowerShell session only; no python-dotenv
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "=== Community Correction - Backend Startup ===" -ForegroundColor Cyan

# Step 1: inject environment vars (current process only)
Write-Host ""
Write-Host "[1/4] Injecting environment variables..." -ForegroundColor Gray

$env:SENSEVOICE_API_URL = "http://8.133.237.222:8000/recognize"
$env:SENSEVOICE_API_KEY = "jrIDYIV1cZKEj4wLqySenGo25AtLxS0XTORyGffyHZU"
# CAPTURE_FAKE intentionally NOT set -> real microphone capture
# USER_TOKEN / ADMIN_TOKEN intentionally NOT set -> use backend demo values
$env:APP_ENV = "development"

Write-Host "  SENSEVOICE_API_URL = $env:SENSEVOICE_API_URL"
Write-Host "  SENSEVOICE_API_KEY  = (set, hidden)"
Write-Host "  CAPTURE_FAKE        = (not set - real capture)"
Write-Host "  APP_ENV             = $env:APP_ENV"

# Step 2: verify Python
Write-Host ""
Write-Host "[2/4] Verifying Python..." -ForegroundColor Gray

$pythonCmd = $null
foreach ($candidate in @("python", "py", "python3")) {
    try {
        & $candidate --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $candidate
            break
        }
    } catch {}
}
if (-not $pythonCmd) {
    Write-Host "ERROR: python not found, please install Python 3.11+" -ForegroundColor Red
    exit 1
}
Write-Host "  Python command: $pythonCmd"

# Step 3: run seed (idempotent)
Write-Host ""
Write-Host "[3/4] Seeding demo data (idempotent)..." -ForegroundColor Gray

& $pythonCmd scripts/seed_demo.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: seed_demo.py returned non-zero, continuing anyway" -ForegroundColor Yellow
}

# Step 4: start uvicorn
Write-Host ""
Write-Host "[4/4] Starting FastAPI backend..." -ForegroundColor Gray
Write-Host "  URL : http://127.0.0.1:8000"
Write-Host "  Ctrl+C to stop"
Write-Host ""

& $pythonCmd -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
