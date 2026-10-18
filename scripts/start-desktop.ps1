param([switch]$NoOpen)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonwPath = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { throw 'Prepare the project Python environment first. See LOCAL_APP.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'backend\staticapp\index.html'))) { throw 'Build the local dashboard with scripts/build-local.ps1 first.' }
$launchArgs = @('desktop/launch.pyw')
if ($NoOpen) { $launchArgs += '--no-open' }
Start-Process -FilePath $pythonwPath -ArgumentList $launchArgs -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
Write-Output 'Derek is starting in the Windows tray. Workspace: http://127.0.0.1:8000'
