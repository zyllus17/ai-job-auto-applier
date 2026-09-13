<#
.SYNOPSIS
    AI Job Auto-Applier - Windows Turnkey Quickstart for PowerShell
.DESCRIPTION
    Automated one-command setup for Windows PowerShell users.
    Checks Python, installs required packages, fetches Playwright Chromium,
    and initializes environment.
#>

[CmdletBinding()]
param()

Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   🚀 AI JOB AUTO-APPLIER - WINDOWS POWERSHELL QUICKSTART       " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Setting up your automated job search, CV generator, and tracker..."
Write-Host ""

# 1. Detect Python
$pythonCmd = $null
$pyPrefix = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
    $pyPrefix = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
} else {
    Write-Host "[ERROR] Python 3 was not found in your PATH!" -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://www.python.org/ and verify 'Add to PATH' is checked." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Using Python: $pythonCmd" -ForegroundColor Green
Write-Host ""

# 2. Install Python Dependencies
Write-Host "[+] Installing Python dependencies..." -ForegroundColor Yellow
& $pythonCmd ($pyPrefix + @("-m", "pip", "install", "--quiet", "--upgrade", "pip"))
& $pythonCmd ($pyPrefix + @("-m", "pip", "install", "pypdf", "pyyaml", "python-telegram-bot", "psutil", "python-dotenv", "aiohttp", "playwright", "fastapi", "uvicorn[standard]", "websockets"))

Write-Host "[OK] Python dependencies installed successfully." -ForegroundColor Green
Write-Host ""

# 3. Install Playwright Chromium Browser
Write-Host "[+] Installing Playwright Chromium browser binary..." -ForegroundColor Yellow
& $pythonCmd ($pyPrefix + @("-m", "playwright", "install", "chromium"))
Write-Host "[OK] Playwright Chromium ready." -ForegroundColor Green
Write-Host ""

# 4. Environment Config Setup
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Created .env configuration from template." -ForegroundColor Green
}

# 5. Directories
if (-not (Test-Path "documents\applications")) { New-Item -ItemType Directory -Path "documents\applications" -Force | Out-Null }
if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" -Force | Out-Null }

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   🎉 SETUP COMPLETE! AI JOB AUTO-APPLIER READY ON WINDOWS      " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Launch commands:"
Write-Host "  1. Web Dashboard:       .\run.ps1" -ForegroundColor Green
Write-Host "  2. Make Shim:           .\make.ps1 run" -ForegroundColor Green
Write-Host "  3. Background Daemon:   $pythonCmd tools\daemon_job_runner.py --interval-mins 60"
Write-Host "  4. Browser Auto-Apply:  $pythonCmd tools\browser_autofill.py `"<url>`" --mode semi-auto"
Write-Host "  5. Telegram Bot:        $pythonCmd tools\telegram_bot.py"
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""
