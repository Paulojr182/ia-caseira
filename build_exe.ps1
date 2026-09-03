$ErrorActionPreference = "Stop"

$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente virtual não encontrado. Crie o venv e instale as dependências primeiro."
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name ALFRED `
    --collect-all google.genai `
    (Join-Path $PSScriptRoot "main_basic.py")

Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.example") `
    -Destination (Join-Path $PSScriptRoot "dist\.env.example") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README_EXECUTAVEL.txt") `
    -Destination (Join-Path $PSScriptRoot "dist\LEIA-ME.txt") -Force

Write-Host "Executável criado em dist\ALFRED.exe"
