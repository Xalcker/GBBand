"""Gráficos: convierte tiles dibujados como texto (.tiles) al formato 2bpp del Game Boy y genera una hoja
de contacto en PNG para revisarlos a simple vista.

Formato de un archivo .tiles (uno o varios por carpeta, p. ej. src/chr/):

    # comentario
    @20            <- número de tile en hexadecimal (el siguiente sin "@" usa el número siguiente)
    ........       <- 8 filas de 8 caracteres: '.' o '0' = color 0, '1', '2', '3' = colores 1 a 3
    ...

El formato 2bpp del GB entrelaza los planos por fila: por cada fila, un byte con el bit 0 de los 8 píxeles
y otro con el bit 1 (el bit 7 del byte es el píxel de la izquierda). Es distinto al del NES, donde van
primero los 8 bytes del plano 0 y luego los 8 del plano 1.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

TONES = (0xFF, 0xAA, 0x55, 0x00)  # colores 0 a 3 en la hoja de contacto: del más claro al más oscuro


def parse_tiles(text: str, source: str = "<texto>") -> dict[int, list[str]]:
    """Lee un .tiles y devuelve {número de tile: 8 filas de 8 caracteres}."""
    tiles: dict[int, list[str]] = {}
    number = 0
    rows: list[str] = []
    start = number
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";")[0].strip() if raw.lstrip().startswith("@") else raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            if rows:
                raise ValueError(f"{source}:{lineno}: el tile {start:#x} no tiene 8 filas")
            number = int(line[1:].split()[0], 16)
            continue
        if len(line) != 8 or any(c not in ".0123" for c in line):
            raise ValueError(f"{source}:{lineno}: fila inválida {line!r} (8 caracteres de '.0123')")
        if not rows:
            start = number
        rows.append(line)
        if len(rows) == 8:
            if start in tiles:
                raise ValueError(f"{source}:{lineno}: el tile {start:#x} está repetido")
            tiles[start] = rows
            rows = []
            number = start + 1
    if rows:
        raise ValueError(f"{source}: el último tile no tiene 8 filas")
    return tiles


def encode_tile(rows: list[str]) -> bytes:
    """Un tile de 8 filas a 16 bytes 2bpp."""
    out = bytearray()
    for row in rows:
        lo = hi = 0
        for i, c in enumerate(row):
            v = 0 if c == "." else int(c)
            lo |= (v & 1) << (7 - i)
            hi |= (v >> 1) << (7 - i)
        out += bytes((lo, hi))
    return bytes(out)


def build_2bpp(tiles: dict[int, list[str]]) -> bytes:
    """Todos los tiles desde el 0 hasta el más alto; los huecos quedan en blanco."""
    if not tiles:
        return b""
    data = bytearray(16 * (max(tiles) + 1))
    for number, rows in tiles.items():
        data[number * 16 : number * 16 + 16] = encode_tile(rows)
    return bytes(data)


def decode_2bpp(data: bytes) -> list[list[str]]:
    """Inversa de build_2bpp (para las pruebas): lista de tiles de 8 filas."""
    tiles = []
    for t in range(0, len(data), 16):
        rows = []
        for r in range(8):
            lo, hi = data[t + 2 * r], data[t + 2 * r + 1]
            rows.append("".join(str(((hi >> (7 - i)) & 1) << 1 | ((lo >> (7 - i)) & 1)) for i in range(8)))
        tiles.append(rows)
    return tiles


def write_png(path: Path, width: int, height: int, gray: bytes) -> None:
    """PNG de grises de 8 bits, solo con la biblioteca estándar."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + gray[y * width : (y + 1) * width] for y in range(height))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def contact_sheet(tiles: dict[int, list[str]], path: Path, scale: int = 4, per_row: int = 16) -> None:
    """Hoja con todos los tiles (su número se lee por posición: fila = número // 16, columna = número % 16).
    Las casillas vacías salen en rosa pálido de gris (0xE0) para distinguirlas del color 0 (blanco)."""
    count = max(tiles) + 1 if tiles else 0
    rows_n = (count + per_row - 1) // per_row
    cell = 8 * scale + 2  # 1 px de separación a cada lado
    width, height = per_row * cell, max(rows_n, 1) * cell
    canvas = bytearray([0x80]) * (width * height)
    for number in range(count):
        cx, cy = (number % per_row) * cell + 1, (number // per_row) * cell + 1
        art = tiles.get(number)
        for y in range(8 * scale):
            for x in range(8 * scale):
                if art is None:
                    value = 0xE0
                else:
                    c = art[y // scale][x // scale]
                    value = TONES[0 if c == "." else int(c)]
                canvas[(cy + y) * width + cx + x] = value
    write_png(path, width, height, bytes(canvas))


def build_dir(src: Path, out: Path) -> list[Path]:
    """Convierte cada .tiles de `src` en out/<nombre>.2bpp y out/<nombre>.png. Devuelve los .2bpp."""
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for file in sorted(src.glob("*.tiles")):
        tiles = parse_tiles(file.read_text(encoding="utf-8"), file.name)
        target = out / (file.stem + ".2bpp")
        target.write_bytes(build_2bpp(tiles))
        contact_sheet(tiles, out / (file.stem + ".png"))
        made.append(target)
    return made
