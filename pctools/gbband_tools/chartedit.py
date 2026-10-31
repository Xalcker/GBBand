"""Lógica del editor de charts, sin interfaz: leer los charts exportados, aplicar ediciones manuales y validar.

Aplicar y validar ediciones es lo de bandcore (`bandcore.chartedit`, igual en los cuatro juegos; ahí está el formato
de edits.json). Aquí queda lo propio de la Game Boy: leer los charts que ya están en src/songs/<canción>/ en binario.
Las notas se identifican por su cuadro (el mismo de los charts, contando la entrada de la autopista).
"""

from __future__ import annotations

import re
from pathlib import Path

from bandcore.chartedit import (  # noqa: F401  (el resto de GBBand los usa como chartedit.<nombre>)
    EDITS_FILE,
    EDITS_VERSION,
    KICK_MASK,
    LANE_MASK,
    MAX_DRUM_BUTTONS,
    MAX_DRUM_HANDS,
    TOM_MASK,
    apply_edits,
    chart_from_json,
    chart_problems,
    diff_charts,
    dump_edits,
    lanes_of,
    load_edits,
    save_edits,
    validate_chart,
)

from .chart import CHART_END, END_FLAG, STAR_FLAG, SUSTAIN_FLAG, ChartNote

# --- Leer los charts -------------------------------------------------------------------


def parse_chart_bytes(data: bytes) -> list[tuple[int, int]]:
    """Las entradas (cuadros desde la anterior, carriles) de un chart en binario, hasta el fin ($FF)."""
    return [(data[i], data[i + 1]) for i in range(0, len(data), 2)]


def entries_to_chart(entries: list[tuple[int, int]], drums: bool = False) -> list[ChartNote]:
    """Inverso de chart.chart_entries: del formato del juego a notas con su cola y su frase estelar.
    En la batería el bit $40 es un platillo (no hay colas)."""
    notes: list[dict] = []
    open_notes: list[dict] = []  # notas con cola esperando su entrada de fin
    frame = 0
    for delta, mask in entries:
        if mask == CHART_END:
            break
        frame += delta
        if mask == 0:  # relleno: solo avanza el tiempo
            continue
        if mask & END_FLAG:
            release = mask & LANE_MASK
            for note in list(open_notes):
                if note["mask"] & ~release == 0:
                    note["end"] = frame
                    release &= ~note["mask"]
                    open_notes.remove(note)
            continue
        note = {"frame": frame, "mask": mask & LANE_MASK, "end": None, "star": bool(mask & STAR_FLAG),
                "cymbal": drums and bool(mask & SUSTAIN_FLAG)}
        notes.append(note)
        if mask & SUSTAIN_FLAG and not drums:
            open_notes.append(note)
    return [ChartNote(n["frame"], n["mask"], n["end"], n["star"], n["cymbal"]) for n in notes]


INSTRUMENT_NAMES = ("guitarra", "teclado", "bajo", "bateria")


def read_song_charts(song_dir: Path) -> dict[str, list[ChartNote]]:
    """Los charts de src/songs/<canción>/chart_<instrumento>_<dificultad>.bin, por clave "instrumento/dificultad"."""
    result: dict[str, list[ChartNote]] = {}
    for path in sorted(song_dir.glob("chart_*.bin")):
        match = re.fullmatch(r"chart_(\w+?)_(\w+)\.bin", path.name)
        if match:
            result[f"{match.group(1)}/{match.group(2)}"] = entries_to_chart(
                parse_chart_bytes(path.read_bytes()), match.group(1) == "bateria")
    return result
