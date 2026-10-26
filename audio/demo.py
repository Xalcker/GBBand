"""Canción de prueba "ENSAYO" (original de GBBand, GPL-2.0-or-later): ~32 s en La menor a 120 BPM.

    uv run python audio/demo.py

Compone la melodía, el arpegio, el bajo y la batería directamente como registros del APU (IR mínima: la
fase 3 la reemplaza por la IR completa), y escribe en src/songs/demo/:
  song.asm       ficha de la canción y secciones de ROM (bancos 16 a 18)
  stream_b.bin / stream_c.bin   el stream FRS partido en los dos bancos de audio
  keyframes.bin  los 4 registros de estado completo
  chart_guitarra_<dificultad>.bin
  notes.json     lo que sabe el generador (cuadro de cada nota del chart y de cada alta de nota), para las pruebas

Canales: CH1 melodía (pulso 50 %), CH2 arpegio (pulso 25 %), CH3 bajo (triángulo en wave RAM), CH4 batería.
Los timbres y volúmenes están elegidos a ojo y se calibran de oído.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pctools"))

from gbband_tools import audio_gb as gb  # noqa: E402
from gbband_tools import chartgen, layout  # noqa: E402

OUT = ROOT / "src" / "songs" / "demo"
BEAT = 30  # cuadros por tiempo (~119.5 BPM a 59.73 Hz)
BARS = 16
LEAD_IN = 200  # cuadros antes de que empiece el audio (las notas ya están cayendo)
TAIL = 60  # silencio después de la última nota
AUDIO_FRAMES = BARS * 4 * BEAT
END_FRAME = LEAD_IN + AUDIO_FRAMES + TAIL

CHORDS = ["Am", "F", "C", "G"]
MELODY_POOL = {"Am": [69, 72, 74, 76, 79], "F": [65, 69, 72, 74, 77], "C": [67, 72, 74, 76, 79], "G": [67, 71, 74, 76, 79]}
ARP = {"Am": [57, 60, 64, 60], "F": [53, 57, 60, 57], "C": [55, 60, 64, 60], "G": [55, 59, 62, 59]}
BASS = {"Am": 45, "F": 41, "C": 48, "G": 43}
RHYTHM = [  # corcheas (0-7) con nota en cada compás, por sección de 4 compases
    {0, 2, 4, 6},
    {0, 2, 3, 4, 6},
    {0, 1, 2, 3, 4, 5, 6, 7},
    {0, 2, 3, 4, 5, 6, 7},
]

# Batería en el canal de ruido: (NR42 envolvente, NR43 reloj/ancho/divisor)
KICK = (0xF1, 0x6B)
SNARE = (0xB2, 0x43)
HAT = (0x71, 0x21)


def pulse_note(fw: gb.FrameWrites, ch: int, midi: int, duty: int, vol: int, period: int, first: bool = False) -> None:
    x = gb.pulse_reg(gb.midi_hz(midi))
    if ch == 0 and first:
        fw.set(0, 0, 0x00)  # barrido apagado
    fw.set(ch, 1, duty << 6)
    fw.set(ch, 2, vol << 4 | period)
    fw.set(ch, 3, x & 0xFF)
    fw.set(ch, 4, 0x80 | x >> 8)


def wave_note(fw: gb.FrameWrites, midi: int) -> None:
    x = gb.wave_reg(gb.midi_hz(midi))
    fw.set(2, 0, 0x80)  # DAC encendido
    fw.set(2, 2, 0x20)  # volumen 100 %
    fw.set(2, 3, x & 0xFF)
    fw.set(2, 4, 0x80 | x >> 8)


def compose() -> tuple[list[gb.FrameWrites], list[tuple[int, int]], dict]:
    rng = random.Random(7)
    frames = [gb.FrameWrites() for _ in range(AUDIO_FRAMES + 1)]
    frames[0].wave = gb.triangle_wave_ram()
    melody: list[tuple[int, int]] = []  # (cuadro de audio, altura)
    state = {0: None, 1: None, 2: None, 3: None}  # última nota por canal: (cuadro, registros)
    idx = 2
    for bar in range(BARS):
        chord = CHORDS[bar % 4]
        for beat in range(4):
            base = (bar * 4 + beat) * BEAT
            # bajo: en los tiempos 1 y 3; desde el compás 4, en los cuatro
            if beat in (0, 2) or bar >= 4:
                wave_note(frames[base], BASS[chord])
                frames[base + 24].set(2, 0, 0x00)  # DAC apagado: la nota termina
            # batería desde el compás 2
            if bar >= 2:
                env, clk = KICK if beat in (0, 2) else SNARE
                frames[base].set(3, 2, env)
                frames[base].set(3, 3, clk)
                frames[base].set(3, 4, 0x80)
            for half in range(2):
                e = beat * 2 + half
                f = base + half * (BEAT // 2)
                section = RHYTHM[bar // 4]
                if e in section:
                    pool = MELODY_POOL[chord]
                    idx = min(max(idx + rng.choice([-1, -1, 0, 1, 1]), 0), len(pool) - 1)
                    pulse_note(frames[f], 0, pool[idx], 2, 12, 3, first=not melody)
                    melody.append((f, pool[idx]))
                if bar >= 2:
                    pulse_note(frames[f], 1, ARP[chord][e % 4], 1, 7, 2)
                if bar >= 4 and half == 1 and beat not in (0, 2):  # hi-hat a contratiempo
                    frames[f].set(3, 2, HAT[0])
                    frames[f].set(3, 3, HAT[1])
                    frames[f].set(3, 4, 0x80)
    # silencio final y marca de fin
    last = frames[AUDIO_FRAMES]
    last.set(0, 2, 0x00)
    last.set(1, 2, 0x00)
    last.set(2, 0, 0x00)
    last.set(3, 2, 0x00)
    last.end = True
    return frames, melody, state


def keyframe_record(frames: list[gb.FrameWrites], at: int) -> bytes:
    """Estado completo de los 4 canales en el cuadro `at`: para cada canal, su última nota (si todavía suena)
    o su silencio. Reinicia la nota vigente (el volumen vuelve al inicial de la envolvente)."""
    window = {0: 36, 1: 36, 2: 24, 3: 12}  # cuánto dura audible la última nota de cada canal
    fw = gb.FrameWrites(wave=gb.triangle_wave_ram())
    for ch in range(4):
        start = None
        for f in range(at, max(at - window[ch], -1), -1):
            regs = frames[f].channels.get(ch, {})
            if regs.get(4, 0) & 0x80:
                start = f
                break
        if start is not None and ch == 2 and any(frames[f].channels.get(2, {}).get(0) == 0 for f in range(start + 1, at + 1)):
            start = None  # el bajo ya terminó (DAC apagado)
        if start is not None:
            for r, v in frames[start].channels[ch].items():
                fw.set(ch, r, v)
        else:
            silent = {0: 2, 1: 2, 2: 0, 3: 2}[ch]
            fw.set(ch, silent, 0x00)
    return gb.encode_frame(fw)


def asm_for(song: dict) -> str:
    lines = [
        "; Generado por audio/demo.py - no editar a mano",
        "; (song_format.inc ya lo incluye main.asm)",
        "",
        f'SECTION "Cancion demo A", ROMX[$4000], BANK[{song["bank"]}]',
        "SongDemo::",
        '    db "GBBS", 1',
        f'    db "{song["title"]:<16}"',
        f'    db "{song["game"]:<16}"',
        f'    dw {song["end"]}, {song["lead_in"]}',
        f'    db {song["beat"]}, %0001, 3',
    ]
    labels = {}
    for i, name in enumerate(chartgen.DIFFICULTIES):
        labels[i] = f"DemoChartGuitar{name.name.capitalize()}"
    for slot in range(16):
        lines.append(f"    dw {labels[slot]}" if slot in labels else "    dw 0")
    lines.append("    dw $4000")
    for k, (frame, offset) in enumerate(song["keyframes"]):
        bank = song["bank"] + 1 + offset // 16384
        lines.append(f"    dw {frame}")
        lines.append(f"    db {bank}")
        lines.append(f"    dw ${0x4000 + offset % 16384:04X}")
        lines.append(f"    dw DemoKeyframe{k}")
    lines.append("")
    for i, name in enumerate(chartgen.DIFFICULTIES):
        lines.append(f"{labels[i]}:")
        lines.append(f'    INCBIN "songs/demo/chart_guitarra_{name.name}.bin"')
    lines.append("")
    for k, size in enumerate(song["keyframe_sizes"]):
        lines.append(f"DemoKeyframe{k}:")
        lines.append(f'    INCBIN "songs/demo/keyframes.bin", {song["keyframe_offsets"][k]}, {size}')
    lines += [
        "",
        f'SECTION "Cancion demo B", ROMX[$4000], BANK[{song["bank"] + 1}]',
        '    INCBIN "songs/demo/stream_b.bin"',
        "",
        f'SECTION "Cancion demo C", ROMX[$4000], BANK[{song["bank"] + 2}]',
        '    INCBIN "songs/demo/stream_c.bin"',
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames, melody, _ = compose()

    key_frames = [0, AUDIO_FRAMES // 4, AUDIO_FRAMES // 2, 3 * AUDIO_FRAMES // 4]
    stream, offsets = gb.encode_stream(frames, break_at={k + 1 for k in key_frames})
    if len(stream) > 2 * 16384:
        raise SystemExit(f"el stream ({len(stream)} bytes) no cabe en 2 bancos")
    (OUT / "stream_b.bin").write_bytes(stream[:16384])
    (OUT / "stream_c.bin").write_bytes(stream[16384:] or b"\xff")

    records = [keyframe_record(frames, f) for f in key_frames]
    (OUT / "keyframes.bin").write_bytes(b"".join(records))
    sizes = [len(r) for r in records]
    starts = [sum(sizes[:i]) for i in range(len(sizes))]

    chart_info = {}
    for diff in chartgen.DIFFICULTIES:
        notes = [(LEAD_IN + f, p) for f, p in melody]
        chart = chartgen.make_chart(notes, diff, BEAT)
        chartgen.check_playable(chart)
        chartgen.check_layout(chart, diff.name)
        (OUT / f"chart_guitarra_{diff.name}.bin").write_bytes(chartgen.chart_bytes(chart))
        chart_info[diff.name] = chart

    decoded = gb.decode_stream(stream)
    note_ons = gb.note_on_frames(decoded)
    info = {
        "lead_in": LEAD_IN,
        "end_frame": END_FRAME,
        "beat": BEAT,
        "audio_frames": AUDIO_FRAMES,
        "stream_bytes": len(stream),
        "note_on_audio_frames": {str(ch): fr for ch, fr in note_ons.items()},
        "melody_audio_frames": [f for f, _ in melody],
        "charts": {name: [[f, m] for f, m in chart] for name, chart in chart_info.items()},
    }
    (OUT / "notes.json").write_text(json.dumps(info), encoding="utf-8")

    song = {
        "bank": 16,
        "title": "ENSAYO",
        "game": "GBBAND",
        "end": END_FRAME,
        "lead_in": LEAD_IN,
        "beat": BEAT,
        "keyframes": [(f, offsets[f + 1]) for f in key_frames],
        "keyframe_sizes": sizes,
        "keyframe_offsets": starts,
    }
    (OUT / "song.asm").write_text(asm_for(song), encoding="utf-8", newline="\n")
    print(f"stream: {len(stream)} bytes; melodía: {len(melody)} notas; charts: "
          + ", ".join(f"{n}={len(c)}" for n, c in chart_info.items()))
    for d in chartgen.DIFFICULTIES:
        n = layout.conflicts(chart_info[d.name], layout.speed_8_8(d.name), "B")
        print(f"  {d.name}: conflictos de colocación B = {n}")


if __name__ == "__main__":
    main()
