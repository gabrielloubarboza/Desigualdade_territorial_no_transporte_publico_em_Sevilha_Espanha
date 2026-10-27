# Reconstroi a Etapa 4 (diagnostico territorial e prioridades) a partir da raiz do projeto:
#   powershell -ExecutionPolicy Bypass -File scripts\executar_etapa4.ps1
# Pre-requisito: Etapas 1 a 3 carregadas no banco sevilla_oferta_bus.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"

$passos = @(
    "scripts\13_diagnostico.py",
    "scripts\14_testes_etapa4.py",
    "scripts\15_exportar_etapa4.py"
)
foreach ($p in $passos) {
    Write-Host "==> $p" -ForegroundColor Cyan
    & $py $p
    if ($LASTEXITCODE -ne 0) { throw "Falha em $p (codigo $LASTEXITCODE)" }
}
Write-Host "Etapa 4 concluida." -ForegroundColor Green
