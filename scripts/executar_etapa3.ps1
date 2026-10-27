# Reconstroi a Etapa 3 (linhas acessiveis e frequencia programada) a partir da raiz do projeto:
#   powershell -ExecutionPolicy Bypass -File scripts\executar_etapa3.ps1
# Pre-requisito: Etapas 1 e 2 carregadas no banco sevilla_oferta_bus.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"

$passos = @(
    "scripts\10_oferta_programada.py",
    "scripts\11_testes_etapa3.py",
    "scripts\12_exportar_etapa3.py"
)
foreach ($p in $passos) {
    Write-Host "==> $p" -ForegroundColor Cyan
    & $py $p
    if ($LASTEXITCODE -ne 0) { throw "Falha em $p (codigo $LASTEXITCODE)" }
}
Write-Host "Etapa 3 concluida." -ForegroundColor Green
