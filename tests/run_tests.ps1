# Compila y corre las pruebas: pytest (conversor de gráficos y pruebas del ROM en PyBoy, modos DMG y CGB).
# Uso:  .\tests\run_tests.ps1 [-NoBuild]
# (Las pruebas de juego con bots, resultado.txt y capturas por canción llegan con la fase 2.)
param([switch]$NoBuild)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $NoBuild) { & (Join-Path $root 'build.ps1'); if ($LASTEXITCODE -ne 0) { exit 1 } }
& uv run --project $root pytest -q
exit $LASTEXITCODE
