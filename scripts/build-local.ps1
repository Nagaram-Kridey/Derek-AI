param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$dashboardRoot = Join-Path $projectRoot 'web_dashboard'
if (-not $SkipBuild) {
    Push-Location $dashboardRoot
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Dashboard build failed.' }
    } finally { Pop-Location }
}
$source = Join-Path $dashboardRoot 'dist'
$destination = Join-Path $projectRoot 'backend\staticapp'
if (-not (Test-Path -LiteralPath (Join-Path $source 'index.html'))) { throw 'No dashboard build exists.' }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
# Keep prior hashed assets so an already-open tab still loads during updates.
Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
Write-Output 'Built dashboard prepared for the local app.'
