# Compila y corre las pruebas: pytest (gráficos, audio, charts y juego completo en PyBoy, modos DMG y CGB).
# Envoltorio de `uv run gbband test` (igual en macOS y Windows).
# Uso:  .\tests\run_tests.ps1 [--no-build] [--rapida] [--lista] [patron ...]
#   --rapida   tres canciones representativas (cambios del motor); sin ella, las diez
$root = Split-Path $PSScriptRoot -Parent
& uv run --project $root gbband test @args
exit $LASTEXITCODE
