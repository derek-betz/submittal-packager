[CmdletBinding()]
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$PythonVersion = "3.12"
$ExtraDependencies = ".[test]"

function Ensure-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is required. Install App Installer from the Microsoft Store."
    }
}

function Install-Python {
    Write-Host "Installing Python $PythonVersion via winget..."
    winget install -e --id "Python.Python.$PythonVersion" --source winget `
        --accept-source-agreements --accept-package-agreements
}

function Get-Python {
    $pythonExe = & py -$PythonVersion -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $pythonExe) {
        return $null
    }
    return $pythonExe.Trim()
}

function Ensure-Python {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        Ensure-Winget
        Install-Python
    }
    $pythonExe = Get-Python
    if (-not $pythonExe) {
        Ensure-Winget
        Install-Python
        $pythonExe = Get-Python
    }
    if (-not $pythonExe) {
        throw "Python $PythonVersion is not available after install."
    }
    return $pythonExe
}

function Ensure-PythonPath {
    param([string]$PythonExe)

    $pythonDir = Split-Path $PythonExe
    $pythonScripts = Join-Path $pythonDir "Scripts"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @()
    if ($userPath) {
        $entries = $userPath -split ';' | Where-Object { $_ }
    }
    $entries = $entries | Where-Object { $_ -notin @($pythonDir, $pythonScripts) }
    $newEntries = @($pythonDir, $pythonScripts) + $entries
    [Environment]::SetEnvironmentVariable("Path", ($newEntries -join ';'), "User")

    $currentEntries = $env:PATH -split ';' | Where-Object { $_ }
    $currentEntries = $currentEntries | Where-Object { $_ -notin @($pythonDir, $pythonScripts) }
    $env:PATH = (@($pythonDir, $pythonScripts) + $currentEntries) -join ';'
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    $pythonExe = Ensure-Python
    Ensure-PythonPath -PythonExe $pythonExe

    Write-Host "Installing test dependencies..."
    & $pythonExe -m pip install --upgrade pip
    & $pythonExe -m pip install -e $ExtraDependencies

    if (-not $SkipTests) {
        Write-Host "Running tests..."
        & $pythonExe scripts\run_tests.py
    } else {
        Write-Host "Skipping tests."
    }

    & $pythonExe --version
} finally {
    Pop-Location
}
