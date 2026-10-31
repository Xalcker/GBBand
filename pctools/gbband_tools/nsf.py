"""NSF a IR: corre el código de música de un NSF en un 6502 y registra lo que escribe al APU del NES.

    uv run gbband import-song "songs_src/Juego.nsf" --track 2 --name juego_area1

Es la fuente de la IR para la música de juegos comerciales (que cada quien importa de sus propios archivos y que
nunca entra a git). No hace falta FamiStudio: el NSF se ejecuta aquí y de las escrituras a $4000-$4017 se saca, por
cuadro, el estado de cada canal (frecuencia, volumen con su envolvente, duty, si arrancó una nota) y los golpes de
ruido y DPCM. Con eso se arma la IR igual que desde un proyecto de FamiStudio.

Qué emula del APU: envolventes (constantes y de caída), contadores de longitud, contador lineal del triángulo,
barrido de los pulsos y los cuatro pasos del secuenciador de cuadros. El DPCM solo se registra (cuándo empieza cada
sample y qué suena) para clasificar los golpes. No emula los chips de sonido extra (VRC6, FDS, N163...): esas
canciones se rechazan con un mensaje.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import ir
from .cpu6502 import CPU6502
from .m3u import find_playlist

LENGTHS = [10, 254, 20, 2, 40, 4, 80, 6, 160, 8, 60, 10, 14, 12, 26, 14, 12, 16, 24, 18, 48, 20, 96, 22, 192, 24, 72, 26, 16, 28, 32, 30]
NOISE_PERIODS = [4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068]
DPCM_RATES = [428, 380, 340, 320, 286, 254, 226, 214, 190, 160, 142, 128, 106, 84, 72, 54]
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

@dataclass
class Envelope:
    const: bool = True
    loop: bool = False
    vol: int = 0
    start: bool = False
    divider: int = 0
    decay: int = 0

    def clock(self) -> None:
        if self.start:
            self.start, self.decay, self.divider = False, 15, self.vol
        elif self.divider == 0:
            self.divider = self.vol
            if self.decay > 0:
                self.decay -= 1
            elif self.loop:
                self.decay = 15
        else:
            self.divider -= 1

    @property
    def out(self) -> int:
        return self.vol if self.const else self.decay


@dataclass
class Pulse:
    index: int
    env: Envelope = field(default_factory=Envelope)
    duty: int = 0
    timer: int = 0
    length: int = 0
    enabled: bool = False
    sweep_on: bool = False
    sweep_period: int = 0
    sweep_negate: bool = False
    sweep_shift: int = 0
    sweep_reload: bool = False
    sweep_div: int = 0
    trig: bool = False

    def target(self) -> int:
        change = self.timer >> self.sweep_shift
        return self.timer - change - (1 if self.index == 0 else 0) if self.sweep_negate else self.timer + change

    def muted(self) -> bool:
        return self.timer < 8 or self.target() > 0x7FF

    def clock_sweep(self) -> None:
        if self.sweep_div == 0 and self.sweep_on and self.sweep_shift and not self.muted():
            self.timer = self.target()
        if self.sweep_div == 0 or self.sweep_reload:
            self.sweep_div, self.sweep_reload = self.sweep_period, False
        else:
            self.sweep_div -= 1

    def audible(self) -> bool:
        return self.length > 0 and not self.muted()


class Apu:
    def __init__(self) -> None:
        self.pulses = [Pulse(0), Pulse(1)]
        self.tri_control = False
        self.tri_reload = 0
        self.tri_linear = 0
        self.tri_reload_flag = False
        self.tri_timer = 0
        self.tri_length = 0
        self.tri_enabled = False
        self.tri_trig = False
        self.noise_env = Envelope()
        self.noise_halt = False
        self.noise_mode = False
        self.noise_period = 0
        self.noise_length = 0
        self.noise_enabled = False
        self.noise_trig = False
        self.dpcm_rate = 0
        self.dpcm_addr = 0
        self.dpcm_len = 0
        self.dpcm_starts: list[tuple[int, int, int]] = []  # (dirección, bytes, tasa) de los samples que arrancaron en el cuadro

    def write(self, addr: int, value: int) -> None:
        if 0x4000 <= addr <= 0x4007:
            p = self.pulses[(addr - 0x4000) >> 2]
            reg = addr & 3
            if reg == 0:
                p.duty = value >> 6
                p.env.loop = bool(value & 0x20)
                p.env.const = bool(value & 0x10)
                p.env.vol = value & 0x0F
            elif reg == 1:
                p.sweep_on, p.sweep_period = bool(value & 0x80), (value >> 4) & 7
                p.sweep_negate, p.sweep_shift, p.sweep_reload = bool(value & 8), value & 7, True
            elif reg == 2:
                p.timer = (p.timer & 0x700) | value
            else:
                p.timer = (p.timer & 0xFF) | (value & 7) << 8
                if p.enabled:
                    p.length = LENGTHS[value >> 3]
                p.env.start = True
                p.trig = True
        elif addr == 0x4008:
            self.tri_control, self.tri_reload = bool(value & 0x80), value & 0x7F
        elif addr == 0x400A:
            self.tri_timer = (self.tri_timer & 0x700) | value
        elif addr == 0x400B:
            self.tri_timer = (self.tri_timer & 0xFF) | (value & 7) << 8
            if self.tri_enabled:
                self.tri_length = LENGTHS[value >> 3]
            self.tri_reload_flag = True
            self.tri_trig = True
        elif addr == 0x400C:
            self.noise_halt = bool(value & 0x20)
            self.noise_env.loop = self.noise_halt
            self.noise_env.const = bool(value & 0x10)
            self.noise_env.vol = value & 0x0F
        elif addr == 0x400E:
            self.noise_mode, self.noise_period = bool(value & 0x80), value & 0x0F
        elif addr == 0x400F:
            if self.noise_enabled:
                self.noise_length = LENGTHS[value >> 3]
            self.noise_env.start = True
            self.noise_trig = True
        elif addr == 0x4010:
            self.dpcm_rate = value & 0x0F
        elif addr == 0x4012:
            self.dpcm_addr = 0xC000 + value * 64
        elif addr == 0x4013:
            self.dpcm_len = value * 16 + 1
        elif addr == 0x4015:
            for p, bit in zip(self.pulses, (0, 1)):
                p.enabled = bool(value >> bit & 1)
                if not p.enabled:
                    p.length = 0
            self.tri_enabled = bool(value & 4)
            if not self.tri_enabled:
                self.tri_length = 0
            self.noise_enabled = bool(value & 8)
            if not self.noise_enabled:
                self.noise_length = 0
            if value & 0x10:
                self.dpcm_starts.append((self.dpcm_addr, self.dpcm_len, self.dpcm_rate))

    def status(self) -> int:
        return (self.pulses[0].length > 0) | (self.pulses[1].length > 0) << 1 | (self.tri_length > 0) << 2 | (self.noise_length > 0) << 3

    def clock_quarter(self) -> None:
        for p in self.pulses:
            p.env.clock()
        self.noise_env.clock()
        if self.tri_reload_flag:
            self.tri_linear = self.tri_reload
        elif self.tri_linear > 0:
            self.tri_linear -= 1
        if not self.tri_control:
            self.tri_reload_flag = False

    def clock_half(self) -> None:
        for p in self.pulses:
            if not p.env.loop and p.length > 0:
                p.length -= 1
            p.clock_sweep()
        if not self.tri_control and self.tri_length > 0:
            self.tri_length -= 1
        if not self.noise_halt and self.noise_length > 0:
            self.noise_length -= 1

    def finish_frame(self) -> None:
        """Los pasos 2 a 4 del secuenciador de cuadros (60 Hz): el primero (un reloj de envolvente) se aplica antes de
        registrar el estado del cuadro, para que lo que escribió la rutina de reproducción ya cuente (la envolvente
        arranca en 15 y el contador lineal del triángulo se carga en ese primer reloj)."""
        self.clock_quarter()
        self.clock_half()
        self.clock_quarter()
        self.clock_quarter()
        self.clock_half()


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


def dpcm_zcr(read, start: int, length: int) -> float:
    """Cruces por cero por bit del sample (modulación delta de 1 bit): bajo = grave (bombo), alto = agudo o ruido.
    `read(addr)` lee la memoria donde está el sample."""
    bits = []
    for i in range(min(length, 400)):
        byte = read(start + i if start + i <= 0xFFFF else start)
        bits += [byte >> k & 1 for k in range(8)]
    flips = sum(1 for a, b in zip(bits, bits[1:]) if a != b)
    return flips / max(len(bits), 1)


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
    tracks, noise_hits, dpcm_hits, noise_active = record(machine.apu, frames, play, machine.read)
    result = ir.SongIR(path.stem, header.title, frames, tracks, {c: [] for c in ir.CHANNELS}, None, source="NSF")
    if over_budget:
        result.warn(f"{over_budget} cuadros donde la rutina de reproducción tardó más de un cuadro NES de CPU")
    return build_ir(result, tracks, noise_hits, dpcm_hits, noise_active)


def record(apu: Apu, frames: int, play, read) -> tuple[dict, list, list, list]:
    """Graba cuadro por cuadro el estado de cada canal del APU. `play(f)` escribe los registros del cuadro `f` (la
    rutina de reproducción de un NSF, o las escrituras de un VGM) y `read(addr)` lee la memoria (los samples DPCM)."""
    tracks = {c: ir.Track.silent(frames) for c in ir.TONAL}
    noise_hits: list[tuple[int, int, int, bool]] = []  # (cuadro, índice de periodo, vol, modo corto)
    dpcm_hits: list[tuple[int, float, int]] = []  # (cuadro, zcr, duración en cuadros)
    noise_active = [0] * frames
    for f in range(frames):
        play(f)
        # estado de cada canal al inicio del cuadro (después de lo que escribió la rutina de reproducción y del
        # primer reloj del secuenciador)
        apu.clock_quarter()
        for p, name in zip(apu.pulses, ("Square1", "Square2")):
            track = tracks[name]
            if p.audible() and p.length > 0 and p.env.out > 0:
                track.freq[f] = ir.NES_CPU_HZ / (16 * (p.timer + 1))
                track.vol[f] = p.env.out
                track.duty[f] = p.duty
            track.trig[f] = p.trig
            p.trig = False
        track = tracks["Triangle"]
        if apu.tri_length > 0 and apu.tri_linear > 0 and apu.tri_timer >= 2:
            track.freq[f] = ir.NES_CPU_HZ / (32 * (apu.tri_timer + 1))
            track.vol[f] = 15
        track.trig[f] = apu.tri_trig
        apu.tri_trig = False
        if apu.noise_length > 0 and apu.noise_env.out > 0:
            noise_active[f] = apu.noise_env.out
        if apu.noise_trig:
            noise_hits.append((f, apu.noise_period, apu.noise_env.out, apu.noise_mode))
            apu.noise_trig = False
        for addr, length, rate in apu.dpcm_starts:
            dur = max(1, round(length * 8 * DPCM_RATES[rate] / CYCLES_PER_FRAME))
            dpcm_hits.append((f, dpcm_zcr(read, addr, length), dur))
        apu.dpcm_starts.clear()
        apu.finish_frame()
    return tracks, noise_hits, dpcm_hits, noise_active


def build_ir(result: ir.SongIR, tracks: dict, noise_hits: list, dpcm_hits: list, noise_active: list) -> ir.SongIR:
    """Las notas de la IR a partir de lo grabado por `record`."""
    frames = result.length_frames
    for name in ir.TONAL:
        result.notes[name] = tonal_notes(tracks[name])
    for f, period, vol, short in noise_hits:
        duration = 1
        while f + duration < frames and noise_active[f + duration] > 0 and duration < 60:
            duration += 1
        pitch = 24 + (15 - period) * 3 + (12 if short else 0)  # más agudo = periodo más corto
        result.notes["Noise"].append(ir.Note(f, pitch, duration))
    for f, zcr, dur in dpcm_hits:
        result.notes["DPCM"].append(ir.Note(f, 24 + int(zcr * 60), dur))
    if not any(result.notes[c] for c in ir.TONAL):
        result.warn("no se oyó ninguna nota en los canales tonales (¿la pista está vacía o es de otro chip?)")
    return result


def tonal_notes(track: ir.Track) -> list[ir.Note]:
    """Las notas de un canal: una por arranque o por cambio de altura sostenido (el vibrato no cuenta como notas)."""
    notes: list[ir.Note] = []
    start = pitch = None
    candidate: tuple[int, int] | None = None  # (cuadro, altura) de un posible cambio
    for f in range(len(track.freq)):
        active = track.freq[f] > 0 and track.vol[f] > 0
        if not active:
            if start is not None:
                notes.append(ir.Note(start, pitch, f - start))
                start = None
            candidate = None
            continue
        p = round(ir.hz_midi(track.freq[f]))
        if start is None or track.trig[f]:
            if start is not None:
                notes.append(ir.Note(start, pitch, f - start))
            start, pitch, candidate = f, p, None
        elif abs(p - pitch) >= 2:
            if candidate and candidate[1] == p:
                notes.append(ir.Note(start, pitch, candidate[0] - start))
                start, pitch, candidate = candidate[0], p, None
            else:
                candidate = (f, p)
        else:
            candidate = None
    if start is not None:
        notes.append(ir.Note(start, pitch, len(track.freq) - start))
    return notes


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
