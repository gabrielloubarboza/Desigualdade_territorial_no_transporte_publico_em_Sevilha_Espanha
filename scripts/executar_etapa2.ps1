# Reconstroi a Etapa 2 (acessibilidade em 400 m) a partir da raiz do projeto:
#   powershell -ExecutionPolicy Bypass -File scripts\executar_etapa2.ps1
# Pre-requisito: Etapa 1 carregada no banco sevilla_oferta_bus (scripts\executar_etapa1.ps1).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"

$passos = @(
    "scripts\06_barreiras_osm.py",
    "scripts\07_acessibilidade.py",
    "scripts\08_testes_etapa2.py",
    "scripts\09_exportar_etapa2.py"
)
foreach ($p in $passos) {
    Write-Host "==> $p" -ForegroundColor Cyan
    & $py $p
    if ($LASTEXITCODE -ne 0) { throw "Falha em $p (codigo $LASTEXITCODE)" }
}
Write-Host "Etapa 2 concluida." -ForegroundColor Green
