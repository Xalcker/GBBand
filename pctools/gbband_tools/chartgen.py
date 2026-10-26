"""Charts de la fase 2: un generador sencillo de un solo instrumento (la melodía) para la canción de prueba.

En la fase 3 se porta el generador completo de NESBand (contorno, acordes, colas, frases estelares) para que
lea la IR. Aquí solo hace falta algo que produzca charts jugables en las 4 dificultades y que respete la
colocación B: dos notas del mismo carril deben estar separadas lo suficiente para no compartir tiles
(`layout.conflicts`).

Formato del chart (el de NESBand, 2 bytes por entrada): (cuadros desde la entrada anterior, máscara de carriles).
Bits 0-4 = carriles; $20 = frase estelar, $40 = nota con cola (o platillo), $80 = fin de una cola. Fin del chart:
(0, $FF). Si dos entradas están a más de 255 cuadros se intercalan entradas de relleno (0 carriles).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import layout

CHART_END = 0xFF
MAX_DELTA = 255


@dataclass(frozen=True)
class Difficulty:
    name: str
    lanes: int  # carriles que usa (desde el verde)
    min_gap: int  # cuadros mínimos entre dos notas (igual que NESBand)


DIFFICULTIES = [
    Difficulty("facil", 3, 24),
    Difficulty("medio", 4, 14),
    Difficulty("dificil", 5, 9),
    Difficulty("experto", 5, 5),
]


def reduce_notes(notes: list[tuple[int, int]], min_gap: int, beat: int) -> list[tuple[int, int]]:
    """Quita notas demasiado juntas conservando primero las del tiempo. `notes` = [(cuadro, altura)]."""
    keep: list[tuple[int, int]] = []
    for frame, pitch in notes:
        if keep and frame - keep[-1][0] < min_gap:
            # compiten: gana la que cae en el tiempo (o la que ya estaba)
            if frame % beat == 0 and keep[-1][0] % beat != 0:
                keep[-1] = (frame, pitch)
            continue
        keep.append((frame, pitch))
    return keep


def assign_lanes(notes: list[tuple[int, int]], lanes: int, scheme: str, s: int) -> list[tuple[int, int]]:
    """Carril de cada nota según su altura (la más grave a la izquierda), evitando que dos notas del mismo
    carril queden más cerca de lo que permite la colocación. Devuelve [(cuadro, máscara)]."""
    if not notes:
        return []
    lo = min(p for _, p in notes)
    hi = max(p for _, p in notes)
    gap = layout.min_lane_gap_frames(s, scheme)
    last_use: dict[int, int] = {}
    chart: list[tuple[int, int]] = []
    for frame, pitch in notes:
        want = round((pitch - lo) / max(hi - lo, 1) * (lanes - 1))
        for lane in sorted(range(lanes), key=lambda l: (abs(l - want), l)):
            if frame - last_use.get(lane, -10_000) >= gap:
                last_use[lane] = frame
                chart.append((frame, 1 << lane))
                break
        # si ningún carril está libre, la nota se descarta
    return chart


def make_chart(melody: list[tuple[int, int]], difficulty: Difficulty, beat: int, scheme: str = "B") -> list[tuple[int, int]]:
    """Chart (cuadro, máscara) de una dificultad a partir de la melodía [(cuadro, altura)]."""
    s = layout.speed_8_8(difficulty.name)
    return assign_lanes(reduce_notes(melody, difficulty.min_gap, beat), difficulty.lanes, scheme, s)


def chart_entries(chart: list[tuple[int, int]]) -> list[tuple[int, int]]:
    entries: list[tuple[int, int]] = []
    previous = 0
    for frame, mask in sorted(chart):
        delta = frame - previous
        while delta > MAX_DELTA:
            entries.append((MAX_DELTA, 0))
            delta -= MAX_DELTA
        entries.append((delta, mask))
        previous = frame
    entries.append((0, CHART_END))
    return entries


def chart_bytes(chart: list[tuple[int, int]]) -> bytes:
    return bytes(b for entry in chart_entries(chart) for b in entry)


def parse_chart(data: bytes) -> list[tuple[int, int]]:
    """Inversa de chart_bytes: [(cuadro, máscara)] sin las entradas de relleno."""
    notes = []
    frame = 0
    for i in range(0, len(data), 2):
        delta, mask = data[i], data[i + 1]
        if mask == CHART_END:
            break
        frame += delta
        if mask:
            notes.append((frame, mask))
    return notes


def check_playable(chart: list[tuple[int, int]]) -> None:
    """Un control de GB no deja apretar ← y → a la vez (verde + amarillo), ni queremos amarillo + naranja
    (con ESPEJO sería verde + amarillo)."""
    for frame, mask in chart:
        lanes = {b for b in range(5) if mask >> b & 1}
        if {0, 2} <= lanes or {2, 4} <= lanes:
            raise ValueError(f"acorde imposible en el cuadro {frame}: carriles {sorted(lanes)}")


def check_layout(chart: list[tuple[int, int]], difficulty: str, scheme: str = "B") -> None:
    """Falla si dos gemas del mismo carril compartirían un tile."""
    n = layout.conflicts(chart, layout.speed_8_8(difficulty), scheme)
    if n:
        raise ValueError(f"{n} pares de notas del mismo carril se pisan en la colocación {scheme}")
