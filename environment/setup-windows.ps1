# Tuesday Cinema Club starter kit: local studio setup for Windows (PowerShell).
#
# What it does (and nothing else):
#   1. Checks for Ollama (install it from https://ollama.com/download first).
#   2. Pulls the workshop writing model, llama3.2:3b (about 2 GB).
#   3. Creates a Python virtual environment in .venv with the optional helpers.
#   4. Runs environment\check_setup.py.
#
# Usage, from the repository root:
#   powershell -ExecutionPolicy Bypass -File environment\setup-windows.ps1

$ErrorActionPreference = "Stop"
$Model = if ($env:TCC_MODEL) { $env:TCC_MODEL } else { "llama3.2:3b" }
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "`n== 1 of 4: Ollama =="
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "[missing] Ollama. Download and run the installer from https://ollama.com/download, then rerun this script."
    exit 1
}
Write-Host "[ready] Ollama is installed."

Write-Host "`n== 2 of 4: Writing model ($Model) =="
ollama pull $Model

Write-Host "`n== 3 of 4: Python helpers =="
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "[missing] Python 3. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and rerun."
    exit 1
}
if (-not (Test-Path .venv)) { & $py.Source -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
Write-Host "[ready] .venv created. Use .venv\Scripts\python.exe to run scripts with the optional helpers."

Write-Host "`n== 4 of 4: Check =="
& .\.venv\Scripts\python.exe environment\check_setup.py

Write-Host "`nNext: test the model. If it replies, you are ready."
Write-Host "  ollama run $Model `"hi`""
