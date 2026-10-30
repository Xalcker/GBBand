"""El APU de la Game Boy (DMG) visto desde las escrituras a sus registros: la base de los importadores de VGM y GBS.

Igual que `nsf.py` con el APU del NES, no genera sonido: lleva el estado de cada canal (frecuencia, volumen con su
envolvente, duty, longitud, barrido) y, cada cuadro de la Game Boy, lo registra para armar la IR:

    pulso 1 (CH1) -> Square1 · pulso 2 (CH2) -> Square2 · onda (CH3) -> Triangle · ruido (CH4) -> golpes de Noise

El tiempo va en ciclos T (4 194 304 por segundo); el secuenciador de cuadros corre a 512 Hz (longitud en los pasos
pares, barrido en el 2 y el 6, envolvente en el 7). La forma de onda de CH3 se pierde (en la ROM suena el triángulo),
pero si la wave RAM repite su dibujo 2 o 4 veces la altura sube una o dos octavas, como en el hardware.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import ir

CPU_HZ = 4_194_304
FRAME_CYCLES = 70_224  # un cuadro de la Game Boy (59.73 Hz)
SEQ_CYCLES = CPU_HZ // 512
# Bits que se leen siempre en 1 en $FF10-$FF26 (Pan Docs, "Audio registers")
READ_MASKS = [0x80, 0x3F, 0x00, 0xFF, 0xBF, 0xFF, 0x3F, 0x00, 0xFF, 0xBF, 0x7F, 0xFF, 0x9F, 0xFF, 0xBF,
              0xFF, 0xFF, 0x00, 0x00, 0xBF, 0x00, 0x00, 0x70]
WAVE_VOLUME = (0, 15, 8, 4)  # NR32 bits 6-5: mudo, 100 %, 50 %, 25 %, como volumen de la IR
NOISE_MAX_FRAMES = 60


@dataclass
class Envelope:
    initial: int = 0
    up: bool = False
    period: int = 0
    vol: int = 0
    timer: int = 0

    def load(self, value: int) -> None:
        self.initial, self.up, self.period = value >> 4, bool(value & 8), value & 7

    def trigger(self) -> None:
        self.vol, self.timer = self.initial, self.period

    def clock(self) -> None:
        if not self.period:
            return
        self.timer -= 1
        if self.timer <= 0:
            self.timer = self.period
            if self.up and self.vol < 15:
                self.vol += 1
            elif not self.up and self.vol > 0:
                self.vol -= 1


@dataclass
class Channel:
    max_length: int = 64
    on: bool = False  # el canal suena (se apaga al acabarse la longitud, con el DAC apagado o por el barrido)
    dac: bool = False
    length: int = 0
    length_on: bool = False
    freq: int = 0  # los 11 bits de NRx3/NRx4
    duty: int = 0
    env: Envelope = field(default_factory=Envelope)
    trig: bool = False  # hubo un disparo desde el último registro de cuadro

    def clock_length(self) -> None:
        if self.length_on and self.length > 0:
            self.length -= 1
            if self.length == 0:
                self.on = False


class Apu:
    def __init__(self) -> None:
        self.ch = [Channel(), Channel(), Channel(max_length=256), Channel()]
        self.regs = bytearray(0x30)  # $FF10-$FF3F tal como se escribieron
        self.regs[0x14], self.regs[0x15] = 0x77, 0xF3  # NR50 y NR51 como los deja el arranque (un VGM puede no escribirlos)
        self.power = True
        self.wave_vol = 0
        self.sweep_period = self.sweep_shift = 0
        self.sweep_negate = False
        self.sweep_timer = 0
        self.sweep_on = False
        self.shadow = 0
        self.nr43 = 0
        self.noise_hits: list[tuple[int, int]] = []  # (NR43, volumen inicial) de los disparos de CH4 desde el último cuadro
        self.time = 0  # ciclos T
        self.next_seq = SEQ_CYCLES
        self.seq_step = 0

    # ---- tiempo ------------------------------------------------------------------------------------------------

    def run_until(self, time: int) -> None:
        """Avanza el secuenciador de cuadros hasta el ciclo `time`."""
        while self.next_seq <= time:
            step = self.seq_step
            if step % 2 == 0:
                for c in self.ch:
                    c.clock_length()
            if step in (2, 6):
                self.clock_sweep()
            if step == 7:
                for i in (0, 1, 3):
                    self.ch[i].env.clock()
            self.seq_step = (step + 1) & 7
            self.next_seq += SEQ_CYCLES
        self.time = max(self.time, time)

    # ---- barrido de CH1 ----------------------------------------------------------------------------------------

    def sweep_target(self) -> int:
        delta = self.shadow >> self.sweep_shift
        return self.shadow - delta if self.sweep_negate else self.shadow + delta

    def clock_sweep(self) -> None:
        if not self.sweep_on:
            return
        self.sweep_timer -= 1
        if self.sweep_timer > 0:
            return
        self.sweep_timer = self.sweep_period or 8
        if not self.sweep_period:
            return
        target = self.sweep_target()
        if target > 0x7FF:
            self.ch[0].on = False
        elif self.sweep_shift:
            self.shadow = self.ch[0].freq = target
            if self.sweep_target() > 0x7FF:
                self.ch[0].on = False

    # ---- registros ---------------------------------------------------------------------------------------------

    def read(self, addr: int) -> int:
        offset = addr - 0xFF10
        if offset == 0x16:  # NR52: encendido y qué canales suenan
            return 0x70 | self.power << 7 | sum(c.on << i for i, c in enumerate(self.ch))
        if offset < len(READ_MASKS):
            return self.regs[offset] | READ_MASKS[offset]
        if offset >= 0x20:
            return self.regs[offset]
        return 0xFF

    def write(self, addr: int, value: int) -> None:
        offset = addr - 0xFF10
        if not 0 <= offset < 0x30:
            return
        if offset >= 0x20:  # wave RAM
            self.regs[offset] = value
            return
        if offset == 0x16:
            power = bool(value & 0x80)
            if self.power and not power:  # apagar borra todos los registros de sonido
                self.regs[:0x16] = bytes(0x16)
                for c in self.ch:
                    c.on = c.dac = c.length_on = False
                    c.duty = c.freq = 0
                    c.env = Envelope()
                self.wave_vol = self.nr43 = 0
                self.sweep_period = self.sweep_shift = 0
                self.sweep_negate = False
            self.power = power
            return
        if not self.power:
            return
        self.regs[offset] = value
        index, reg = (offset // 5, offset % 5) if offset < 0x14 else (None, None)
        if index is None:
            return  # NR50 y NR51: el paneo se mira al registrar el cuadro
        c = self.ch[index]
        if index == 0 and reg == 0:
            self.sweep_period, self.sweep_negate, self.sweep_shift = value >> 4 & 7, bool(value & 8), value & 7
        elif reg == 1:
            if index == 2:
                c.length = 256 - value
            else:
                c.length = 64 - (value & 0x3F)
                if index < 2:
                    c.duty = value >> 6
        elif reg == 2:
            if index == 2:
                self.wave_vol = WAVE_VOLUME[value >> 5 & 3]
            else:
                c.env.load(value)
                c.dac = bool(value & 0xF8)
                if not c.dac:
                    c.on = False
        elif reg == 0 and index == 2:
            c.dac = bool(value & 0x80)
            if not c.dac:
                c.on = False
        elif reg == 3:
            if index == 3:
                self.nr43 = value
            else:
                c.freq = (c.freq & 0x700) | value
        elif reg == 4:
            if index < 3:
                c.freq = (c.freq & 0xFF) | (value & 7) << 8
            c.length_on = bool(value & 0x40)
            if value & 0x80:
                self.trigger(index)

    def trigger(self, index: int) -> None:
        c = self.ch[index]
        c.on = c.dac
        if c.length == 0:
            c.length = c.max_length
        c.env.trigger()
        c.trig = True
        if index == 0:
            self.shadow = c.freq
            self.sweep_timer = self.sweep_period or 8
            self.sweep_on = bool(self.sweep_period or self.sweep_shift)
            if self.sweep_shift and self.sweep_target() > 0x7FF:
                c.on = False
        elif index == 3 and c.on:
            self.noise_hits.append((self.nr43, c.env.vol))

    # ---- lo que se oye -----------------------------------------------------------------------------------------

    def panned(self, index: int) -> bool:
        """El canal sale por alguna bocina (NR51)."""
        return bool(self.regs[0x15] >> index & 0x11)

    def wave_octaves(self) -> int:
        """Cuántas veces se repite el dibujo de la wave RAM en sus 32 pasos (1, 2 o 4)."""
        steps = [b >> s & 15 for b in self.regs[0x20:0x30] for s in (4, 0)]
        repeats = 1
        for size in (16, 8):
            if steps[:size] * (32 // size) == steps and len(set(steps)) > 1:
                repeats = 32 // size
        return repeats


def noise_hz(nr43: int) -> float:
    divisor = nr43 & 7 or 0.5
    return 524_288 / divisor / 2 ** ((nr43 >> 4) + 1)


def noise_pitch(nr43: int) -> int:
    """Una "altura" para agrupar los golpes de ruido: 3 pasos por octava de su frecuencia, +12 en el modo corto (más tonal)."""
    return 24 + round(3 * math.log2(noise_hz(nr43))) + (12 if nr43 & 8 else 0)


class Recorder:
    """Registra el estado de los cuatro canales cada cuadro y al final arma la IR."""

    def __init__(self, apu: Apu, frames: int):
        self.apu = apu
        self.frames = frames
        self.tracks = {c: ir.Track.silent(frames) for c in ir.TONAL}
        self.noise_on = [False] * frames
        self.noise_hits: list[tuple[int, int, int]] = []  # (cuadro, NR43, volumen)
        self.wave_repeats: set[int] = set()

    def capture(self, f: int) -> None:
        apu = self.apu
        for index, name in enumerate(ir.TONAL):
            c, track = apu.ch[index], self.tracks[name]
            vol = apu.wave_vol if index == 2 else c.env.vol
            if apu.power and c.on and vol > 0 and apu.panned(index) and c.freq < 0x7FF:
                if index == 2:
                    repeats = apu.wave_octaves()
                    self.wave_repeats.add(repeats)
                    track.freq[f] = 65_536 / (2048 - c.freq) * repeats
                else:
                    track.freq[f] = 131_072 / (2048 - c.freq)
                    track.duty[f] = c.duty
                track.vol[f] = vol
            track.trig[f] = c.trig
            c.trig = False
        noise = apu.ch[3]
        self.noise_on[f] = apu.power and noise.on and noise.env.vol > 0 and apu.panned(3)
        for nr43, vol in apu.noise_hits:
            if vol or noise.env.up:
                self.noise_hits.append((f, nr43, vol))
        apu.noise_hits.clear()

    def to_ir(self, name: str, game: str, source: str, frames: int | None = None) -> ir.SongIR:
        from .nsf import tonal_notes

        frames = frames or self.frames
        tracks = {c: ir.Track(t.freq[:frames], t.vol[:frames], t.duty[:frames], t.trig[:frames]) for c, t in self.tracks.items()}
        song = ir.SongIR(name, game, frames, tracks, {c: [] for c in ir.CHANNELS}, None, source=source)
        for channel in ir.TONAL:
            song.notes[channel] = tonal_notes(tracks[channel])
        hits = [h for h in self.noise_hits if h[0] < frames]
        for i, (f, nr43, _vol) in enumerate(hits):
            following = hits[i + 1][0] if i + 1 < len(hits) else frames
            if following == f:
                continue  # dos disparos en el mismo cuadro: cuenta el último
            limit = min(following, f + NOISE_MAX_FRAMES)
            duration = 1
            while f + duration < limit and self.noise_on[f + duration]:
                duration += 1
            song.notes["Noise"].append(ir.Note(f, noise_pitch(nr43), duration))
        if self.wave_repeats - {1}:
            song.warn("la onda de CH3 repite su dibujo dentro de la wave RAM: su altura se subió de octava para el triángulo")
        if not any(song.notes[c] for c in ir.TONAL):
            song.warn("no se oyó ninguna nota en los canales tonales (¿la pista está vacía?)")
        return song
