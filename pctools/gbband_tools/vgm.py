"""VGM a IR: las escrituras grabadas al APU de la Game Boy (DMG), con sus tiempos, pasadas por `gbapu.py`.

    uv run gbband import-song "songs_src/Juego - Pista.vgz" --name juego_pista

Un VGM ya trae cada escritura a $FF10-$FF3F (comando $B3) separada por esperas en muestras de 44 100 Hz, así que no
hace falta correr el código del juego como en un NSF o un GBS. `.vgz` es el mismo archivo comprimido con gzip. El
archivo se lee con el lector genérico de bandcore (el mismo de GENBand y NGBand). Solo se aceptan VGM de Game Boy: los
de otros chips (Sega, YM2612...) se rechazan con un mensaje. El título y el juego salen de la etiqueta GD3, y la
duración, de la que dice el archivo (una vuelta, con la introducción); `--duration` graba más segundos repitiendo desde
el punto de repetición.
"""

from __future__ import annotations

from pathlib import Path

from bandcore import detect
from bandcore import vgm as core

from . import gbapu, ir

SAMPLE_HZ = core.SAMPLE_RATE


def other_chips(vgm: core.Vgm) -> list[str]:
    """Los otros chips que declara la cabecera, con su nombre para mostrar."""
    return [detect.chip_name(chip, vgm) for chip in vgm.clocks if chip != "gb_dmg"]


def run(path: Path, seconds: float | None = None) -> tuple[ir.SongIR, core.Vgm]:
    vgm = core.read_vgm(path)
    if "gb_dmg" not in vgm.clocks:
        chips = other_chips(vgm)
        raise SystemExit(f"{path.name} no es música de Game Boy" + (f" (es de {', '.join(chips)})" if chips else "")
                         + ": solo se importan VGM del APU de la Game Boy (DMG)")
    total = vgm.total_samples
    if seconds:
        total = round(seconds * SAMPLE_HZ) if vgm.loop_write is not None else min(total, round(seconds * SAMPLE_HZ))
    frames = max(1, int(total * gbapu.CPU_HZ / SAMPLE_HZ) // gbapu.FRAME_CYCLES)
    apu = gbapu.Apu()
    recorder = gbapu.Recorder(apu, frames)
    f = 0
    for w in core.looped_writes(vgm, total, "gb_dmg"):
        time = w.sample * gbapu.CPU_HZ // SAMPLE_HZ
        while f < frames and (f + 1) * gbapu.FRAME_CYCLES <= time:
            apu.run_until((f + 1) * gbapu.FRAME_CYCLES - 1)
            recorder.capture(f)
            f += 1
        if f >= frames:
            break
        apu.run_until(time)
        apu.write(0xFF10 + w.reg, w.value)
    while f < frames:
        apu.run_until((f + 1) * gbapu.FRAME_CYCLES - 1)
        recorder.capture(f)
        f += 1
    song = recorder.to_ir(path.stem, vgm.game, "VGM")
    if vgm.flags.get("gb_dmg", 0) & 1:
        song.warn("el VGM trae dos Game Boy: solo se importa la primera")
    if other_chips(vgm):
        song.warn(f"el VGM también usa {', '.join(other_chips(vgm))}: solo se importa la Game Boy")
    return song, vgm


def load(path: Path, options) -> tuple[ir.SongIR, str, str]:
    song, vgm = run(path, options.duration)
    return song, vgm.title or path.stem, vgm.game
