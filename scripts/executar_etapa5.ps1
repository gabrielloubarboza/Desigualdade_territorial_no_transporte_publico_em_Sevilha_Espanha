# Reconstroi os produtos finais (Etapa 5) a partir da raiz do projeto:
#   powershell -ExecutionPolicy Bypass -File scripts\executar_etapa5.ps1
# Pre-requisito: Etapas 1 a 4 no banco sevilla_oferta_bus. QGIS e opcional (verificacao/estilos dos GeoPackages).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"

$passos = @(
    "scripts\16_geopackages_finales.py",
    "scripts\17_figuras.py",
    "scripts\18_informe_pdf.py",
    "scripts\19_codigo_em_destaque.py",
    "scripts\20_verificacion_productos.py"
)
foreach ($p in $passos) {
    Write-Host "==> $p" -ForegroundColor Cyan
    & $py $p
    if ($LASTEXITCODE -ne 0) { throw "Falha em $p (codigo $LASTEXITCODE)" }
}
Write-Host "Etapa 5 concluida." -ForegroundColor Green
