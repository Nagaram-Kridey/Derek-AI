$ErrorActionPreference = 'Stop'
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExecutable = if ($ollamaCommand) { $ollamaCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs/Ollama/ollama.exe' }
if (-not (Test-Path -LiteralPath $ollamaExecutable)) {
    throw 'Install Ollama for Windows, then run this script again.'
}
# These variables apply to this server process, not global Windows settings.
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
& $ollamaExecutable serve
