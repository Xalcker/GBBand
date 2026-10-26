"""Backend de audio de la Game Boy: de la IR a un stream FRS (ver audio_gb.py).

Mapeo de canales (docs/diseno.md):
    Pulso 1 -> CH1 · Pulso 2 -> CH2 · Triángulo -> CH3 (wave RAM con el triángulo de 32 pasos) ·
    Ruido y DPCM -> CH4 (parches de batería por papel: bombo, tarola, hi-hat, platillo, toms)

Tiempo: 1 cuadro NES = 1 cuadro GB. El tempo queda 0.6 % más lento (59.73 contra 60.10 Hz), imperceptible, y los
charts y el audio comparten el mismo eje sin conversión.

Volumen: un pulso de la GB no cambia de volumen sin reiniciarse (no se usa el "zombie mode"), así que cada nota se
ajusta a la mejor de estas formas, y el error se reporta en el log:
  1. volumen constante: NRx2 = vol << 4
  2. caída monótona: envolvente por hardware, NRx2 = vol << 4 | periodo (1 a 7; cada paso dura periodo/64 s)
  3. dos tramos (constante o caída) con un reinicio de la nota en medio, si eso baja bastante el error
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import audio_gb as gb
from . import ir
from .audio_gb import FrameWrites

GB_FPS = 4_194_304 / 70_224
ENV_FRAMES_PER_STEP = GB_FPS / 64  # un paso de la envolvente por hardware en cuadros por unidad de periodo
PULSE_MIN_HZ = 64.0
WAVE_MIN_HZ = 32.0
FIT_GOOD = 0.6  # error medio (en pasos de volumen) bajo el cual no se busca otro ajuste
SPLIT_GAIN = 0.55  # un reinicio de nota solo vale la pena si el error baja a esta fracción
MIN_SPLIT = 5  # cuadros mínimos de cada tramo

# Parches de batería en CH4: (NR42, [NR43 en cada cuadro del parche]). El NR44 siempre dispara ($80).
# Los timbres están elegidos a ojo (se calibran de oído, ver docs/decisiones.md).
PATCHES = {
    "kick": (0xF1, [0x55, 0x65, 0x75, 0x77]),
    "snare": (0xD1, [0x43, 0x33]),
    "hat_closed": (0x61, [0x11]),
    "hat_open": (0x73, [0x11]),
    "crash": (0xA3, [0x12]),
    "tom_hi": (0xA1, [0x5B]),
    "tom_mid": (0xA1, [0x6B]),
    "tom_lo": (0xA1, [0x7B]),
}
PATCH_PRIORITY = {"kick": 5, "snare": 4, "crash": 3, "tom_hi": 2, "tom_mid": 2, "tom_lo": 2, "hat_open": 1, "hat_closed": 1}
ROLE_CLASS = {"kick": "kick", "snare": "snare", "tom1": "tom_hi", "tom2": "tom_mid", "tom3": "tom_lo"}


@dataclass
class AudioResult:
    frames: list[FrameWrites]  # un FrameWrites por cuadro; el último lleva la marca de fin
    log: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)  # por canal tonal: estado modelado en cada cuadro (para los keyframes)


# ---- ajuste de volumen --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Fit:
    vol: int  # volumen inicial
    period: int  # 0 = constante; 1 a 7 = cae un paso cada `period`/64 s
    error: float  # error medio absoluto (pasos de volumen)

    def at(self, k: int) -> int:
        if not self.period:
            return self.vol
        return max(self.vol - int(k / (self.period * ENV_FRAMES_PER_STEP)), 0)


def fit_segment(vols: list[int]) -> Fit:
    """La mejor envolvente de una sola pieza para los volúmenes de una nota."""
    n = len(vols)
    best: Fit | None = None
    for c in range(1, 16):
        fit = Fit(c, 0, sum(abs(v - c) for v in vols) / n)
        if best is None or fit.error < best.error:
            best = fit
    for v0 in {max(1, min(15, vols[0] + d)) for d in (-1, 0, 1)}:
        for p in range(1, 8):
            fit = Fit(v0, p, sum(abs(v - Fit(v0, p, 0).at(k)) for k, v in enumerate(vols)) / n)
            if fit.error < best.error - 1e-9:
                best = fit
    return best


def fit_note(vols: list[int]) -> list[tuple[int, Fit]]:
    """Uno o dos tramos [(cuadro de inicio dentro de la nota, ajuste)]."""
    whole = fit_segment(vols)
    if whole.error <= FIT_GOOD or len(vols) < 2 * MIN_SPLIT:
        return [(0, whole)]
    best_split, best_error = None, whole.error
    for k in range(MIN_SPLIT, len(vols) - MIN_SPLIT + 1):
        a, b = fit_segment(vols[:k]), fit_segment(vols[k:])
        error = (a.error * k + b.error * (len(vols) - k)) / len(vols)
        if error < best_error:
            best_split, best_error = (k, a, b), error
    if best_split and best_error <= whole.error * SPLIT_GAIN:
        k, a, b = best_split
        return [(0, a), (k, b)]
    return [(0, whole)]


# ---- pitch -----------------------------------------------------------------------------------------------------

def fold(freq: float, minimum: float, log: list[str], what: str) -> float:
    """Sube de octava lo que queda por debajo del rango del canal (y lo avisa)."""
    folded = 0
    while freq < minimum:
        freq *= 2
        folded += 1
    if folded:
        log.append(f"{what}: {freq / 2 ** folded:.1f} Hz está bajo el rango ({minimum:.0f} Hz); se sube {folded} octava(s)")
    return freq


class Pitch:
    """x de 11 bits para un canal; recuerda las notas que tuvo que subir de octava (un aviso por altura)."""

    def __init__(self, log: list[str], what: str, pulse: bool):
        self.log, self.what, self.pulse = log, what, pulse
        self.seen: set[int] = set()
        self.minimum = PULSE_MIN_HZ if pulse else WAVE_MIN_HZ

    def x(self, freq: float) -> int:
        if freq < self.minimum:
            key = round(ir.hz_midi(freq))
            if key not in self.seen:
                self.seen.add(key)
                fold(freq, self.minimum, self.log, f"{self.what} {ir.midi_to_name(key)}")
            freq = fold(freq, self.minimum, [], "")
        value = gb.pulse_reg(freq) if self.pulse else gb.wave_reg(freq)
        return value


# ---- conversión ------------------------------------------------------------------------------------------------

def segments(track: ir.Track) -> list[tuple[int, int]]:
    """Las notas de un canal tonal: [(primer cuadro, último cuadro)] donde suena (freq y volumen > 0)."""
    result = []
    start = None
    for i in range(len(track.freq)):
        active = track.freq[i] > 0 and track.vol[i] > 0
        if start is not None and (not active or track.trig[i]):
            result.append((start, i - 1))
            start = None
        if active and start is None:
            start = i
    if start is not None:
        result.append((start, len(track.freq) - 1))
    return result


def scale(vol: int, gain: float) -> int:
    return max(1, min(15, round(vol * gain))) if vol > 0 else 0


def emit_pulse(song: ir.SongIR, channel: str, ch: int, frames: list[FrameWrites], gain: float, log: list[str],
               errors: list[float], model: list, retriggers: list[int]) -> None:
    track = song.tracks[channel]
    pitch = Pitch(log, f"{channel}", True)
    n = len(frames) - 1
    for first, last in segments(track):
        if first >= n:
            break
        last = min(last, n - 1)
        vols = [scale(track.vol[i], gain) for i in range(first, last + 1)]
        parts = fit_note(vols)
        for index, (offset, fit) in enumerate(parts):
            end_offset = parts[index + 1][0] if index + 1 < len(parts) else len(vols)
            errors.append(fit.error)
            start = first + offset
            fw = frames[start]
            x = pitch.x(track.freq[start])
            if ch == 0 and start == first and not any(frames[j].channels.get(0) for j in range(start)):
                fw.set(0, 0, 0x00)  # barrido apagado antes de la primera nota
            fw.set(ch, 1, track.duty[start] << 6)
            fw.set(ch, 2, fit.vol << 4 | fit.period)
            fw.set(ch, 3, x & 0xFF)
            fw.set(ch, 4, 0x80 | x >> 8)
            if index:
                retriggers[0] += 1
            prev_x, prev_duty = x, track.duty[start]
            for i in range(start + 1, first + end_offset):
                regs = frames[i].channels.setdefault(ch, {})
                x = pitch.x(track.freq[i])
                if track.duty[i] != prev_duty:
                    regs[1] = track.duty[i] << 6
                    prev_duty = track.duty[i]
                if x != prev_x:
                    regs[3] = x & 0xFF
                    if x >> 8 != prev_x >> 8:
                        regs[4] = x >> 8
                    prev_x = x
                if not regs:
                    del frames[i].channels[ch]
            for i in range(start, first + end_offset):
                model[i] = (fit.at(i - start), fit.period, prev_duty)
        nxt = last + 1
        if nxt < n and not (track.freq[nxt] > 0 and track.vol[nxt] > 0):
            frames[nxt].set(ch, 2, 0x00)  # DAC apagado: la nota termina


def emit_triangle(song: ir.SongIR, frames: list[FrameWrites], log: list[str], model: list) -> None:
    track = song.tracks["Triangle"]
    pitch = Pitch(log, "Triangle", False)
    n = len(frames) - 1
    frames[0].wave = gb.triangle_wave_ram()
    for first, last in segments(track):
        if first >= n:
            break
        last = min(last, n - 1)
        x = pitch.x(track.freq[first])
        fw = frames[first]
        fw.set(2, 0, 0x80)  # DAC encendido
        fw.set(2, 2, 0x20)  # volumen 100 %
        fw.set(2, 3, x & 0xFF)
        fw.set(2, 4, 0x80 | x >> 8)
        prev_x = x
        for i in range(first + 1, last + 1):
            x = pitch.x(track.freq[i])
            if x != prev_x:
                regs = frames[i].channels.setdefault(2, {})
                regs[3] = x & 0xFF
                if x >> 8 != prev_x >> 8:
                    regs[4] = x >> 8
                prev_x = x
        for i in range(first, last + 1):
            model[i] = (15, 0, 0)
        nxt = last + 1
        if nxt < n and not (track.freq[nxt] > 0 and track.vol[nxt] > 0):
            frames[nxt].set(2, 0, 0x00)  # DAC apagado


def patch_class(note: ir.Note, assignment: dict | None, key: str) -> str:
    item = (assignment or {}).get(key) or {}
    role, cymbal = item.get("lane"), bool(item.get("cymbal"))
    name = (note.instrument or "").lower()
    if role is None:  # sin papel asignado: por el nombre del instrumento, si no un hi-hat cerrado
        for words, guess in ((("bombo", "kick"), "kick"), (("tarola", "snare", "caja"), "snare"), (("abierto", "open"), "hat_open"),
                             (("crash",), "crash")):
            if any(w in name for w in words):
                return guess
        return "hat_closed"
    if cymbal and role not in ("kick", "snare"):
        if any(w in name for w in ("abierto", "open", "ride")):
            return "hat_open"
        if "crash" in name:
            return "crash"
        return "hat_closed"
    return ROLE_CLASS[role]


def emit_drums(song: ir.SongIR, frames: list[FrameWrites], assignment: dict | None, log: list[str], stats: dict) -> None:
    from .drums import group_key  # (evita un ciclo de importaciones)

    n = len(frames) - 1
    hits: dict[int, str] = {}
    conflicts = 0
    for channel in ir.DRUM_CHANNELS:
        for note in song.notes.get(channel, []):
            if note.frame >= n:
                continue
            cls = patch_class(note, assignment, group_key(channel, note.pitch, note.instrument))
            old = hits.get(note.frame)
            if old is not None:
                conflicts += 1
                if PATCH_PRIORITY[old] >= PATCH_PRIORITY[cls]:
                    continue
            hits[note.frame] = cls
    if conflicts:
        log.append(f"batería: {conflicts} golpes coinciden en el mismo cuadro (solo hay un canal de ruido): se queda el de más prioridad")
    stats["drum_hits"] = len(hits)
    ordered = sorted(hits)
    for index, frame in enumerate(ordered):
        env, seq = PATCHES[hits[frame]]
        limit = ordered[index + 1] if index + 1 < len(ordered) else n
        for k, nr43 in enumerate(seq):
            if frame + k >= limit or frame + k >= n:
                break
            fw = frames[frame + k]
            if k == 0:
                fw.set(3, 2, env)
                fw.set(3, 3, nr43)
                fw.set(3, 4, 0x80)
            else:
                fw.set(3, 3, nr43)


def convert(song: ir.SongIR, assignment: dict | None = None, gain: dict[str, float] | None = None,
            max_frames: int | None = None) -> AudioResult:
    """La IR a cuadros de escrituras del APU. `max_frames` corta la canción (si el stream no cabe en su slot)."""
    gain = gain or {}
    total = min(song.length_frames, max_frames) if max_frames else song.length_frames
    frames = [FrameWrites() for _ in range(total + 1)]
    log: list[str] = []
    errors: list[float] = []
    retriggers = [0]
    model = {c: [None] * (total + 1) for c in ir.TONAL}
    emit_pulse(song, "Square1", 0, frames, gain.get("Square1", 1.0), log, errors, model["Square1"], retriggers)
    emit_pulse(song, "Square2", 1, frames, gain.get("Square2", 1.0), log, errors, model["Square2"], retriggers)
    emit_triangle(song, frames, log, model["Triangle"])
    stats: dict = {}
    emit_drums(song, frames, assignment, log, stats)
    # silencio final y marca de fin
    last = frames[total]
    last.set(0, 2, 0x00)
    last.set(1, 2, 0x00)
    last.set(2, 0, 0x00)
    last.set(3, 2, 0x00)
    last.end = True
    stats["pulse_notes"] = len(errors)
    stats["envelope_error_mean"] = sum(errors) / len(errors) if errors else 0.0
    stats["envelope_error_max"] = max(errors, default=0.0)
    stats["bad_notes"] = sum(1 for e in errors if e > 1.5)
    stats["retriggers"] = retriggers[0]
    if stats["bad_notes"]:
        log.append(f"volumen: {stats['bad_notes']} de {len(errors)} notas de pulso quedan con más de 1.5 pasos de error "
                   f"(medio {stats['envelope_error_mean']:.2f}, máximo {stats['envelope_error_max']:.1f})")
    return AudioResult(frames, log, stats, model)


# ---- keyframes --------------------------------------------------------------------------------------------------

def keyframe_record(result: AudioResult, song: ir.SongIR, at: int, gain: dict[str, float] | None = None) -> bytes:
    """El estado completo de los 4 canales en el cuadro `at`, como un registro de cuadro FRS. Reinicia la nota vigente
    de cada canal con el volumen que tenía en ese cuadro (la caída por hardware empieza de nuevo desde ahí)."""
    fw = FrameWrites(wave=gb.triangle_wave_ram())
    pitch_log: list[str] = []
    for ch, channel in enumerate(("Square1", "Square2", "Triangle")):
        state = result.model[channel][at] if at < len(result.model[channel]) else None
        track = song.tracks[channel]
        if state is None:
            fw.set(ch, 2 if ch < 2 else 0, 0x00)
            continue
        vol, period, duty = state
        if ch == 2:
            x = Pitch(pitch_log, "Triangle", False).x(track.freq[at])
            fw.set(2, 0, 0x80)
            fw.set(2, 2, 0x20)
            fw.set(2, 3, x & 0xFF)
            fw.set(2, 4, 0x80 | x >> 8)
        else:
            x = Pitch(pitch_log, channel, True).x(track.freq[at])
            fw.set(ch, 1, duty << 6)
            fw.set(ch, 2, vol << 4 | (period if vol else 0))
            fw.set(ch, 3, x & 0xFF)
            fw.set(ch, 4, 0x80 | x >> 8)
            if vol == 0:
                fw.set(ch, 2, 0x00)
    fw.set(3, 2, 0x00)
    return gb.encode_frame(fw)
