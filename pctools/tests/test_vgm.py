"""Pruebas del APU de la Game Boy (`gbapu.py`) y del importador de VGM, con VGM sintéticos armados aquí."""

import gzip
from pathlib import Path

import pytest

from gbband_tools import gbapu, ir, vgm

SAMPLES_PER_FRAME = vgm.SAMPLE_HZ * gbapu.FRAME_CYCLES / gbapu.CPU_HZ  # 738.4


def write(reg: int, value: int) -> bytes:
    return bytes([0xB3, reg - 0xFF10, value])


def wait(samples: int) -> bytes:
    out = b""
    while samples > 0:
        step = min(samples, 0xFFFF)
        out += bytes([0x61]) + step.to_bytes(2, "little")
        samples -= step
    return out


def gd3(*tags: str) -> bytes:
    fields = list(tags) + [""] * (11 - len(tags))
    body = "".join(f + "\0" for f in fields).encode("utf-16-le")
    return b"Gd3 " + (0x100).to_bytes(4, "little") + len(body).to_bytes(4, "little") + body


def vgm_bytes(commands: bytes, total: int, loop_at: int | None = None, loop_samples: int = 0, gb: bool = True,
              tags: tuple[str, ...] = ("Pista", "", "Juego")) -> bytes:
    """Un VGM 1.61 con los datos en $100. `loop_at` es la posición dentro de `commands` a la que se repite."""
    header = bytearray(0x100)
    header[:4] = b"Vgm "
    header[0x08:0x0C] = (0x161).to_bytes(4, "little")
    header[0x18:0x1C] = total.to_bytes(4, "little")
    if loop_at is not None:
        header[0x1C:0x20] = (0x100 + loop_at - 0x1C).to_bytes(4, "little")
        header[0x20:0x24] = loop_samples.to_bytes(4, "little")
    header[0x34:0x38] = (0x100 - 0x34).to_bytes(4, "little")
    if gb:
        header[0x80:0x84] = gbapu.CPU_HZ.to_bytes(4, "little")
    else:
        header[0x0C:0x10] = (3_579_545).to_bytes(4, "little")  # SN76489
    data = commands + b"\x66"
    header[0x14:0x18] = (0x100 + len(data) - 0x14).to_bytes(4, "little")
    raw = bytes(header) + data + gd3(*tags)
    raw = raw[:4] + (len(raw) - 4).to_bytes(4, "little") + raw[8:]
    return raw


SETUP = write(0xFF26, 0x80) + write(0xFF25, 0xFF) + write(0xFF24, 0x77) + write(0xFF11, 0x80) + write(0xFF12, 0xF0)


def note_every(frames: int, count: int) -> tuple[bytes, int]:
    """Una nota nueva de CH1 cada `frames` cuadros (a medio cuadro, como un driver que escribe siempre en el mismo
    momento); devuelve los comandos y las muestras que duran."""
    done = round(SAMPLES_PER_FRAME / 2)
    out = SETUP + wait(done)
    for k in range(count):
        x = 0x780 + 8 * (k % 8)
        out += write(0xFF13, x & 0xFF) + write(0xFF14, 0x80 | x >> 8)
        target = round(((k + 1) * frames + 0.5) * SAMPLES_PER_FRAME)
        out += wait(target - done)
        done = target
    return out, done


def test_apu_pulso_envolvente_y_longitud():
    apu = gbapu.Apu()
    rec = gbapu.Recorder(apu, 40)
    apu.write(0xFF25, 0xFF)
    apu.write(0xFF11, 0x40 | 0x20)  # duty 25 %, longitud 64 - 32 = 32 pasos de 256 Hz = 7.5 cuadros
    apu.write(0xFF12, 0xF1)  # volumen 15, baja un paso cada 1/64 s (casi un cuadro)
    apu.write(0xFF13, 0x00)
    apu.write(0xFF14, 0xC7)  # dispara con longitud: x = $700 -> 131072 / 256 = 512 Hz
    for f in range(40):
        apu.run_until((f + 1) * gbapu.FRAME_CYCLES - 1)
        rec.capture(f)
    t = rec.tracks["Square1"]
    assert t.freq[0] == pytest.approx(512) and t.duty[0] == 1 and t.trig[0] and not t.trig[1]
    assert t.vol[0] > t.vol[5] > 0  # la envolvente baja
    assert t.freq[10] == 0  # la longitud lo apagó


