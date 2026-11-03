$root=Split-Path -Parent $PSScriptRoot
Push-Location $root
try { & ./.venv/Scripts/python.exe -m testing_workspace stop } finally {Pop-Location}
