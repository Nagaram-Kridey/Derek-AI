param([switch]$Publish)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Push-Location $root
try { if($Publish){ & ./.venv/Scripts/python.exe -m testing_workspace start --publish } else { & ./.venv/Scripts/python.exe -m testing_workspace start }; if($LASTEXITCODE){throw 'Test workspace failed. See message above.'} } finally {Pop-Location}