def test_apu_onda_ruido_y_barrido():
    apu = gbapu.Apu()
    rec = gbapu.Recorder(apu, 30)
    apu.write(0xFF25, 0xFF)
    for i in range(16):  # un diente de sierra que se repite dos veces: suena una octava arriba
        apu.write(0xFF30 + i, (i % 8) * 0x22)
    apu.write(0xFF1A, 0x80)
    apu.write(0xFF1C, 0x40)  # 50 %
    apu.write(0xFF1D, 0x00)
    apu.write(0xFF1E, 0x87)  # 65536 / 256 = 256 Hz, x2 por la repetición
    apu.write(0xFF21, 0xA2)
    apu.write(0xFF22, 0x35)
    apu.write(0xFF23, 0x80)
    apu.write(0xFF10, 0x13)  # barrido hacia arriba, cada 1/128 s, shift 3 (x 1.125 por paso)
    apu.write(0xFF12, 0xF0)
    apu.write(0xFF13, 0x00)
    apu.write(0xFF14, 0x84)  # x = $400 -> 128 Hz y sube hasta pasarse de $7FF
    for f in range(30):
        apu.run_until((f + 1) * gbapu.FRAME_CYCLES - 1)
        rec.capture(f)
    wave = rec.tracks["Triangle"]
    assert wave.freq[0] == pytest.approx(512) and wave.vol[0] == 8
    assert rec.noise_hits == [(0, 0x35, 10)]
    sq = rec.tracks["Square1"]
    assert sq.freq[0] > 128 and sq.freq[29] == 0  # el barrido sube la nota y la apaga al desbordarse
    song = rec.to_ir("x", "y", "prueba")
    assert [n.frame for n in song.notes["Noise"]] == [0]
    assert any("octava" in line for line in song.log)


def test_apu_paneo_y_apagado():
    apu = gbapu.Apu()
    apu.write(0xFF25, 0x00)  # ningún canal sale por las bocinas
    apu.write(0xFF12, 0xF0)
    apu.write(0xFF14, 0x87)
    rec = gbapu.Recorder(apu, 2)
    rec.capture(0)
    assert rec.tracks["Square1"].freq[0] == 0
    apu.write(0xFF25, 0x10)
    apu.write(0xFF26, 0x00)  # apagar el APU borra los registros
    rec.capture(1)
    assert rec.tracks["Square1"].freq[1] == 0 and apu.read(0xFF12) == 0x00 and apu.read(0xFF26) == 0x70


def test_vgm_notas_y_etiquetas(tmp_path):
    commands, total = note_every(16, 8)
    path = tmp_path / "prueba.vgm"
    path.write_bytes(vgm_bytes(commands, total))
    song, info = vgm.run(path)
    assert (info.title, info.game) == ("Pista", "Juego")
    assert song.length_frames == 128
    assert [n.frame for n in song.notes["Square1"]] == [0, 16, 32, 48, 64, 80, 96, 112]
    assert song.notes["Square1"][0].pitch == round(ir.hz_midi(1024))
    assert all(not song.notes[c] for c in ("Square2", "Triangle", "Noise"))


def test_vgz_y_repeticion(tmp_path):
    commands, total = note_every(16, 4)
    loop_at = len(SETUP) + 3  # después de la espera de medio cuadro
    path = tmp_path / "prueba.vgz"
    path.write_bytes(gzip.compress(vgm_bytes(commands, total, loop_at, total)))
    song, _ = vgm.run(path)
    assert [n.frame for n in song.notes["Square1"]] == [0, 16, 32, 48]
    song, _ = vgm.run(path, seconds=3)  # 179 cuadros: casi tres vueltas
    assert [n.frame for n in song.notes["Square1"]][:7] == [0, 16, 32, 48, 64, 80, 96]


def test_vgm_de_otro_chip_se_rechaza(tmp_path):
    path = tmp_path / "sega.vgm"
    path.write_bytes(vgm_bytes(wait(44100), 44100, gb=False))
    with pytest.raises(SystemExit, match="SN76489"):
        vgm.run(path)


def test_vgm_salta_comandos_de_otros_chips(tmp_path):
    commands, total = note_every(16, 2)
    other = bytes([0x50, 0x9F]) + bytes([0x52, 0x2B, 0x80]) + bytes([0x67, 0x66, 0x00, 3, 0, 0, 0, 1, 2, 3])
    path = tmp_path / "mezcla.vgm"
    path.write_bytes(vgm_bytes(other + commands, total))
    song, _ = vgm.run(path)
    assert [n.frame for n in song.notes["Square1"]] == [0, 16]


def test_importar_un_vgm_de_principio_a_fin(tmp_path):
    from gbband_tools import audio_gb as gb
    from gbband_tools import songs

    commands, total = note_every(16, 40)
    path = tmp_path / "prueba.vgm"
    path.write_bytes(vgm_bytes(commands, total, tags=("Cancion GB", "", "Juego GB")))
    log = songs.import_song(songs.Options(source=str(path), name="vgm_sintetica"), root=tmp_path)
    folder = tmp_path / "src" / "songs" / "vgm_sintetica"
    for name in ("song.asm", "info.json", "stream_b.bin", "chart_guitarra_experto.bin"):
        assert (folder / name).exists(), name
    on = gb.note_on_frames(gb.decode_stream((folder / "stream_b.bin").read_bytes()))[0]
    assert on[:3] == [0, 16, 32]
    assert any("CANCION GB" in line for line in log)
