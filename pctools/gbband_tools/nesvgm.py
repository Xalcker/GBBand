"""VGM del NES a IR: las escrituras al APU del NES (comando $B4) pasadas por el mismo APU emulado que un NSF.

    uv run gbband import-song "songs_src/Juego - Pista.vgz" --name juego_pista       (VGM del NES)

Un VGM ya trae las escrituras a $4000-$4017 con sus tiempos, así que no hace falta correr el 6502 como en un NSF:
las de cada cuadro del NES (60.1 Hz) se aplican a `nsf.Apu` y `nsf.record` graba el estado de cada canal igual que
con un NSF. Los samples DPCM vienen en bloques de datos de tipo $C2 (escrituras a la RAM del NES). El canal extra
del Famicom Disk System ($4040 en adelante) se ignora con un aviso. El título y el juego salen de la etiqueta GD3.
"""

from __future__ import annotations

from pathlib import Path

from bandcore import vgm as core

from . import ir, nsf

BLOCK_NES_RAM = 0xC2  # bloque de datos: dirección (2 bytes) y los bytes que van ahí


def run(path: Path, seconds: float | None = None) -> tuple[ir.SongIR, core.Vgm]:
    vgm = core.read_vgm(path)
    if "nes_apu" not in vgm.clocks:
        raise SystemExit(f"{path.name} no es música del NES: solo se importan VGM del APU del NES")
    total = vgm.total_samples
    if seconds:
        total = round(seconds * core.SAMPLE_RATE) if vgm.loop_write is not None else min(total, round(seconds * core.SAMPLE_RATE))
    frames = max(1, int(total / core.SAMPLE_RATE * ir.NES_FPS))
    writes = list(core.looped_writes(vgm, total, "nes_apu"))
    memory = bytearray(0x10000)
    for block in vgm.blocks:
        if block.type == BLOCK_NES_RAM and len(block.data) > 2:
            start = block.data[0] | block.data[1] << 8
            data = block.data[2 : 2 + 0x10000 - start]
            memory[start : start + len(data)] = data

    apu = nsf.Apu()
    pos = 0
    fds = 0

    def play(f: int) -> None:
        nonlocal pos, fds
        end = (f + 1) * core.SAMPLE_RATE / ir.NES_FPS
        while pos < len(writes) and writes[pos].sample < end:
            w = writes[pos]
            if w.reg <= 0x17:
                apu.write(0x4000 + w.reg, w.value)
            else:
                fds += 1
            pos += 1

    tracks, noise_hits, dpcm_hits, noise_active = nsf.record(apu, frames, play, memory.__getitem__)
    result = ir.SongIR(path.stem, vgm.game, frames, tracks, {c: [] for c in ir.CHANNELS}, None, source="VGM del NES")
    if fds:
        result.warn(f"el VGM usa el canal del Famicom Disk System ({fds} escrituras): se pierde")
    return nsf.build_ir(result, tracks, noise_hits, dpcm_hits, noise_active), vgm


def load(path: Path, options) -> tuple[ir.SongIR, str, str]:
    song, vgm = run(path, options.duration)
    return song, vgm.title or path.stem, vgm.game
