"""Charts de GBBand: el generador común está en bandcore (`bandcore.chart`, ahí se explica cómo se arma un chart).

Lo que cambia en la Game Boy: con la colocación B de las gemas (layout.py), dos notas del mismo carril necesitan una
separación mínima en píxeles (21, 18, 14 y 10 cuadros de fácil a experto). En los charts que se generan aquí,
`enforce_lane_gap` las mueve de carril o las quita; el chart compartido de NESBand (charts.json) no se toca: sus notas
muy juntas se dibujan alineadas a la fila (`aligned_frames`, el mapa `align_map` que va después del chart; ver
docs/decisiones.md, punto 29). Los charts van en binario (`chart_bytes`, `parse_chart`).
"""

from __future__ import annotations

from . import layout

# El generador de charts, la nota y las reglas de lo que se puede tocar son los mismos en los cuatro juegos:
# viven en bandcore (aquí se vuelven a exportar para el resto del juego)
from bandcore.chart import (  # noqa: F401
    BLOCKED_PAIRS,
    CHART_END,
    DIFFICULTIES,
    DRUM_BLOCKED_PAIRS,
    END_FLAG,
    KEYS_WINDOW,
    MAX_DELTA,
    MIN_SUSTAIN,
    ROLES,
    STAR_FIRST,
    STAR_FLAG,
    STAR_PHRASE_LEN,
    STAR_SPACING,
    SUSTAIN_FLAG,
    SUSTAIN_GAP,
    SUSTAIN_TRIM,
    BeatGrid,
    ChartNote,
    Difficulty,
    Note,
    arpeggio_pitch,
    assign_lanes,
    chart_entries,
    chart_size,
    check_playable,
    chord_masks,
    estimate_beat,
    lanes_clash,
    merge_attacks,
    reduce_notes,
    second_lane,
    star_notes,
    sustain_ends,
)


def build_chart(
    notes: list[Note],
    difficulty: Difficulty,
    grid: BeatGrid,
    lead_in: int,
    role: str = "lead",
    partner: list[Note] | None = None,
    stats: dict | None = None,
) -> list[ChartNote]:
    """El chart guarda cuadros, no filas: así sirve para cualquier velocidad de
    la autopista (el juego calcula en qué fila se dibuja cada nota).

    role es el papel del instrumento (ver ROLES) y partner las notas del otro canal de pulso,
    de donde sale la armonía de los acordes."""
    reduced = reduce_notes(merge_attacks(notes), difficulty, grid, role)
    stats = stats if stats is not None else {}
    # El contorno de la melodía manda en todos; el teclado mira un vecindario más corto (2 notas a cada
    # lado y no 4), así sus carriles siguen la melodía pero no son los mismos que los de la guitarra
    lanes = assign_lanes(reduced, difficulty.lanes, window=KEYS_WINDOW if role == "keys" else 4)
    masks = chord_masks(reduced, lanes, difficulty, grid, role, merge_attacks(partner or []))
    reduced, masks = enforce_lane_gap(reduced, masks, difficulty, move=True, stats=stats)
    # La cola ocupa tiles del carril: la siguiente gema del carril debe quedar a la separación mínima de la colocación B
    gap = layout.min_lane_gap_frames(layout.speed_8_8(difficulty.name), "B")
    ends = sustain_ends(reduced, [tuple(b for b in range(5) if mask >> b & 1) for mask in masks], gap)
    stars = star_notes(len(reduced), [mask & (mask - 1) != 0 for mask in masks])
    return [
        ChartNote(lead_in + note.frame, mask, None if end is None else lead_in + end, star)
        for note, mask, end, star in zip(reduced, masks, ends, stars)
    ]


def drawn_mask(mask: int, drums: bool) -> int:
    """Los carriles cuyas columnas ocupa la nota al dibujarse: en la batería el bombo (carril 4) es una barra que cruza
    los cinco, así que pisa las gemas de cualquier carril en sus filas."""
    return 0x1F if drums and mask & 0x10 else mask


def aligned_frames(chart: list[ChartNote], s: int, drums: bool = False) -> set[int]:
    """Cuadros de las notas que se dibujan alineadas a la fila (colocación A) en vez de con desplazamiento (B).

    Con la colocación B una gema puede ocupar dos filas de tiles, y dos gemas del mismo carril no pueden compartir un
    tile. El chart compartido (el de NESBand) trae notas del mismo carril más juntas que eso (hasta 5 cuadros en
    experto), así que esas se alinean a la fila: ocupan una sola y quedan a menos de 4 px de su lugar. Se repite
    hasta que no quede ningún par del mismo carril que se pise; si aun alineadas no caben, se dejan así (pasa con
    CAIDA DE NOTAS más lenta, no con la velocidad de cada dificultad)."""
    aligned: set[int] = set()
    for _ in range(len(chart) + 1):
        changed = False
        last: dict[int, tuple[int, set[int]]] = {}
        for note in chart:
            rows = set(layout.place(note.frame, s, "A" if note.frame in aligned else "B").rows)
            mask = drawn_mask(note.mask, drums)
            for lane in range(5):
                if not mask >> lane & 1:
                    continue
                if lane in last and last[lane][1] & rows:
                    prev = last[lane][0]
                    if note.frame not in aligned:
                        aligned.add(note.frame)
                        changed = True
                    elif prev not in aligned:
                        aligned.add(prev)
                        changed = True
                last[lane] = (note.frame, rows)
        if not changed:
            break
    return aligned


