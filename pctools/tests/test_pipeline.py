"""Pruebas de las herramientas de PC de la fase 2: stream FRS, charts, colocación y datos de la canción de prueba."""

import json
import random
import re
from pathlib import Path

import pytest

from gbband_tools import audio_gb as gb
from gbband_tools import chartgen, layout

ROOT = Path(__file__).resolve().parents[2]
SONG = ROOT / "src" / "songs" / "demo"


# ---- pitch y formas de onda ----------------------------------------------------------------------

def test_pitch_pulso():
    # La4 (440 Hz): x = 2048 - 131072/440 = 1750.1 -> 1750; la frecuencia real queda a < 0.1 % del objetivo
    assert gb.pulse_reg(440.0) == 1750
    assert abs(131072 / (2048 - 1750) - 440) / 440 < 0.001
    with pytest.raises(ValueError):
        gb.pulse_reg(30.0)  # por debajo del rango del pulso (~64 Hz)


def test_pitch_wave():
    # La2 (110 Hz) en la onda de 32 pasos: x = 2048 - 65536/110 = 1452.2
    assert gb.wave_reg(110.0) == 1452
    assert gb.wave_reg(33.0) == 62
    with pytest.raises(ValueError):
        gb.wave_reg(20.0)


def test_triangulo_en_wave_ram():
    wave = gb.triangle_wave_ram()
    assert len(wave) == 16
    nibbles = [n for b in wave for n in (b >> 4, b & 15)]
    assert nibbles == list(range(15, -1, -1)) + list(range(16))


# ---- formato FRS ---------------------------------------------------------------------------------

def random_frames(rng: random.Random, n: int) -> list[gb.FrameWrites]:
    frames = [gb.FrameWrites() for _ in range(n)]
    for fw in frames:
        if rng.random() < 0.3:
            for ch in range(4):
                if rng.random() < 0.5:
                    regs = [r for r in range(5) if not (ch in (1, 3) and r == 0)]
                    for r in rng.sample(regs, rng.randint(1, len(regs))):
                        fw.set(ch, r, rng.randrange(256))
    frames[0].wave = bytes(rng.randrange(256) for _ in range(16))
    frames[-1].end = True
    return frames


@pytest.mark.parametrize("seed", range(5))
def test_frs_ida_y_vuelta(seed):
    rng = random.Random(seed)
    frames = random_frames(rng, 700)
    stream, offsets = gb.encode_stream(frames)
    decoded = gb.decode_stream(stream)
    assert len(decoded) == len(frames)
    for original, got in zip(frames, decoded):
        assert got.channels == original.channels
        assert got.wave == original.wave
        assert got.end == original.end
    assert len(offsets) == len(frames) and offsets == sorted(offsets)


def test_frs_rachas_de_vacios_largas():
    frames = [gb.FrameWrites() for _ in range(1000)]
    frames[0].set(0, 2, 0xF0)
    frames[-1].end = True
    stream, _ = gb.encode_stream(frames)
    assert len(gb.decode_stream(stream)) == 1000
    assert len(stream) < 30  # 1000 cuadros vacíos caben en unos pocos bytes


def test_frs_break_at_empieza_registro():
    frames = [gb.FrameWrites() for _ in range(300)]
    frames[-1].end = True
    stream, offsets = gb.encode_stream(frames, break_at={100})
    assert stream[offsets[100]] & 0x80  # el cuadro 100 abre una racha propia
    assert offsets[100] != offsets[99]


def test_frs_canal_sin_registro_cero():
    fw = gb.FrameWrites()
    fw.set(1, 0, 1)
    with pytest.raises(ValueError):
        gb.encode_frame(fw)


# ---- colocación y charts ---------------------------------------------------------------------------

def test_velocidades_de_la_rom():
    """La tabla de velocidades de highway.asm es la de layout.speed_8_8."""
    text = (ROOT / "src" / "highway.asm").read_text(encoding="utf-8")
    m = re.search(r"SpeedTable:\s*dw ([\d, ]+)", text)
    assert m
    assert [int(x) for x in m.group(1).split(",")] == [layout.speed_8_8(d) for d in layout.DIFFICULTIES]


def test_error_de_colocacion():
    s = layout.speed_8_8("facil")
    worst_a = max(abs(layout.error_px(f, s, "A")) for f in range(2000))
    worst_b = max(abs(layout.error_px(f, s, "B")) for f in range(2000))
    assert worst_a <= 4.0 and worst_b <= 1.0
    assert layout.tiles_used("A") == 10 and layout.tiles_used("B") == 70


def test_separacion_minima_del_mismo_carril():
    # En B una gema puede cruzar dos filas: 16 px; en A, 8 px
    s = layout.speed_8_8("experto")
    assert layout.min_lane_gap_frames(s, "A") == 6
    assert layout.min_lane_gap_frames(s, "B") == 12
    assert layout.conflicts([(1000, 1), (1001, 1)], s, "B") == 1  # pegadas: comparten tiles
    assert layout.conflicts([(1000, 1), (1000 + 12, 1)], s, "B") == 0  # a la separación mínima nunca chocan
    assert layout.conflicts([(1000, 1), (1001, 2)], s, "B") == 0  # en carriles distintos no importa


def test_chart_ida_y_vuelta():
    chart = [(10, 1), (300, 0b10100), (301, 8), (900, 2)]
    data = chartgen.chart_bytes(chart)
    assert data[-2:] == bytes([0, 0xFF])
    assert chartgen.parse_chart(data) == chart
    assert max(data[0::2]) <= 255  # deltas de un byte (con rellenos de 255 cuando hace falta)


def test_check_playable():
    chartgen.check_playable([(5, 0b00011), (9, 0b11000)])
    with pytest.raises(ValueError):
        chartgen.check_playable([(5, 0b00101)])  # verde + amarillo
    with pytest.raises(ValueError):
        chartgen.check_playable([(5, 0b10100)])  # amarillo + naranja


# ---- la canción de prueba ------------------------------------------------------------------------------

def test_cancion_demo_coherente():
    info = json.loads((SONG / "notes.json").read_text(encoding="utf-8"))
    assert info["lead_in"] >= 160  # las notas ya están cayendo cuando empieza el audio (anticipación fácil: 156 cuadros)
    for diff in layout.DIFFICULTIES:
        chart = [tuple(n) for n in info["charts"][diff]]
        assert chart
        chartgen.check_playable(chart)
        chartgen.check_layout(chart, diff)
        on_ch1 = {info["lead_in"] + f for f in info["melody_audio_frames"]}
        assert all(f in on_ch1 for f, _ in chart), "toda nota del chart debe salir de una nota de la melodía"
        # el chart de la ROM es el mismo que el de notes.json
        data = (SONG / f"chart_guitarra_{diff}.bin").read_bytes()
        assert chartgen.parse_chart(data) == chart
    # el stream decodificado tiene las altas de nota que dice el generador
    stream = (SONG / "stream_b.bin").read_bytes() + (SONG / "stream_c.bin").read_bytes()
    decoded = gb.decode_stream(stream)  # (stream_c.bin trae un byte de relleno si el stream cabe en el banco B)
    ons = gb.note_on_frames(decoded)
    assert [len(ons[c]) for c in range(4)] == [len(info["note_on_audio_frames"][str(c)]) for c in range(4)]
    assert len(decoded) == info["audio_frames"] + 1
    assert decoded[-1].end


def test_dificultades_mas_ralas_hacia_facil():
    info = json.loads((SONG / "notes.json").read_text(encoding="utf-8"))
    sizes = [len(info["charts"][d]) for d in layout.DIFFICULTIES]
    assert sizes == sorted(sizes)
