$root=Split-Path -Parent $PSScriptRoot
Push-Location $root
try { & ./.venv/Scripts/python.exe -m testing_workspace init; & ./.venv/Scripts/python.exe -m testing_workspace configure } finally {Pop-Location}
