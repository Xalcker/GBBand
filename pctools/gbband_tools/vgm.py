"""VGM a IR: las escrituras grabadas al APU de la Game Boy (DMG), con sus tiempos, pasadas por `gbapu.py`.

    uv run gbband import-song "songs_src/Juego - Pista.vgz" --name juego_pista

Un VGM ya trae cada escritura a $FF10-$FF3F (comando $B3) separada por esperas en muestras de 44 100 Hz, así que no
hace falta correr el código del juego como en un NSF o un GBS. `.vgz` es el mismo archivo comprimido con gzip. Solo se
aceptan VGM de Game Boy: los de otros chips (Sega, YM2612...) se rechazan con un mensaje. El título y el juego salen de
la etiqueta GD3, y la duración, de la que dice el archivo (una vuelta, con la introducción); `--duration` graba más
segundos repitiendo desde el punto de repetición.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from pathlib import Path

from . import gbapu, ir

SAMPLE_HZ = 44_100
GB_DMG = 0xB3
# Largo total (con el byte del comando) de los comandos que no son del Game Boy, para saltarlos
_SIZES = {0x4F: 2, 0x50: 2, 0x62: 1, 0x63: 1, 0x90: 5, 0x91: 5, 0x92: 6, 0x93: 11, 0x94: 2, 0x95: 5}
for _c in range(0x30, 0x40):
    _SIZES[_c] = 2
for _c in range(0x40, 0x4F):
    _SIZES[_c] = 3
for _c in range(0x51, 0x60):
    _SIZES[_c] = 3
for _c in range(0x70, 0x90):
    _SIZES[_c] = 1
for _c in range(0xA0, 0xC0):
    _SIZES[_c] = 3
for _c in range(0xC0, 0xE0):
    _SIZES[_c] = 4
for _c in range(0xE0, 0x100):
    _SIZES[_c] = 5
CHIPS = {0x0C: "SN76489", 0x10: "YM2413", 0x2C: "YM2612", 0x30: "YM2151", 0x74: "AY8910", 0x84: "NES APU"}


@dataclass
class Vgm:
    version: int
    total_samples: int
    loop_offset: int | None  # posición absoluta en el archivo, o None si no se repite
    loop_samples: int
    data_offset: int
    gb_clock: int
    data: bytes
    title: str
    game: str
    author: str


def parse(raw: bytes) -> Vgm:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    if raw[:4] != b"Vgm ":
        raise ValueError("no es un VGM (falta 'Vgm ')")
    u32 = lambda at: int.from_bytes(raw[at:at + 4], "little") if at + 4 <= len(raw) else 0
    version = u32(0x08)
    data_offset = 0x34 + u32(0x34) if version >= 0x150 and u32(0x34) else 0x40
    field = lambda at: u32(at) if at + 4 <= data_offset else 0  # los campos que caen dentro de los datos valen 0
    loop = u32(0x1C)
    gd3 = ["", "", "", "", "", "", "", ""]
    if u32(0x14):
        start = 0x14 + u32(0x14)
        if raw[start:start + 4] == b"Gd3 ":
            size = int.from_bytes(raw[start + 8:start + 12], "little")
            gd3 = raw[start + 12:start + 12 + size].decode("utf-16-le", errors="replace").split("\0")
    tag = lambda i: gd3[i].strip() if i < len(gd3) else ""
    return Vgm(version, u32(0x18), 0x1C + loop if loop else None, u32(0x20), data_offset, field(0x80), raw,
               tag(0), tag(2), tag(6))


def other_chips(vgm: Vgm) -> list[str]:
    raw = vgm.data
    found = []
    for at, name in CHIPS.items():
        if at + 4 <= vgm.data_offset and int.from_bytes(raw[at:at + 4], "little") & 0x3FFFFFFF:
            found.append(name)
    return found


def events(vgm: Vgm, max_samples: int):
    """Las escrituras al Game Boy como (muestra, registro $FF10-$FF3F, valor), hasta `max_samples`."""
    raw = vgm.data
    pos, sample = vgm.data_offset, 0
    looped_at = None  # la muestra en que se repitió por última vez (una vuelta sin esperas no avanza: se termina)
    while pos < len(raw) and sample < max_samples:
        cmd = raw[pos]
        if cmd == GB_DMG:
            reg, value = raw[pos + 1], raw[pos + 2]
            if not reg & 0x80:  # el bit 7 es el segundo chip
                yield sample, 0xFF10 + reg, value
            pos += 3
        elif cmd == 0x61:
            sample += int.from_bytes(raw[pos + 1:pos + 3], "little")
            pos += 3
        elif cmd == 0x62:
            sample += 735
            pos += 1
        elif cmd == 0x63:
            sample += 882
            pos += 1
        elif 0x70 <= cmd <= 0x7F:
            sample += (cmd & 15) + 1
            pos += 1
        elif 0x80 <= cmd <= 0x8F:
            sample += cmd & 15
            pos += 1
        elif cmd == 0x66:
            if vgm.loop_offset is None or looped_at == sample:
                return
            pos, looped_at = vgm.loop_offset, sample
        elif cmd == 0x67:
            pos += 7 + (int.from_bytes(raw[pos + 3:pos + 7], "little") & 0x7FFFFFFF)
        elif cmd == 0x68:
            pos += 12
        elif cmd in _SIZES:
            pos += _SIZES[cmd]
        else:
            raise ValueError(f"comando de VGM desconocido ${cmd:02X} en {pos:#x}")


def run(path: Path, seconds: float | None = None) -> tuple[ir.SongIR, Vgm]:
    vgm = parse(path.read_bytes())
    if not vgm.gb_clock:
        chips = other_chips(vgm)
        raise SystemExit(f"{path.name} no es música de Game Boy" + (f" (es de {', '.join(chips)})" if chips else "")
                         + ": solo se importan VGM del APU de la Game Boy (DMG)")
    total = vgm.total_samples
    if seconds:
        total = round(seconds * SAMPLE_HZ) if vgm.loop_offset is not None else min(total, round(seconds * SAMPLE_HZ))
    frames = max(1, int(total * gbapu.CPU_HZ / SAMPLE_HZ) // gbapu.FRAME_CYCLES)
    apu = gbapu.Apu()
    recorder = gbapu.Recorder(apu, frames)
    f = 0
    for sample, reg, value in events(vgm, total):
        time = sample * gbapu.CPU_HZ // SAMPLE_HZ
        while f < frames and (f + 1) * gbapu.FRAME_CYCLES <= time:
            apu.run_until((f + 1) * gbapu.FRAME_CYCLES - 1)
            recorder.capture(f)
            f += 1
        if f >= frames:
            break
        apu.run_until(time)
        apu.write(reg, value)
    while f < frames:
        apu.run_until((f + 1) * gbapu.FRAME_CYCLES - 1)
        recorder.capture(f)
        f += 1
    song = recorder.to_ir(path.stem, vgm.game, "VGM")
    if vgm.gb_clock & 0x40000000:
        song.warn("el VGM trae dos Game Boy: solo se importa la primera")
    if other_chips(vgm):
        song.warn(f"el VGM también usa {', '.join(other_chips(vgm))}: solo se importa la Game Boy")
    return song, vgm


def load(path: Path, options) -> tuple[ir.SongIR, str, str]:
    song, vgm = run(path, options.duration)
    return song, vgm.title or path.stem, vgm.game
