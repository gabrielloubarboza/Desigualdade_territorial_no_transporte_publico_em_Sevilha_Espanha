# Regenera figuras, PDF e codigo em destaque a partir dos GeoPackages de produtos/ e dos CSV de resultados/,
# SEM acessar o PostgreSQL:
#   powershell -ExecutionPolicy Bypass -File scripts\gerar_produtos_visuais.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"

foreach ($p in @("scripts\17_figuras.py", "scripts\18_informe_pdf.py", "scripts\19_codigo_em_destaque.py")) {
    Write-Host "==> $p" -ForegroundColor Cyan
    & $py $p
    if ($LASTEXITCODE -ne 0) { throw "Falha em $p (codigo $LASTEXITCODE)" }
}
Write-Host "==> scripts\20_verificacion_productos.py --sin-bd" -ForegroundColor Cyan
& $py scripts\20_verificacion_productos.py --sin-bd
if ($LASTEXITCODE -ne 0) { throw "Falha na verificacao (codigo $LASTEXITCODE)" }
Write-Host "Produtos visuais regenerados." -ForegroundColor Green
