"""Stream de registros por cuadro ("FRS", versión 1) del APU de la Game Boy.

El audio de GBBand es una lista de escrituras a registros del APU, un registro por cuadro. Un cuadro de música
es un cuadro de juego, así que charts y audio comparten el mismo índice.

Registro de un cuadro:

    byte H
      bit 7 = 1   "cuadros vacíos": bits 0-6 = N-1, N de 1 a 128 cuadros sin cambios
      bit 7 = 0   bits 0-3 = canales presentes (CH1..CH4); bit 4 = NR50 y NR51 siguen (2 bytes);
                  bit 5 = wave RAM sigue (16 bytes); bit 6 = fin del stream
    por cada canal presente (en orden CH1..CH4):
      byte M      máscara de registros que se escriben (bit k = NRx<k>; CH2 y CH4 no tienen NRx0)
      los valores en bruto, en orden x0..x4 (NRx4 siempre al final)

Un canal "presente" con M = 0 es válido pero inútil; el codificador no lo genera.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Dirección base de NRx0 de cada canal (CH2 y CH4 no tienen NRx0: su bit 0 no se usa y su NRx1 cae en base+1)
CHANNEL_BASE = (0xFF10, 0xFF15, 0xFF1A, 0xFF1F)
NR_REG_NAMES = ("NR10", "NR11", "NR12", "NR13", "NR14", "NR21", "NR22", "NR23", "NR24", "NR30", "NR31",
                "NR32", "NR33", "NR34", "NR41", "NR42", "NR43", "NR44")

END_FLAG = 0x40
WAVE_FLAG = 0x20
MASTER_FLAG = 0x10
EMPTY_FLAG = 0x80
MAX_EMPTY_RUN = 128

NTSC_NES_HZ = 1_789_773
CGB_FPS = 4_194_304 / 70_224


# ---------------------------------------------------------------------------- pitch

def pulse_reg(freq_hz: float) -> int:
    """Valor de 11 bits de NRx3/NRx4 para un pulso de `freq_hz`: x = 2048 - 131072 / f."""
    x = round(2048 - 131072 / freq_hz)
    if not 0 <= x <= 2047:
        raise ValueError(f"{freq_hz:.1f} Hz fuera del rango del pulso (64 Hz a 131 kHz)")
    return x


def wave_reg(freq_hz: float) -> int:
    """Valor de 11 bits de NR33/NR34 para la onda de 32 pasos: x = 2048 - 65536 / f."""
    x = round(2048 - 65536 / freq_hz)
    if not 0 <= x <= 2047:
        raise ValueError(f"{freq_hz:.1f} Hz fuera del rango del canal 3 (32 Hz a 65 kHz)")
    return x


def midi_hz(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def triangle_wave_ram() -> bytes:
    """Los 32 pasos del triángulo (15...0, 0...15) empaquetados en 16 bytes (nibble alto primero)."""
    steps = [15 - i for i in range(16)] + [i for i in range(16)]
    return bytes(steps[i] << 4 | steps[i + 1] for i in range(0, 32, 2))


# ---------------------------------------------------------------------------- codificación

@dataclass
class FrameWrites:
    """Lo que se escribe en un cuadro: {canal 0-3: {registro 0-4: valor}} y opcionalmente la wave RAM."""

    channels: dict[int, dict[int, int]] = field(default_factory=dict)
    wave: bytes | None = None
    end: bool = False

    def is_empty(self) -> bool:
        return not self.channels and self.wave is None and not self.end

    def set(self, channel: int, reg: int, value: int) -> None:
        self.channels.setdefault(channel, {})[reg] = value


def encode_frame(fw: FrameWrites) -> bytes:
    """Un registro de cuadro no vacío."""
    mask = 0
    body = bytearray()
    for ch in range(4):
        regs = fw.channels.get(ch)
        if not regs:
            continue
        mask |= 1 << ch
        if ch in (1, 3) and 0 in regs:
            raise ValueError(f"el canal {ch + 1} no tiene NRx0")
        m = 0
        for r in regs:
            m |= 1 << r
        body.append(m)
        for r in sorted(regs):
            body.append(regs[r])
    head = mask | (WAVE_FLAG if fw.wave is not None else 0) | (END_FLAG if fw.end else 0)
    out = bytearray([head])
    if fw.wave is not None:
        if len(fw.wave) != 16:
            raise ValueError("la wave RAM mide 16 bytes")
        out += fw.wave
    # (el orden en el stream: H, wave RAM, y luego los canales)
    out += body
    return bytes(out)


def encode_stream(frames: list[FrameWrites], break_at: set[int] | None = None) -> tuple[bytes, list[int]]:
    """Codifica todos los cuadros. Devuelve (stream, offsets) donde offsets[i] = posición del registro que
    empieza en el cuadro i. Las rachas de vacíos se cortan antes de los cuadros de `break_at`, para que esos
    cuadros siempre empiecen un registro (los keyframes saltan a ahí). El último cuadro debe llevar `end`."""
    if not frames or not frames[-1].end:
        raise ValueError("el último cuadro debe llevar la marca de fin")
    break_at = break_at or set()
    out = bytearray()
    offsets: list[int] = []
    run = 0
    run_start = 0
    for i, fw in enumerate(frames):
        if run and i in break_at:
            out.append(EMPTY_FLAG | (run - 1))
            run = 0
        if fw.is_empty():
            if run == 0:
                run_start = len(out)
            run += 1
            offsets.append(run_start)
            if run == MAX_EMPTY_RUN:
                out.append(EMPTY_FLAG | (run - 1))
                run = 0
            continue
        if run:
            out.append(EMPTY_FLAG | (run - 1))
            run = 0
        offsets.append(len(out))
        out += encode_frame(fw)
    if run:
        out.append(EMPTY_FLAG | (run - 1))
    return bytes(out), offsets


def decode_stream(stream: bytes) -> list[FrameWrites]:
    """Inversa de encode_stream (para las pruebas y para calcular qué suena en cada cuadro)."""
    frames: list[FrameWrites] = []
    i = 0
    while i < len(stream):
        head = stream[i]
        i += 1
        if head & EMPTY_FLAG:
            frames += [FrameWrites() for _ in range((head & 0x7F) + 1)]
            continue
        fw = FrameWrites(end=bool(head & END_FLAG))
        if head & MASTER_FLAG:
            raise ValueError("NR50/NR51 en el stream no está soportado todavía")
        if head & WAVE_FLAG:
            fw.wave = bytes(stream[i : i + 16])
            i += 16
        for ch in range(4):
            if not head >> ch & 1:
                continue
            m = stream[i]
            i += 1
            for r in range(5):
                if m >> r & 1:
                    fw.set(ch, r, stream[i])
                    i += 1
        frames.append(fw)
        if fw.end:
            break
    return frames


def note_on_frames(frames: list[FrameWrites]) -> dict[int, list[int]]:
    """{canal: [cuadros en los que se dispara una nota]} (NRx4 con el bit 7)."""
    result: dict[int, list[int]] = {ch: [] for ch in range(4)}
    for i, fw in enumerate(frames):
        for ch, regs in fw.channels.items():
            if regs.get(4, 0) & 0x80:
                result[ch].append(i)
    return result
