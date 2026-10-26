"""Genera src/chr/gems.tiles: las gemas de los 5 carriles con sus 4 variantes de desplazamiento vertical.

    uv run gbband build-gems

Cada gema mide 16x8 px (2 tiles de ancho) y lleva en el fondo las líneas del carril (columnas 0 y 15, color 1).
Las formas son distintas por carril para que se distingan sin color (en DMG):
  verde ◀ · rojo ▼ · amarillo ▶ · azul anillo · naranja rombo

Tiles por carril (14), desde TILE_GEM + 14*carril:
  0-1    desplazamiento 0 (un tile de alto: izquierda, derecha)
  2-5    desplazamiento 2: arriba izq, arriba der, abajo izq, abajo der
  6-9    desplazamiento 4
  10-13  desplazamiento 6
La colocación A solo usa los tiles 0-1 de cada carril.
"""

from __future__ import annotations

TILE_GEM = 0x60
GEM_STRIDE = 14

# Símbolo de cada carril en la parte de adentro (6 filas x 12 columnas): {fila 1..6: [(col_ini, col_fin)]}
SYMBOLS = {
    0: {1: [(8, 9)], 2: [(6, 9)], 3: [(4, 9)], 4: [(4, 9)], 5: [(6, 9)], 6: [(8, 9)]},  # verde: flecha izquierda
    1: {1: [(1, 10)], 2: [(2, 9)], 3: [(3, 8)], 4: [(4, 7)], 5: [(5, 6)]},  # rojo: flecha abajo
    2: {1: [(2, 3)], 2: [(2, 5)], 3: [(2, 7)], 4: [(2, 7)], 5: [(2, 5)], 6: [(2, 3)]},  # amarillo: flecha derecha
    3: {1: [(4, 7)], 2: [(3, 3), (8, 8)], 3: [(3, 3), (8, 8)], 4: [(3, 3), (8, 8)], 5: [(3, 3), (8, 8)], 6: [(4, 7)]},  # azul: anillo
    4: {1: [(5, 6)], 2: [(4, 7)], 3: [(3, 8)], 4: [(3, 8)], 5: [(4, 7)], 6: [(5, 6)]},  # naranja: rombo
}

BG_LEFT = "1......."  # línea del carril, mitad izquierda
BG_RIGHT = ".......1"


def gem_art(lane: int) -> list[str]:
    """La gema completa: 8 filas de 16 caracteres."""
    rows = ["1." + "3" * 12 + ".1"]
    for r in range(1, 7):
        inner = ["2"] * 12
        for a, b in SYMBOLS[lane].get(r, []):
            for c in range(a, b + 1):
                inner[c] = "1"
        rows.append("13" + "".join(inner) + "31")
    rows.append(rows[0])
    return rows


def shifted_tiles(art: list[str], k: int) -> tuple[list[str], list[str], list[str], list[str]]:
    """(arriba izq, arriba der, abajo izq, abajo der) con la gema desplazada k px hacia abajo."""
    top, bottom = [], []
    for r in range(8):
        top.append(art[r - k] if r >= k else BG_LEFT + BG_RIGHT)
        bottom.append(art[8 - k + r] if r < k else BG_LEFT + BG_RIGHT)
    return (
        [row[:8] for row in top],
        [row[8:] for row in top],
        [row[:8] for row in bottom],
        [row[8:] for row in bottom],
    )


TILE_METER = 0x10  # cinco pares de tiles (sprite 8x16): el medidor con 0, 4, 8, 12 y 16 px llenos


def meter_tiles() -> list[tuple[str, list[str]]]:
    """Un segmento de medidor (8x16 px, marco a los lados) lleno de abajo hacia arriba en 0, 4, 8, 12 o 16 px."""
    tiles = []
    for level in range(5):
        fill = 4 * level
        rows = []
        for r in range(16):
            rows.append("3222222" + "3" if r >= 16 - fill else "3......3")
        tiles += [(f"medidor nivel {level} arriba", rows[:8]), (f"medidor nivel {level} abajo", rows[8:])]
    return tiles


TILE_BAR = 0xA6  # el bombo de la batería: una barra que cruza los 5 carriles


def bar_tiles() -> list[tuple[str, list[str]]]:
    """Los 13 tiles de la barra (se repiten en los 10 tiles del ancho de la autopista): uno lleno y, por cada desplazamiento
    de 2, 4 y 6 px, arriba y abajo en su versión de tile izquierdo (línea de carril en la columna 0) y derecho."""
    art = ["33333333", "22222222", "22222222", "11111111", "11111111", "22222222", "22222222", "33333333"]
    tiles = [("barra llena", art)]
    for k in (2, 4, 6):
        for side, blank in (("izq", BG_LEFT), ("der", BG_RIGHT)):
            tiles.append((f"barra desp {k} arriba {side}", [art[r - k] if r >= k else blank for r in range(8)]))
        for side, blank in (("izq", BG_LEFT), ("der", BG_RIGHT)):
            tiles.append((f"barra desp {k} abajo {side}", [art[8 - k + r] if r < k else blank for r in range(8)]))
    return tiles


def build_gems_tiles() -> str:
    lines = [
        "# Generado por `gbband build-gems` - no editar a mano",
        "# 5 carriles x 14 tiles (ver pctools/gbband_tools/gemgen.py)",
        "",
    ]
    for lane in range(5):
        art = gem_art(lane)
        base = TILE_GEM + GEM_STRIDE * lane
        names = ["verde", "rojo", "amarillo", "azul", "naranja"]
        tl, tr, _, _ = shifted_tiles(art, 0)
        tiles = [("desp 0 izq", tl), ("desp 0 der", tr)]
        for k in (2, 4, 6):
            a, b, c, d = shifted_tiles(art, k)
            tiles += [(f"desp {k} arriba izq", a), (f"desp {k} arriba der", b), (f"desp {k} abajo izq", c), (f"desp {k} abajo der", d)]
        lines.append(f"@{base:02X}  ; {names[lane]}: {tiles[0][0]}")
        for i, (name, rows) in enumerate(tiles):
            if i:
                lines.append(f"# {names[lane]}: {name}")
            lines += rows
    lines.append(f"@{TILE_METER:02X}  ; medidores (sprites 8x16: vida y poder estelar)")
    for name, rows in meter_tiles():
        lines.append(f"# {name}")
        lines += rows
    lines.append(f"@{TILE_BAR:02X}  ; el bombo: barra naranja a lo ancho de los carriles")
    for name, rows in bar_tiles():
        lines.append(f"# {name}")
        lines += rows
    return "\n".join(lines) + "\n"
