<#
.SYNOPSIS
    AI Job Auto-Applier - Windows PowerShell Make Shim
.DESCRIPTION
    Provides make-style command routing (run, install, clean, test, help) in PowerShell.
.EXAMPLE
    .\make.ps1 run
    .\make.ps1 install
    .\make.ps1 clean
    .\make.ps1 test
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Target = "help",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

Set-Location -Path $PSScriptRoot

switch ($Target.ToLower()) {
    "help" {
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host "  🚀 AI Job Auto-Applier - PowerShell Make Shim" -ForegroundColor Cyan
        Write-Host "============================================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  .\make.ps1 run      - Install deps, free port, start dashboard & open browser" -ForegroundColor Green
        Write-Host "  .\make.ps1 install  - Install dependencies and Playwright browser binary" -ForegroundColor Green
        Write-Host "  .\make.ps1 clean    - Free port 8420 by stopping dashboard processes" -ForegroundColor Green
        Write-Host "  .\make.ps1 test     - Run automated test suite" -ForegroundColor Green
        Write-Host ""
        Write-Host "Direct alternatives:"
        Write-Host "  .\run.ps1           - Launch dashboard directly"
        Write-Host "  python run.py       - Universal launcher"
        Write-Host ""
        break
    }
    "run" {
        & "$PSScriptRoot\run.ps1" $RemainingArgs
        break
    }
    "install" {
        & "$PSScriptRoot\run.ps1" @("--install")
        break
    }
    "clean" {
        & "$PSScriptRoot\run.ps1" @("--clean-only")
        break
    }
    "test" {
        & "$PSScriptRoot\run.ps1" @("--test")
        break
    }
    default {
        & "$PSScriptRoot\run.ps1" @($Target) + $RemainingArgs
        break
    }
}
