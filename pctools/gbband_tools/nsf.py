"""NSF a IR: corre el código de música de un NSF en un 6502 y registra lo que escribe al APU del NES.

    uv run gbband import-song "songs_src/Juego.nsf" --track 2 --name juego_area1

Es la fuente de la IR para la música de juegos comerciales (que cada quien importa de sus propios archivos y que
nunca entra a git). No hace falta FamiStudio: el NSF se ejecuta aquí y de las escrituras a $4000-$4017 se saca, por
cuadro, el estado de cada canal (frecuencia, volumen con su envolvente, duty, si arrancó una nota) y los golpes de
ruido y DPCM. Con eso se arma la IR igual que desde un proyecto de FamiStudio.

El APU emulado y la grabación cuadro por cuadro son los de bandcore (`bandcore.nesapu`, compartidos con NESBand);
aquí queda el 6502 que corre la rutina del NSF. No emula los chips de sonido extra (VRC6, FDS, N163...): esas
canciones se rechazan con un mensaje.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bandcore import nesapu
from bandcore.nesapu import Apu, record, tonal_notes  # noqa: F401  (el APU del NES es el de bandcore, compartido con NESBand)

from . import ir
from .cpu6502 import CPU6502
from .m3u import find_playlist

EXPANSIONS = {0x01: "VRC6", 0x02: "VRC7", 0x04: "FDS", 0x08: "MMC5", 0x10: "N163", 0x20: "Sunsoft 5B", 0x40: "VT02+"}
CYCLES_PER_FRAME = 29780
DEFAULT_SECONDS = 120


@dataclass
class Header:
    songs: int
    first_song: int
    load: int
    init: int
    play: int
    title: str
    artist: str
    copyright: str
    banks: tuple[int, ...]
    expansion: int
    data: bytes


def parse_header(raw: bytes) -> Header:
    if raw[:5] != b"NESM\x1a":
        raise ValueError("no es un NSF (falta NESM)")
    text = lambda a, b: raw[a:b].split(b"\0")[0].decode("latin-1")
    return Header(raw[6], raw[7], int.from_bytes(raw[8:10], "little"), int.from_bytes(raw[10:12], "little"),
                  int.from_bytes(raw[12:14], "little"), text(0x0E, 0x2E), text(0x2E, 0x4E), text(0x4E, 0x6E),
                  tuple(raw[0x70:0x78]), raw[0x7B], raw[0x80:])


# ---- APU --------------------------------------------------------------------------------------------------------


# ---- memoria del NSF ---------------------------------------------------------------------------------------------

class NsfMachine:
    def __init__(self, header: Header):
        self.h = header
        self.ram = bytearray(0x800)
        self.prg_ram = bytearray(0x2000)
        self.apu = Apu()
        self.rom = bytearray(0x8000)
        self.bank_regs = list(header.banks)
        self.banked = any(header.banks)
        self.data = header.data
        if self.banked:
            self.pad = header.load & 0xFFF
            self.image = bytes(self.pad) + header.data
        else:
            offset = header.load - 0x8000
            self.rom[offset:offset + len(header.data)] = header.data[: 0x8000 - offset]
        self.cpu = CPU6502(self.read, self.write)

    def read(self, addr: int) -> int:
        if addr < 0x2000:
            return self.ram[addr & 0x7FF]
        if addr == 0x4015:
            return self.apu.status()
        if addr < 0x6000:
            return 0
        if addr < 0x8000:
            return self.prg_ram[addr - 0x6000]
        if self.banked:
            bank = self.bank_regs[(addr - 0x8000) >> 12]
            pos = bank * 0x1000 + (addr & 0xFFF)
            return self.image[pos] if pos < len(self.image) else 0
        return self.rom[addr - 0x8000]

    def write(self, addr: int, value: int) -> None:
        value &= 0xFF
        if addr < 0x2000:
            self.ram[addr & 0x7FF] = value
        elif 0x4000 <= addr <= 0x4017:
            self.apu.write(addr, value)
        elif 0x5FF8 <= addr <= 0x5FFF:
            self.bank_regs[addr - 0x5FF8] = value
        elif 0x6000 <= addr < 0x8000:
            self.prg_ram[addr - 0x6000] = value


def run(path: Path, song: int, seconds: int, log: list[str] | None = None) -> ir.SongIR:
    """Corre la canción `song` (desde 0) durante `seconds` y devuelve su IR."""
    raw = path.read_bytes()
    header = parse_header(raw)
    if header.expansion:
        names = ", ".join(n for bit, n in EXPANSIONS.items() if header.expansion & bit)
        raise SystemExit(f"La canción usa chips de sonido extra ({names}). Solo se importa el sonido del NES (2A03): "
                         "busca la versión americana/europea del juego, que normalmente no los usa.")
    machine = NsfMachine(header)
    cpu = machine.cpu
    cpu.call(header.init, a=song, x=0)
    over_budget = 0

    def play(f: int) -> None:
        nonlocal over_budget
        try:
            used = cpu.call(header.play, limit=3 * CYCLES_PER_FRAME)
        except TimeoutError:
            used = 3 * CYCLES_PER_FRAME
            over_budget += 1
        if used > CYCLES_PER_FRAME:
            over_budget += 1

    frames = int(seconds * ir.NES_FPS)
    rec = record(machine.apu, frames, play, machine.read)
    result = ir.SongIR(path.stem, header.title, frames, rec.tracks, {c: [] for c in ir.CHANNELS}, None, source="NSF")
    if over_budget:
        result.warn(f"{over_budget} cuadros donde la rutina de reproducción tardó más de un cuadro NES de CPU")
    return build_ir(result, rec)


def build_ir(result: ir.SongIR, rec: nesapu.Recording) -> ir.SongIR:
    """Las notas de la IR a partir de lo grabado por `record` (las de bandcore.nesapu.notes)."""
    result.notes.update(nesapu.notes(rec))
    if not any(result.notes[c] for c in ir.TONAL):
        result.warn("no se oyó ninguna nota en los canales tonales (¿la pista está vacía o es de otro chip?)")
    return result


def load(path: Path, options) -> tuple[ir.SongIR, str, str]:
    """Importa una pista de un NSF. `options.track` es la del .m3u (desde 1); `options.song`, el índice desde 0."""
    raw = path.read_bytes()
    header = parse_header(raw)
    song, title, game, seconds = options.song, None, None, options.duration
    if options.track is not None:
        song = options.track - 1
        playlist = find_playlist(path)
        if playlist:
            track = playlist.tracks.get(options.track)
            if track is None:
                raise SystemExit(f"La pista {options.track} no está en el .m3u de {path.name}")
            title, game, seconds = track.title, playlist.game, seconds or track.seconds
    if not 0 <= song < max(header.songs, 1):
        raise SystemExit(f"{path.name} tiene {header.songs} pistas: la {song} no existe")
    result = run(path, song, seconds or DEFAULT_SECONDS)
    return result, title or header.title or path.stem, game or header.title
