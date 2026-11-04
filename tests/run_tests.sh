#!/usr/bin/env bash
# Compila y corre las pruebas: pytest (gráficos, audio, charts y juego completo en PyBoy, modos DMG y CGB).
# Envoltorio de `uv run gbband test`, que es igual en macOS y Windows (ver bandcore.testrun).
# Uso:  tests/run_tests.sh [--no-build] [--rapida] [--lista] [patron ...]
#   --rapida   tres canciones representativas (cambios del motor); sin ella, las diez
#   patron     filtra las pruebas por nombre (pytest -k); acepta comas: 'link,rom'
# Los bots de juego (perfecto, sin tocar, machacando) dejan resultado.txt y capturas en build/test-demo-<bot>-<dificultad>-<modo>.
exec uv run --project "$(cd "$(dirname "$0")/.." && pwd)" gbband test "$@"
