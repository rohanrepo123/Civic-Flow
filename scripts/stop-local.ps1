$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$stateFile = Join-Path $repoRoot "runtime\local-services.json"
if (-not (Test-Path $stateFile)) {
    Write-Host "No CivicFlow local services are recorded as running."
    exit 0
}

$services = @(Get-Content $stateFile -Raw | ConvertFrom-Json)
for ($index = $services.Count - 1; $index -ge 0; $index--) {
    $service = $services[$index]
    $processInfo = Get-Process -Id $service.pid -ErrorAction SilentlyContinue
    if (-not $processInfo) {
        Write-Host "Cleared stale record for $($service.name) (PID $($service.pid) is not running)."
        continue
    }

    # Get-Process.Path may be empty/inaccessible, and stale or older state
    # files can contain values that are not valid Windows paths. Treat those
    # records as unverified rather than allowing GetFullPath to abort cleanup.
    $sameExecutable = $false
    $actualExecutable = [string]$processInfo.Path
    $recordedExecutable = [string]$service.executable
    if (-not [string]::IsNullOrWhiteSpace($actualExecutable) -and
        -not [string]::IsNullOrWhiteSpace($recordedExecutable)) {
        try {
            $actualFullPath = [IO.Path]::GetFullPath($actualExecutable)
            $recordedFullPath = [IO.Path]::GetFullPath($recordedExecutable)
            $sameExecutable = $actualFullPath -ieq $recordedFullPath
        } catch [System.ArgumentException] {
            $sameExecutable = $false
        } catch [System.NotSupportedException] {
            $sameExecutable = $false
        } catch [System.IO.PathTooLongException] {
            $sameExecutable = $false
        }
    }

    $sameStartTime = $false
    if ($service.startedAtTicks -and $processInfo.StartTime) {
        try {
            $sameStartTime = $processInfo.StartTime.ToUniversalTime().Ticks -eq [long]$service.startedAtTicks
        } catch {
            $sameStartTime = $false
        }
    }
    if (-not $sameExecutable -or -not $sameStartTime) {
        Write-Host "Skipped PID $($service.pid): it is no longer the CivicFlow $($service.name) process."
        continue
    }

    & taskkill.exe /PID $service.pid /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not stop $($service.name) (PID $($service.pid))." }
    else { Write-Host "Stopped $($service.name)." }
}
Remove-Item -LiteralPath $stateFile -Force
