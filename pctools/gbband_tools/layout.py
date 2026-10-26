"""Colocación de las notas en el fondo: modelo en Python de lo que hace la ROM, para medirlo y para revisar charts.

La autopista cae por scroll vertical. Una nota del cuadro F está en la línea de golpe (y = HIT_Y) cuando suena
y antes está F*s píxeles más arriba, con s = velocidad en px/cuadro (punto fijo 8.8). Su posición en el fondo
de 256 px, en punto fijo 8.8:  y_fix = HIT_Y*256 - F*s   (se toma módulo 65536: el fondo da la vuelta a los 256 px).

Colocación A (como NESBand): la gema ocupa una sola fila de tiles; su posición se redondea a múltiplos de 8 px.
Colocación B: la gema tiene 4 variantes con desplazamiento vertical de 0, 2, 4 y 6 px y puede cruzar dos filas
de tiles; la posición se redondea a múltiplos de 2 px.

Dos gemas del mismo carril no pueden compartir un tile (el tile de una variante dibuja una sola gema), así que
`conflicts` cuenta los pares de notas del mismo carril que se pisarían.
"""

from __future__ import annotations

from dataclasses import dataclass

HIT_Y = 120  # y (en pantalla) de la parte de arriba de la gema cuando suena: fila de tiles 15, pegada a la Window
TRAVEL = 120  # píxeles que recorre una nota desde el borde de arriba hasta la línea de golpe
FPS = 59.7275  # 70224 ciclos T por cuadro a 4 194 304 Hz
LANES = 5
ANTICIPATION = {"facil": 2.6, "medio": 2.2, "dificil": 1.7, "experto": 1.3}  # segundos (igual que NESBand)
DIFFICULTIES = list(ANTICIPATION)


def speed_8_8(difficulty: str) -> int:
    """Velocidad de caída en px/cuadro, punto fijo 8.8: TRAVEL píxeles en `anticipación` segundos."""
    return round(TRAVEL * 256 / (ANTICIPATION[difficulty] * FPS))


def y_fix(frame: int, s: int) -> int:
    """Posición de la parte de arriba de la gema en el fondo (8.8, sin módulo: puede ser negativa)."""
    return HIT_Y * 256 - frame * s


@dataclass(frozen=True)
class Placement:
    row: int  # fila de tiles de arriba de la gema (módulo 32 al escribirla en el mapa)
    offset: int  # píxeles de desplazamiento dentro de esa fila (0 a 7; en B solo pares)
    rows: tuple[int, ...]  # filas de tiles que ocupa (1 en A; 1 o 2 en B)


def place(frame: int, s: int, scheme: str) -> Placement:
    y = y_fix(frame, s)
    if scheme == "A":
        row = (y + 4 * 256) >> 11  # fila más cercana
        return Placement(row, 0, (row,))
    if scheme == "B":
        y2 = (y + 256) >> 9  # posición en pasos de 2 px (redondeo al más cercano)
        row, offset = y2 >> 2, (y2 & 3) * 2
        return Placement(row, offset, (row,) if offset == 0 else (row, row + 1))
    raise ValueError(scheme)


def drawn_y(p: Placement) -> int:
    """Posición de la parte de arriba de la gema, en píxeles del fondo, tal como queda dibujada."""
    return p.row * 8 + p.offset


def error_px(frame: int, s: int, scheme: str) -> float:
    """Error visual en píxeles: dibujada menos ideal."""
    return drawn_y(place(frame, s, scheme)) - y_fix(frame, s) / 256


def conflicts(notes: list[tuple[int, int]], s: int, scheme: str, tile_rows: bool = True) -> int:
    """Pares consecutivos de notas del mismo carril cuyas gemas comparten una fila de tiles.
    `notes` = [(cuadro, máscara de carriles)]. Una nota con conflicto no se puede dibujar bien."""
    last: dict[int, set[int]] = {}
    count = 0
    for frame, mask in notes:
        rows = set(place(frame, s, scheme).rows)
        for lane in range(LANES):
            if mask >> lane & 1:
                if lane in last and last[lane] & rows:
                    count += 1
                last[lane] = rows
    return count


def min_lane_gap_frames(s: int, scheme: str) -> int:
    """Separación mínima segura (en cuadros) entre dos notas del mismo carril: 1 fila en A, 2 en B (peor caso:
    16 px, porque una gema B puede cruzar dos filas)."""
    px = 8 if scheme == "A" else 16
    return -(-px * 256 // s)  # techo


def tiles_used(scheme: str) -> int:
    """Tiles de gemas en VRAM: A = 2 por carril; B = 2 + 3 variantes de 4 tiles = 14 por carril."""
    return LANES * (2 if scheme == "A" else 14)
