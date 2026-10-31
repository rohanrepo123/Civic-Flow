param(
    [switch]$WithPlaywright
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$activeVenvPython = if ($env:VIRTUAL_ENV) { Join-Path $env:VIRTUAL_ENV "Scripts\python.exe" } else { $null }
$venvPython = if ($activeVenvPython -and (Test-Path $activeVenvPython)) { $activeVenvPython } else { Join-Path $repoRoot ".venv\Scripts\python.exe" }
$node = Get-Command node -ErrorAction SilentlyContinue
$nextCli = Join-Path $repoRoot "frontend_member1\node_modules\next\dist\bin\next"
$runtimeDir = Join-Path $repoRoot "runtime"
$logsDir = Join-Path $repoRoot "runtime_logs"
$stateFile = Join-Path $runtimeDir "local-services.json"

if (-not (Test-Path $venvPython) -or -not (Test-Path $nextCli) -or -not $node) {
    throw "Run .\scripts\setup-local.ps1 first."
}
if (Test-Path $stateFile) {
    throw "Local services already have a process record. Run .\scripts\stop-local.ps1 first."
}

function Find-AvailablePort([int[]]$Candidates, [int[]]$AlreadySelected = @()) {
    foreach ($candidate in $Candidates) {
        if ($candidate -in $AlreadySelected) { continue }
        $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $candidate)
        try {
            $probe.Start()
            return $candidate
        } catch {
            continue
        } finally {
            $probe.Stop()
        }
    }
    throw "No available local port was found in the requested range."
}

$frontendPort = Find-AvailablePort @(3001..3010)
$corePort = Find-AvailablePort @(8000..8020)
$aiPort = Find-AvailablePort @(8000..8020) @($corePort)
$browserPort = Find-AvailablePort @(8000..8020) @($corePort, $aiPort)
New-Item -ItemType Directory -Force -Path $runtimeDir, $logsDir | Out-Null

# Load local provider choices from .env without printing their values.
$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line.TrimStart().StartsWith("#")) { continue }
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

$env:PYTHONPATH = (Join-Path $repoRoot "backend\contracts\civicflow_contracts") + ";" + $repoRoot
$env:LOCAL_DEMO_MODE = "true"
$env:USE_MOCK_AI = "false"
$env:USE_MOCK_BROWSER = "false"
$env:DATABASE_URL = "postgresql+asyncpg://civicflow:civicflow@127.0.0.1:5432/civicflow"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:AI_AGENT_URL = "http://127.0.0.1:$aiPort"
$env:BROWSER_AGENT_URL = "http://127.0.0.1:$browserPort"
$env:BROWSER_AGENT_API_TOKEN = [guid]::NewGuid().ToString("N")
$env:CORS_ORIGINS = @("http://localhost:$frontendPort", "http://127.0.0.1:$frontendPort") | ConvertTo-Json -Compress
$ollamaBaseUrl = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL } else { "http://localhost:11434" }
$env:OLLAMA_BASE_URL = $ollamaBaseUrl -replace "host\.docker\.internal", "localhost"
$env:OLLAMA_CHAT_MODEL = if ($env:OLLAMA_CHAT_MODEL) { $env:OLLAMA_CHAT_MODEL } else { "nemotron-3-super:cloud" }
$env:LLM_PROVIDER = "ollama"
$env:OPENAI_MODEL = ""
$env:OPENAI_API_KEY = ""
$env:EMBEDDING_PROVIDER = if ($env:EMBEDDING_PROVIDER) { $env:EMBEDDING_PROVIDER } else { "sentence_transformers" }
$env:EMBEDDING_MODEL = if ($env:EMBEDDING_MODEL) { $env:EMBEDDING_MODEL } else { "BAAI/bge-m3" }
$env:EMBEDDING_ALLOW_DOWNLOAD = "false"
$env:CIVICFLOW_BROWSER_RUNTIME = if ($WithPlaywright) { "playwright" } else { "mock" }
$env:CIVICFLOW_ALLOW_LOCAL_MOCK = "true"
$env:NEXT_PUBLIC_CORE_API_URL = "http://localhost:$corePort"
$env:NEXT_PUBLIC_BROWSER_AGENT_URL = "http://localhost:$browserPort"

$started = [System.Collections.Generic.List[object]]::new()
function Start-LocalService([string]$Name, [string]$Exe, [string[]]$Arguments, [string]$WorkingDirectory) {
    $stdout = Join-Path $logsDir "$Name.out.log"
    $stderr = Join-Path $logsDir "$Name.err.log"
    $process = Start-Process -FilePath $Exe -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $started.Add([pscustomobject]@{
        name = $Name
        pid = $process.Id
        executable = $Exe
        startedAtTicks = $process.StartTime.ToUniversalTime().Ticks
    })
    Start-Sleep -Milliseconds 600
    if ($process.HasExited) { throw "$Name exited during startup. See $stderr" }
}

try {
    Start-LocalService "browser-agent" $venvPython @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$browserPort") `
        (Join-Path $repoRoot "backend\services\browser_agent")
    Start-LocalService "ai-agent" $venvPython @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$aiPort") `
        (Join-Path $repoRoot "backend\services\ai_agent")
    Start-LocalService "core-api" $venvPython @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$corePort") `
        (Join-Path $repoRoot "backend\services\core_api")
    Start-LocalService "frontend" $node.Source @((('"{0}"' -f $nextCli)), "dev", "--hostname", "127.0.0.1", "--port", "$frontendPort") `
        (Join-Path $repoRoot "frontend_member1")

    $started | ConvertTo-Json | Set-Content -Path $stateFile -Encoding utf8
    $checks = @(
        @{ name = "Browser Agent"; url = "http://127.0.0.1:$browserPort/health/ready" },
        @{ name = "AI Agent"; url = "http://127.0.0.1:$aiPort/health/ready" },
        @{ name = "Core API"; url = "http://127.0.0.1:$corePort/health/ready" },
        @{ name = "Frontend"; url = "http://127.0.0.1:$frontendPort/" }
    )
    foreach ($check in $checks) {
        $ready = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            try {
                Invoke-WebRequest -Uri $check.url -TimeoutSec 2 -UseBasicParsing | Out-Null
                $ready = $true
                break
            } catch { Start-Sleep -Milliseconds 750 }
        }
        if (-not $ready) { throw "$($check.name) did not become ready. Check logs in $logsDir" }
    }

    Write-Host "CivicFlow is running without Docker."
    Write-Host "Frontend:     http://localhost:$frontendPort"
    Write-Host "Core API:     http://localhost:$corePort/health/ready"
    Write-Host "AI Agent:     http://localhost:$aiPort/health/ready"
    Write-Host "Browser:      http://localhost:$browserPort/health/ready"
    Write-Host "Browser mode: $env:CIVICFLOW_BROWSER_RUNTIME"
    Write-Host "Logs:         $logsDir"
    Write-Host "Stop with:    .\scripts\stop-local.ps1"
} catch {
    $started | ConvertTo-Json | Set-Content -Path $stateFile -Encoding utf8
    & (Join-Path $PSScriptRoot "stop-local.ps1")
    throw
}
