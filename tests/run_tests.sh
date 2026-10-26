#!/usr/bin/env bash
# Compila y corre las pruebas: pytest (conversor de graficos y pruebas del ROM en PyBoy, modos DMG y CGB).
# Uso:  ./tests/run_tests.sh [--no-build]
# (Las pruebas de juego con bots, resultado.txt y capturas por cancion llegan con la fase 2.)
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "${1:-}" != "--no-build" ]; then "$root/build.sh"; fi
uv run --project "$root" pytest -q
