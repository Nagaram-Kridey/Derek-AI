param([int]$Port = 8000, [switch]$Celery)
$ErrorActionPreference = 'Stop'
if (-not $Celery) {
    & (Join-Path $PSScriptRoot 'start-desktop.ps1')
    return
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimeDir = Join-Path $projectRoot '.companion'
$localStatusPath = Join-Path $runtimeDir 'runtime\supervisor.json'
if (Test-Path -LiteralPath $localStatusPath) {
    try {
        $localStatus = Get-Content -LiteralPath $localStatusPath -Raw | ConvertFrom-Json
        $localStatusAge = [DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($localStatus.updated_at)
        if ($localStatus.status -ne 'stopped' -and $localStatusAge.TotalSeconds -lt 30 -and (Get-Process -Id $localStatus.pid -ErrorAction SilentlyContinue)) {
            throw 'Stop the local tray app before starting the separate Celery runtime.'
        }
    } catch {
        if ($_.Exception.Message -like 'Stop the local tray*') { throw }
    }
}
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Prepare the project Python environment first.' }
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$services = @(
    @{ Name = 'backend'; Match = 'manage\.py.*runserver'; Args = @('backend/manage.py', 'runserver', "127.0.0.1:$Port", '--noreload') },
    @{ Name = 'research'; Match = 'celery.*worker.*derek-research'; Args = @('-m','celery','-A','config','worker','--pool=solo','--concurrency=1','--queues=celery','--hostname=derek-research@%h','--loglevel=INFO') },
    @{ Name = 'interactive'; Match = 'celery.*worker.*derek-interactive'; Args = @('-m','celery','-A','config','worker','--pool=solo','--concurrency=1','--queues=interactive','--hostname=derek-interactive@%h','--loglevel=INFO') },
    @{ Name = 'delivery'; Match = 'celery.*worker.*derek-delivery'; Args = @('-m','celery','-A','config','worker','--pool=solo','--concurrency=1','--queues=delivery','--hostname=derek-delivery@%h','--loglevel=INFO') },
    @{ Name = 'scheduler'; Match = 'celery.*\bbeat\b'; Args = @('-m','celery','-A','config','beat','--schedule=.companion/celerybeat-schedule','--loglevel=INFO') }
)
# The runtime needs Docker/Redis first. This helper starts no paid provider calls.
$priorPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $projectRoot 'backend'
    foreach ($service in $services) {
        $existing = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $pythonPath -and $_.CommandLine -match $service.Match }
        if ($existing) { Write-Output "$($service.Name): already running"; continue }
        if ($service.Name -eq 'research') {
            $oldWorker = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $pythonPath -and $_.CommandLine -match 'celery.*\bworker\b' -and $_.CommandLine -notmatch 'derek-(research|interactive|delivery)' }
            if ($oldWorker) { throw 'An older project worker is running. Stop it cleanly before starting the separated workers.' }
        }
        $process = Start-Process -FilePath $pythonPath -ArgumentList $service.Args -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir "$($service.Name)-stdout.log") -RedirectStandardError (Join-Path $runtimeDir "$($service.Name)-stderr.log")
        Write-Output "$($service.Name): started (process $($process.Id))"
    }
} finally {
    if ($null -eq $priorPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue } else { $env:PYTHONPATH = $priorPythonPath }
}
