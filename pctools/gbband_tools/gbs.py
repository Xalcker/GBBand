"""GBS a IR: corre el código de música de un GBS en un SM83 y registra lo que escribe al APU de la Game Boy.

    uv run gbband import-song "songs_src/Juego.gbs" --track 3 --name juego_nivel1

Es el equivalente de `nsf.py` para la Game Boy: el GBS trae el código del juego y tres direcciones (carga, init y
play). Se llama a init con A = la canción (desde 0) y luego a play al ritmo que pide el archivo: cada VBlank (59.73 Hz) o
con el timer (TAC y TMA del encabezado, que la música puede cambiar). Las escrituras a $FF10-$FF3F pasan por `gbapu.py`.
El banco de $4000-$7FFF se cambia escribiendo en $2000-$3FFF, como en un MBC1, y los RST saltan a la dirección de carga
más el vector.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import gbapu, ir
from .m3u import find_playlist
from .sm83 import SM83

DEFAULT_SECONDS = 120
TIMER_HZ = (4096, 262_144, 65_536, 16_384)  # TAC bits 1-0
SENTINEL = 0xFFFF  # la dirección a la que "vuelven" init y play


@dataclass
class Header:
    songs: int
    first_song: int  # desde 1
    load: int
    init: int
    play: int
    sp: int
    tma: int
    tac: int
    title: str
    author: str
    copyright: str
    data: bytes


def parse_header(raw: bytes) -> Header:
    if raw[:3] != b"GBS":
        raise ValueError("no es un GBS (falta GBS)")
    if raw[3] != 1:
        raise ValueError(f"versión de GBS {raw[3]} desconocida (solo existe la 1)")
    u16 = lambda at: int.from_bytes(raw[at:at + 2], "little")
    text = lambda a, b: raw[a:b].split(b"\0")[0].decode("latin-1").strip()
    return Header(raw[4], raw[5], u16(6), u16(8), u16(10), u16(12), raw[14], raw[15], text(0x10, 0x30), text(0x30, 0x50),
                  text(0x50, 0x70), raw[0x70:])


class GbsMachine:
    def __init__(self, header: Header):
        self.h = header
        image = bytes(header.load) + header.data
        image += bytes(max(-len(image) % 0x4000, 0x8000 - len(image)))  # bancos completos, y al menos dos
        self.banks = [image[i:i + 0x4000] for i in range(0, len(image), 0x4000)]
        self.bank = 1
        self.ram = bytearray(0x8000)  # $8000-$FFFF
        self.apu = gbapu.Apu()
        self.tma, self.tac = header.tma, header.tac
        self.cpu = SM83(self.read, self.write, rst_base=header.load)
        self.cpu.sp = header.sp

    def read(self, addr: int) -> int:
        if addr < 0x4000:
            return self.banks[0][addr]
        if addr < 0x8000:
            bank = self.banks[self.bank] if self.bank < len(self.banks) else None
            return bank[addr - 0x4000] if bank else 0xFF
        if 0xE000 <= addr < 0xFE00:
            addr -= 0x2000
        if 0xFF10 <= addr <= 0xFF3F:
            return self.apu.read(addr)
        if addr == 0xFF06:
            return self.tma
        if addr == 0xFF07:
            return self.tac | 0xF8
        if addr == 0xFF00:
            return 0xFF  # ningún botón
        return self.ram[addr - 0x8000]

    def write(self, addr: int, value: int) -> None:
        if addr < 0x8000:
            if 0x2000 <= addr < 0x4000:
                self.bank = value or 1
            return
        if 0xE000 <= addr < 0xFE00:
            addr -= 0x2000
        if 0xFF10 <= addr <= 0xFF3F:
            self.apu.write(addr, value)
        elif addr == 0xFF06:
            self.tma = value
        elif addr == 0xFF07:
            self.tac = value & 7 | (self.tac & 0x80)
        self.ram[addr - 0x8000] = value

    def period(self) -> int:
        """Ciclos T entre dos llamadas a play."""
        if not self.h.tac & 4:
            return gbapu.FRAME_CYCLES
        hz = TIMER_HZ[self.tac & 3] * (2 if self.h.tac & 0x80 else 1)
        return max(1, round((256 - self.tma) * gbapu.CPU_HZ / hz))


def run(path: Path, song: int, seconds: float) -> tuple[ir.SongIR, Header]:
    """Corre la canción `song` (desde 0) durante `seconds` y devuelve su IR."""
    header = parse_header(path.read_bytes())
    machine = GbsMachine(header)
    cpu, apu = machine.cpu, machine.apu
    for addr, value in ((0xFF26, 0x80), (0xFF25, 0xFF), (0xFF24, 0x77)):
        apu.write(addr, value)
    frames = int(seconds * gbapu.CPU_HZ / gbapu.FRAME_CYCLES)
    recorder = gbapu.Recorder(apu, frames)
    limit = 10 * gbapu.FRAME_CYCLES
    try:
        cpu.call(header.init, a=song, limit=limit * 6, sentinel=SENTINEL)
    except TimeoutError:
        raise SystemExit(f"{path.name}: la rutina de init no vuelve (¿el GBS espera interrupciones?)") from None
    over_budget = 0
    time = 0  # ciclo de la siguiente llamada a play
    for f in range(frames):
        end = (f + 1) * gbapu.FRAME_CYCLES
        while time < end:
            apu.run_until(time)
            period = machine.period()
            try:
                used = cpu.call(header.play, a=cpu.r[7], limit=limit, sentinel=SENTINEL)
            except TimeoutError:
                used = limit
                cpu.sp = header.sp
            if used > period:
                over_budget += 1
            time += period
        apu.run_until(end - 1)
        recorder.capture(f)
    result = recorder.to_ir(path.stem, header.title, "GBS")
    if over_budget:
        result.warn(f"{over_budget} llamadas a play tardaron más que el tiempo entre dos llamadas")
    if header.tac & 4:
        result.warn(f"play al ritmo del timer: {gbapu.CPU_HZ / machine.period():.2f} llamadas por segundo")
    return result, header


def load(path: Path, options) -> tuple[ir.SongIR, str, str]:
    """Importa una pista de un GBS. `options.track` es la del .m3u tal como viene escrita (muchos numeran desde 0; si no
    hay .m3u o no tiene pista 0, se cuenta desde 1); `options.song`, el índice desde 0."""
    header = parse_header(path.read_bytes())
    song, title, game, seconds = options.song, None, None, options.duration
    if options.track is not None:
        song = options.track - 1
        playlist = find_playlist(path)
        if playlist:
            track = playlist.tracks.get(options.track)
            if track is None:
                raise SystemExit(f"La pista {options.track} no está en el .m3u de {path.name}")
            if 0 in playlist.tracks:
                song = options.track
            title, game, seconds = track.title, playlist.game, seconds or track.seconds
    if not 0 <= song < max(header.songs, 1):
        raise SystemExit(f"{path.name} tiene {header.songs} pistas: la {song} no existe")
    result, _ = run(path, song, seconds or DEFAULT_SECONDS)
    return result, title or header.title or path.stem, game or header.title
