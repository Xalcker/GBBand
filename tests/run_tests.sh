#!/usr/bin/env bash
# Compila y corre las pruebas: pytest (conversor de graficos y pruebas del ROM en PyBoy, modos DMG y CGB).
# Uso:  ./tests/run_tests.sh [--no-build]
# Incluye los bots de juego (perfecto, sin tocar, machacando) en DMG y CGB; dejan resultado.txt y capturas en build/test-demo-<bot>-<dificultad>-<modo>.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "${1:-}" != "--no-build" ]; then "$root/build.sh"; fi
uv run --project "$root" pytest -q