def chart_bytes(chart: list[ChartNote], s: int | None = None, drums: bool = False) -> bytes:
    """El chart tal como va en la ROM: pares (cuadros desde la entrada anterior, carriles) y el fin (0, $FF), y después
    el mapa de las notas alineadas (`align_map`), que la ROM lee con su propio cursor."""
    entries = chart_entries(chart)
    return bytes(b for entry in entries for b in entry) + align_map(entries, aligned_frames(chart, s, drums) if s else set())


def aligned_from_bytes(data: bytes) -> set[int]:
    """Inversa de align_map: los cuadros de las notas que el chart en binario (con su mapa) dibuja alineadas."""
    frames: list[tuple[int, bool]] = []
    frame = 0
    end = 0
    for i in range(0, len(data), 2):
        delta, mask = data[i], data[i + 1]
        if mask == CHART_END:
            end = i + 2
            break
        frame += delta
        if mask & 0x1F:
            frames.append((frame, bool(mask & END_FLAG)))
    bitmap = data[end:]
    return {f for i, (f, is_end) in enumerate(frames)
            if not is_end and i // 8 < len(bitmap) and bitmap[i // 8] >> (i % 8) & 1}


def align_map(entries: list[tuple[int, int]], aligned: set[int]) -> bytes:
    """Un bit por cada entrada con carriles (notas y fines de cola, en orden; los rellenos no cuentan): 1 = la nota se
    dibuja alineada a la fila (colocación A), 0 = con desplazamiento (B). El bit 0 de cada byte va primero. Se rellena
    a un número par de bytes para que el archivo siga siendo de pares."""
    bits = []
    frame = 0
    for delta, mask in entries:
        if mask == CHART_END:
            break
        frame += delta
        if mask & 0x1F:
            bits.append(not mask & END_FLAG and frame in aligned)
    data = bytearray((len(bits) + 7) // 8)
    for i, bit in enumerate(bits):
        if bit:
            data[i // 8] |= 1 << (i % 8)
    if len(data) % 2:
        data.append(0)
    return bytes(data)


def enforce_lane_gap(notes: list[Note], masks: list[int], difficulty: Difficulty, move: bool = True,
                     scheme: str = "B", stats: dict | None = None) -> tuple[list[Note], list[int]]:
    """Separa las gemas del mismo carril lo que pide la colocación (layout.min_lane_gap_frames).

    Una gema ocupa 1 o 2 filas de tiles y dos gemas no pueden compartir un tile, así que entre dos notas del
    mismo carril debe haber al menos `layout.min_lane_gap_frames` cuadros (21, 18, 14 y 11 de fácil a experto).
    Si el carril de una nota no está libre se pasa al más cercano que sí lo esté (`move`; en la batería los
    carriles son papeles y no se mueven); si no hay ninguno, se quita ese carril. Una nota que se queda sin
    carriles se quita. `stats` cuenta lo movido y lo quitado."""
    gap = layout.min_lane_gap_frames(layout.speed_8_8(difficulty.name), scheme)
    last: dict[int, int] = {}
    out_notes: list[Note] = []
    out_masks: list[int] = []
    for note, mask in zip(notes, masks):
        lanes = [b for b in range(5) if mask >> b & 1]
        kept: list[int] = []
        for lane in lanes:
            if note.frame - last.get(lane, -(10**9)) >= gap:
                kept.append(lane)
                continue
            replacement = None
            if move:
                for other in sorted(range(difficulty.lanes), key=lambda l: (abs(l - lane), l)):
                    taken = set(lanes) | set(kept)
                    if (other not in taken and note.frame - last.get(other, -(10**9)) >= gap
                            and not any({other, k} in BLOCKED_PAIRS for k in taken)):
                        replacement = other
                        break
            if replacement is not None:
                kept.append(replacement)
                if stats is not None:
                    stats["moved"] = stats.get("moved", 0) + 1
            elif stats is not None:
                stats["dropped"] = stats.get("dropped", 0) + 1
        if not kept:
            continue
        for lane in kept:
            last[lane] = note.frame
        out_notes.append(note)
        out_masks.append(sum(1 << l for l in kept))
    return out_notes, out_masks


def parse_chart(data: bytes) -> list[tuple[int, int]]:
    """Inversa de chart_bytes: las entradas (cuadro absoluto, byte de carriles y marcas), sin los rellenos."""
    entries = []
    frame = 0
    for i in range(0, len(data), 2):
        delta, mask = data[i], data[i + 1]
        if mask == CHART_END:
            break
        frame += delta
        if mask:
            entries.append((frame, mask))
    return entries
