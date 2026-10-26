"""Genera src/chr/font.tiles (las letras del juego) a partir de Bongo-8 Mono (Caffinate / Nathan Scott, CC0).

    uv run gbband build-font

Necesita Pillow (grupo `dev` del proyecto). El resultado se versiona, así que compilar el ROM no lo necesita.
Cada carácter ocupa el tile de su código ASCII y se dibuja en color 3 (el más oscuro). Solo hay mayúsculas,
dígitos y signos: los textos del juego van sin acentos.
"""

from __future__ import annotations

from pathlib import Path

FONT_CHARS = " !\"#%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def glyphs_from_ttf(path: Path, size: int = 8) -> dict[str, list[str]]:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(path), size)
    glyphs = {}
    for ch in FONT_CHARS:
        image = Image.new("L", (8, 8), 0)
        draw = ImageDraw.Draw(image)
        draw.fontmode = "1"
        draw.text((0, 0), ch, font=font, fill=255)
        glyphs[ch] = ["".join("3" if image.getpixel((x, y)) else "." for x in range(8)) for y in range(8)]
    return glyphs


def build_font_tiles(glyphs: dict[str, list[str]], source: str) -> str:
    lines = [
        f"# Generado por `gbband build-font` desde {source} - no editar a mano",
        "# Un tile por carácter (su número es su código ASCII), en color 3.",
        "",
    ]
    for ch in FONT_CHARS:
        lines.append(f"@{ord(ch):02X}  ; {ch!r}")
        lines += glyphs[ch]
    return "\n".join(lines) + "\n"
