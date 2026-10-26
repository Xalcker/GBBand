"""Mide las colocaciones A y B con los charts reales de NESBand (reference/NESBand/src/songs/*/chart.s).

    uv run gbband measure-placement

Para cada dificultad compara: error visual máximo y medio (en píxeles y en cuadros), tiles de VRAM y cuántas
notas del mismo carril se pisarían (conflictos) con cada colocación.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import layout

LABEL = re.compile(r"^chart_(\w+?)_(guitarra|teclado|bajo|bateria)_(facil|medio|dificil|experto):")
BYTES = re.compile(r"\.byte\s+(\d+),\s*\$([0-9A-Fa-f]+)")
END_FLAG = 0x80
LANE_BITS = 0x1F


def parse_charts(path: Path) -> dict[tuple[str, str, str], list[tuple[int, int]]]:
    """{(canción, instrumento, dificultad): [(cuadro, máscara de carriles)]} sin las entradas de fin de cola."""
    charts: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
    current = None
    frame = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LABEL.match(line)
        if m:
            current = charts.setdefault(m.groups(), [])
            frame = 0
            continue
        b = BYTES.search(line)
        if b and current is not None:
            delta, mask = int(b.group(1)), int(b.group(2), 16)
            if mask == 0xFF:  # fin del chart
                current = None
                continue
            frame += delta
            if mask & END_FLAG or not mask & LANE_BITS:
                continue
            current.append((frame, mask & LANE_BITS))
    return charts


def measure(reference: Path, instruments=("guitarra", "teclado", "bajo")) -> str:
    songs = sorted((reference / "src" / "songs").glob("*/chart.s"))
    charts = {}
    for chart_file in songs:
        charts.update(parse_charts(chart_file))
    lines = [f"Canciones: {len(songs)}; charts: {len(charts)} (instrumentos: {', '.join(instruments)})", ""]
    lines.append("dificultad  px/cuadro  esquema  tiles  error max px (cuadros)  error medio px  notas  conflictos (%)")
    for diff in layout.DIFFICULTIES:
        s = layout.speed_8_8(diff)
        notes = [n for (song, inst, d), ch in charts.items() if d == diff and inst in instruments for n in [ch]]
        total = sum(len(ch) for ch in notes)
        for scheme in "AB":
            errs = [abs(layout.error_px(f, s, scheme)) for ch in notes for f, _ in ch]
            confl = sum(layout.conflicts(ch, s, scheme) for ch in notes)
            px = s / 256
            lines.append(
                f"{diff:<10}  {px:9.3f}  {scheme:^7}  {layout.tiles_used(scheme):5}  "
                f"{max(errs):8.2f} ({max(errs) / px:5.1f})        {sum(errs) / len(errs):8.2f}   "
                f"{total:6}  {confl:6} ({100 * confl / total:5.2f} %)"
            )
    return "\n".join(lines)
