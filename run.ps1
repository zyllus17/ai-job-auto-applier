<#
.SYNOPSIS
    AI Job Auto-Applier Dashboard - Windows PowerShell Launcher
.DESCRIPTION
    Launches the cross-platform dashboard runner on Windows with auto-dependency checks,
    port cleanup, and browser launch.
.EXAMPLE
    .\run.ps1
    .\run.ps1 --clean-only
    .\run.ps1 --no-browser
#>

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

Set-Location -Path $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  🚀 AI Job Auto-Applier Dashboard - PowerShell Launcher" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Find available Python command
$pythonCmd = $null
$pythonArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
    $pythonArgs = @("-3", "run.py") + $ScriptArgs
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
    $pythonArgs = @("run.py") + $ScriptArgs
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCmd = "python3"
    $pythonArgs = @("run.py") + $ScriptArgs
} else {
    Write-Host "[ERROR] Python 3 was not found in your PATH!" -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/ and verify 'Add to PATH' is selected." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Using Python: $pythonCmd" -ForegroundColor Green
Write-Host "Starting Dashboard..." -ForegroundColor Green
Write-Host ""

& $pythonCmd $pythonArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[NOTICE] Dashboard exited with code $LASTEXITCODE." -ForegroundColor Yellow
}
