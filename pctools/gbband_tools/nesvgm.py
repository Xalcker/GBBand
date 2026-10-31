"""VGM del NES a IR: las escrituras al APU del NES (comando $B4) pasadas por el mismo APU emulado que un NSF.

    uv run gbband import-song "songs_src/Juego - Pista.vgz" --name juego_pista       (VGM del NES)

Un VGM ya trae las escrituras a $4000-$4017 con sus tiempos, así que no hace falta correr el 6502 como en un NSF:
`bandcore.nesapu.record_vgm` aplica las de cada cuadro del NES (60.1 Hz) al APU emulado y graba el estado de cada
canal igual que con un NSF. El canal extra del Famicom Disk System ($4040 en adelante) se ignora con un aviso. El
título y el juego salen de la etiqueta GD3.
"""

from __future__ import annotations

from pathlib import Path

from bandcore import nesapu
from bandcore import vgm as core

from . import ir, nsf


def run(path: Path, seconds: float | None = None) -> tuple[ir.SongIR, core.Vgm]:
    vgm = core.read_vgm(path)
    if "nes_apu" not in vgm.clocks:
        raise SystemExit(f"{path.name} no es música del NES: solo se importan VGM del APU del NES")
    total = vgm.total_samples
    if seconds:
        total = round(seconds * core.SAMPLE_RATE) if vgm.loop_write is not None else min(total, round(seconds * core.SAMPLE_RATE))
    rec, fds = nesapu.record_vgm(vgm, total)
    result = ir.SongIR(path.stem, vgm.game, rec.frames, rec.tracks, {c: [] for c in ir.CHANNELS}, None, source="VGM del NES")
    if fds:
        result.warn(f"el VGM usa el canal del Famicom Disk System ({fds} escrituras): se pierde")
    return nsf.build_ir(result, rec), vgm


def load(path: Path, options) -> tuple[ir.SongIR, str, str]:
    song, vgm = run(path, options.duration)
    return song, vgm.title or path.stem, vgm.game
