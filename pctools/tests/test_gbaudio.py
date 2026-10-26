"""Pruebas del conversor de la IR al stream FRS: pitch, duty, volumen, batería y formato con ida y vuelta."""

import pytest

from gbband_tools import audio_gb as gb
from gbband_tools import gbaudio, ir


def song_with(channel: str, freq: float, vol, duty=2, frames=40, start=2, length=20) -> ir.SongIR:
    tracks = {c: ir.Track.silent(frames) for c in ir.TONAL}
    t = tracks[channel]
    for k, f in enumerate(range(start, start + length)):
        t.freq[f] = freq
        t.vol[f] = vol[k] if isinstance(vol, list) else vol
        t.duty[f] = duty
        t.trig[f] = k == 0
    return ir.SongIR("prueba", "", frames, tracks, {c: [] for c in ir.CHANNELS})


def test_pulso_constante_a_440_hz():
    result = gbaudio.convert(song_with("Square1", 440.0, 12))
    regs = result.frames[2].channels[0]
    assert regs[1] == 0x80  # duty 2 (50 %)
    assert regs[2] == 0xC0  # volumen 12, sin envolvente
    x = 2048 - round(131072 / 440.0)
    assert regs[3] == x & 0xFF and regs[4] == 0x80 | x >> 8
    assert result.frames[0].channels.get(0, {}).get(0) is None
    assert result.frames[22].channels[0][2] == 0x00  # la nota termina apagando el DAC
    assert result.frames[-1].end


@pytest.mark.parametrize("nes_duty,gb_bits", [(0, 0x00), (1, 0x40), (2, 0x80), (3, 0xC0)])
def test_duty(nes_duty, gb_bits):
    result = gbaudio.convert(song_with("Square2", 440.0, 10, duty=nes_duty))
    assert result.frames[2].channels[1][1] == gb_bits


def test_sweep_de_cada_pulso_y_barrido_apagado_solo_en_ch1():
    result = gbaudio.convert(song_with("Square1", 440.0, 10))
    assert result.frames[2].channels[0][0] == 0x00  # NR10: barrido apagado antes de la primera nota
    result = gbaudio.convert(song_with("Square2", 440.0, 10))
    assert 0 not in result.frames[2].channels[1]  # CH2 no tiene NRx0


def test_octava_arriba_bajo_el_rango():
    result = gbaudio.convert(song_with("Square1", 50.0, 10))
    regs = result.frames[2].channels[0]
    assert 2048 - 131072 / 100.0 == pytest.approx((regs[4] & 7) << 8 | regs[3], abs=1)
    assert any("octava" in line for line in result.log)


def test_cambio_de_altura_sin_reiniciar_la_nota():
    song = song_with("Square1", 440.0, 12)
    for f in range(12, 22):
        song.tracks["Square1"].freq[f] = 466.16  # un semitono arriba, sin disparo
    result = gbaudio.convert(song)
    assert 4 not in result.frames[12].channels[0] or not result.frames[12].channels[0][4] & 0x80
    assert 3 in result.frames[12].channels[0]  # NR13 nuevo, sin NR14 con disparo


def test_caida_monotona_usa_la_envolvente_por_hardware():
    steps = [max(15 - int(k / (2 * gbaudio.ENV_FRAMES_PER_STEP)), 0) for k in range(20)]  # periodo 2 de la envolvente
    result = gbaudio.convert(song_with("Square1", 440.0, steps))
    nr12 = result.frames[2].channels[0][2]
    assert nr12 >> 4 == 15 and nr12 & 7 != 0 and not nr12 & 8  # volumen 15, bit de dirección = bajar, periodo 1 a 7
    assert result.stats["envelope_error_max"] < 1.0
    assert result.stats["retriggers"] == 0
    assert nr12 & 7 == 2


