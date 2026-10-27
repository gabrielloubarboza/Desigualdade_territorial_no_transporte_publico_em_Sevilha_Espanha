# Reconstroi a Etapa 1 a partir da raiz do projeto:
#   powershell -ExecutionPolicy Bypass -File scripts\executar_etapa1.ps1
# Pre-requisitos: Python 3.12+ com .venv criado (ver README) e banco criado com sql\00_criar_banco.sql.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"

$passos = @(
    "scripts\01_baixar_fontes.py",
    "scripts\02_inspecionar_gtfs.py",
    "scripts\03_rede_osm.py",
    "scripts\04_carregar_banco.py",
    "scripts\05_testes_integridade.py"
)
foreach ($p in $passos) {
    Write-Host "==> $p" -ForegroundColor Cyan
    & $py $p
    if ($LASTEXITCODE -ne 0) { throw "Falha em $p (codigo $LASTEXITCODE)" }
}
Write-Host "Etapa 1 concluida." -ForegroundColor Green
