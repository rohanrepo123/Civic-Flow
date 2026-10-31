param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$activeVenvPython = if ($env:VIRTUAL_ENV) { Join-Path $env:VIRTUAL_ENV "Scripts\python.exe" } else { $null }
$useActiveVenv = $activeVenvPython -and (Test-Path $activeVenvPython)
$venvDir = if ($useActiveVenv) { $env:VIRTUAL_ENV } else { Join-Path $repoRoot ".venv" }
$venvPython = if ($useActiveVenv) { $activeVenvPython } else { Join-Path $venvDir "Scripts\python.exe" }
$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue

if (-not $useActiveVenv -and -not (Test-Path $venvPython)) {
    if (-not $pythonLauncher) {
        throw "Install Python 3.11, 3.12, or 3.13 and the Windows Python launcher, then rerun this script. Python 3.14 is not supported by the current FAISS stack."
    }

    $created = $false
    foreach ($version in @("3.11", "3.12", "3.13")) {
        $basePython = & $pythonLauncher.Source "-$version" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0) { continue }
        & $basePython -m venv --system-site-packages --without-pip $venvDir 2>$null
        if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPython)) {
            $created = $true
            break
        }
    }
    if (-not $created) {
        throw "Could not find Python 3.11-3.13. Install one of those versions and rerun setup."
    }
}

$pythonVersion = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pythonVersion -ge [version]"3.14") {
    throw "The selected environment uses Python $pythonVersion. Activate Python 3.11-3.13 and rerun setup; FAISS currently crashes with Python 3.14 here."
}
$basePython = $venvPython
if ($pythonLauncher) {
    $basePython = & $pythonLauncher.Source "-$pythonVersion" -c "import sys; print(sys.executable)"
    if ($LASTEXITCODE -ne 0) { throw "Could not locate the base Python $pythonVersion interpreter." }
}

Push-Location $repoRoot
try {
    $packages = @(
        "-e", "./backend/contracts/civicflow_contracts",
        "-e", "./backend/services/core_api",
        "-e", "./backend/services/ai_agent",
        "-e", "./backend/services/browser_agent"
    )
    if ($useActiveVenv -and (Test-Path (Join-Path $venvDir "Scripts\pip.exe"))) {
        & $venvPython -m pip install @packages
    } else {
        & $basePython -m pip --python $venvDir install @packages
    }
    if ($LASTEXITCODE -ne 0) { throw "Python service dependencies failed to install." }

    $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
    if (-not $pnpm) {
        $corepack = Get-Command corepack -ErrorAction SilentlyContinue
        if (-not $corepack) { throw "Install Node.js 22 (which includes Corepack), then rerun setup." }
        & $corepack.Source pnpm --dir frontend_member1 install --frozen-lockfile
    } else {
        & $pnpm.Source --dir frontend_member1 install --frozen-lockfile
    }
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependencies failed to install." }
} finally {
    Pop-Location
}

Write-Host "Local dependencies are installed in $venvPython."
Write-Host "For source-grounded service requests, cache BGE-M3 once using:"
Write-Host "  $venvPython -m backend.app.agent.services.embeddings --download-model"
Write-Host "This model download is separate and can use substantial disk space."