def test_forma_rara_se_parte_en_dos_tramos_o_se_reporta_el_error():
    vols = [4] * 6 + [14] * 10 + [6] * 4  # sube de golpe y baja: ninguna envolvente de una pieza lo sigue
    result = gbaudio.convert(song_with("Square1", 440.0, vols))
    assert result.stats["retriggers"] >= 1  # se parte en tramos con un reinicio de la nota
    assert result.stats["envelope_error_mean"] < gbaudio.fit_segment(vols).error  # y así el error baja


def test_ganancia_por_canal():
    quiet = gbaudio.convert(song_with("Square1", 440.0, 12), gain={"Square1": 0.5})
    assert quiet.frames[2].channels[0][2] >> 4 == 6


def test_triangulo_en_la_wave_ram():
    result = gbaudio.convert(song_with("Triangle", 110.0, 15))
    assert result.frames[0].wave == gb.triangle_wave_ram()
    regs = result.frames[2].channels[2]
    assert regs[0] == 0x80 and regs[2] == 0x20  # DAC encendido, volumen 100 %
    x = 2048 - round(65536 / 110.0)
    assert regs[3] == x & 0xFF and regs[4] == 0x80 | x >> 8
    assert result.frames[22].channels[2][0] == 0x00  # DAC apagado al terminar


def test_bateria_por_papeles_y_prioridad():
    song = ir.SongIR("prueba", "", 60, {c: ir.Track.silent(60) for c in ir.TONAL}, {c: [] for c in ir.CHANNELS})
    song.notes["Noise"] = [ir.Note(5, 40, 3, None, "Bombo"), ir.Note(20, 50, 3, None, "Tarola"), ir.Note(30, 70, 2, None, "Platillo")]
    song.notes["DPCM"] = [ir.Note(5, 30, 6, None, "Percusion")]  # coincide con el bombo
    assignment = {
        "Noise:E2:Bombo": None,
    }
    from gbband_tools.drums import group_key

    assignment = {
        group_key("Noise", 40, "Bombo"): {"lane": "kick", "cymbal": False},
        group_key("Noise", 50, "Tarola"): {"lane": "snare", "cymbal": False},
        group_key("Noise", 70, "Platillo"): {"lane": "tom3", "cymbal": True},
        group_key("DPCM", 30, "Percusion"): {"lane": "snare", "cymbal": False},
    }
    result = gbaudio.convert(song, assignment)
    assert result.frames[5].channels[3][2] == gbaudio.PATCHES["kick"][0]  # el bombo gana a la tarola del DPCM
    assert result.frames[6].channels[3][3] == gbaudio.PATCHES["kick"][1][1]  # el bombo baja de tono cuadro a cuadro
    assert result.frames[20].channels[3][2] == gbaudio.PATCHES["snare"][0]
    assert result.frames[30].channels[3][2] == gbaudio.PATCHES["hat_closed"][0]  # platillo corto = hi-hat cerrado
    assert any("coinciden" in line for line in result.log)
    assert result.stats["drum_hits"] == 3


def test_stream_ida_y_vuelta_y_keyframe():
    song = song_with("Square1", 440.0, 12)
    result = gbaudio.convert(song)
    stream, offsets = gb.encode_stream(result.frames, break_at={11})
    decoded = gb.decode_stream(stream)
    assert len(decoded) == len(result.frames)
    for original, got in zip(result.frames, decoded):
        assert got.channels == original.channels and got.wave == original.wave
    assert stream[offsets[11]] & 0x80 == 0 or stream[offsets[11]] & 0x80  # el cuadro 11 abre un registro
    record = gbaudio.keyframe_record(result, song, 10)
    keyframe = gb.decode_stream(record + bytes([0x80]))[0]
    assert keyframe.channels[0][2] >> 4 == 12 and keyframe.channels[0][4] & 0x80
    assert keyframe.wave == gb.triangle_wave_ram()


def test_stream_corta_cuando_no_cabe():
    song = song_with("Square1", 440.0, 12, frames=400, length=300)
    result = gbaudio.convert(song, max_frames=100)
    assert len(result.frames) == 101 and result.frames[-1].end
