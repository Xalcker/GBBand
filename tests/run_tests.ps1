# Compila y corre las pruebas: pytest (gráficos, stream de audio, charts y juego completo en PyBoy, modos DMG y CGB).
# Uso:  .\tests\run_tests.ps1 [-NoBuild]
# Incluye los bots de juego (perfecto, sin tocar, machacando) en DMG y CGB; dejan resultado.txt y capturas en build\test-demo-<bot>-<dificultad>-<modo>.
param([switch]$NoBuild)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $NoBuild) { & (Join-Path $root 'build.ps1'); if ($LASTEXITCODE -ne 0) { exit 1 } }
& uv run --project $root pytest -q
exit $LASTEXITCODE
