"""Representación intermedia (IR) de una canción, independiente de la plataforma de destino.

De la IR salen, por separado, los charts (`chart.py`, que solo mira notas) y el audio de la Game Boy
(`gbaudio.py`, que mira cada cuadro). Las fuentes de la IR son:
  - un proyecto de texto de FamiStudio (`famitext.py`), que trae las notas exactas, o
  - las escrituras al APU de un NSF corridas en un emulador 6502 (`nsf.py`).

Todo se mide en cuadros del NES (60.1 Hz). En la Game Boy 1 cuadro NES = 1 cuadro GB (59.7 Hz): la canción queda
0.6 % más lenta y charts y audio comparten el mismo eje sin conversión (docs/diseno.md).

Convenciones (las de NESBand):
  - canales: "Square1", "Square2", "Triangle", "Noise", "DPCM"
  - duty: 0 = 12.5 %, 1 = 25 %, 2 = 50 %, 3 = 75 %
  - volumen: 0 a 15
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bandcore.chart import Note  # noqa: F401  (la misma en los cuatro juegos)

from bandcore.nesapu import (  # noqa: F401  (la misma clase que graba el APU del NES)
    Track,
)

CHANNELS = ("Square1", "Square2", "Triangle", "Noise", "DPCM")
TONAL = ("Square1", "Square2", "Triangle")
DRUM_CHANNELS = ("Noise", "DPCM")
NES_CPU_HZ = 1_789_773
NES_FPS = 60.0988

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(pitch: int) -> str:
    """60 -> "C4"."""
    return f"{_NAMES[pitch % 12]}{pitch // 12 - 1}"


def midi_hz(pitch: float) -> float:
    return 440.0 * 2 ** ((pitch - 69) / 12)


def hz_midi(freq: float) -> float:
    import math

    return 69 + 12 * math.log2(freq / 440.0)


@dataclass
class SongIR:
    name: str
    game: str
    length_frames: int
    tracks: dict[str, Track]  # canales tonales
    notes: dict[str, list[Note]]  # los 5 canales, para los charts
    frames_per_beat: int | None = None  # None si la fuente no trae tempo (un NSF): se estima con chart.estimate_beat
    source: str = ""
    log: list[str] = field(default_factory=list)  # avisos de la importación (se imprimen y se guardan)

    def warn(self, text: str) -> None:
        if text not in self.log:
            self.log.append(text)

    def onsets(self) -> list[int]:
        return [n.frame for ch in self.notes.values() for n in ch]
