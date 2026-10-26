#!/usr/bin/env bash
# Compila la ROM: src/main.asm -> build/gbband.gb (+ .sym y .map con símbolos para depurar)
# Uso:  ./build.sh
#       ./build.sh --release [--version 0.1.0]
# --release arma la ROM para publicar en build/release/gbband-v<versión>.gb con su suma de verificación
#   (.sha256) y la licencia. La versión sale del archivo VERSION si no se indica.
# NOMBRE=prueba ./build.sh deja build/gbband-prueba.gb sin pisar build/gbband.gb.
# SOLO="patron1,patron2" queda reservado para compilar un subconjunto de canciones (fase 3); por ahora no hace nada.
# (Mismas opciones que build.ps1: -Release, -Version, -Nombre, -Solo.)
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

release=0
version=""
while [ $# -gt 0 ]; do
    case "$1" in
        --release) release=1 ;;
        --version) version="$2"; shift ;;
        *) echo "Opcion desconocida: $1" >&2; exit 1 ;;
    esac
    shift
done
nombre="${NOMBRE:-}"
if [ $release -eq 1 ] && [ -z "$version" ]; then version="$(head -n 1 "$root/VERSION" | tr -d '[:space:]')"; fi

# RGBDS de tools/rgbds si existe; si no, el del PATH (brew install rgbds)
buscar() { if [ -x "$root/tools/rgbds/$1" ]; then echo "$root/tools/rgbds/$1"; else echo "$1"; fi; }
rgbasm="$(buscar rgbasm)"; rgblink="$(buscar rgblink)"; rgbfix="$(buscar rgbfix)"

[ -n "${SOLO:-}" ] && echo "SOLO aun no hace nada (no hay lista de canciones)"

if [ $release -eq 1 ]; then out="$root/build/release"; else out="$root/build"; fi
mkdir -p "$out"
if [ $release -eq 1 ]; then base="gbband-v$version"; elif [ -n "$nombre" ]; then base="gbband-$nombre"; else base="gbband"; fi

# Graficos: src/chr/*.tiles -> build/chr/*.2bpp (y PNG de contacto para revisarlos)
uv run --project "$root" gbband build-gfx > /dev/null

obj="$out/$base.o"
"$rgbasm" -I "$root/src" -I "$root/build" -o "$obj" "$root/src/main.asm"
rom="$out/$base.gb"
"$rgblink" -n "$out/$base.sym" -m "$out/$base.map" -p 0xFF -o "$rom" "$obj"
# Header: logo y sumas (-v), relleno $FF (-p), compatible con CGB (-c), no japones (-j), MBC5 con 8 KB de SRAM con bateria
"$rgbfix" -v -p 0xFF -c -j -t GBBAND -m MBC5+RAM+BATTERY -r 2 "$rom"
rm -f "$obj"

if [ $release -eq 1 ]; then
    hash="$( (sha256sum "$rom" 2>/dev/null || shasum -a 256 "$rom") | cut -d' ' -f1)"
    printf '%s  %s\n' "$hash" "$base.gb" > "$rom.sha256"
    cp "$root/LICENSE" "$out/LICENSE"
    echo "Release: $rom ($hash)"
else
    echo "OK: $rom ($(wc -c < "$rom" | tr -d ' ') bytes)"
fi
