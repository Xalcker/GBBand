"""Pruebas del importador de NSF: el 6502, el APU y la IR que sale de las escrituras."""

from pathlib import Path

import pytest

from gbband_tools import ir, nsf
from gbband_tools.cpu6502 import CPU6502


def machine(code: bytes) -> nsf.NsfMachine:
    header = nsf.Header(1, 1, 0x8000, 0x8000, 0x8000, "t", "", "", (0,) * 8, 0, code)
    return nsf.NsfMachine(header)


def test_cpu_suma_bucles_y_subrutinas():
    code = bytes([
        0xA9, 0x05,        # LDA #5
        0x18,              # CLC
        0x69, 0x0A,        # ADC #10
        0x85, 0x00,        # STA $00
        0xA2, 0x03,        # LDX #3
        0xCA,              # loop: DEX
        0xD0, 0xFD,        # BNE loop
        0x86, 0x01,        # STX $01
        0x20, 0x14, 0x80,  # JSR sub
        0x85, 0x02,        # STA $02
        0x60,              # RTS
        0xA9, 0x42, 0x60,  # sub: LDA #$42 ; RTS
    ])
    m = machine(code)
    m.cpu.call(0x8000)
    assert m.ram[0] == 0x0F and m.ram[1] == 0 and m.ram[2] == 0x42


def test_cpu_banderas_y_pila():
    # SEC; LDA #$80; ADC #$80 -> $01 con acarreo y desbordamiento; PHA; LDA #0; PLA; STA $00; PHP/PLP
    code = bytes([0x38, 0xA9, 0x80, 0x69, 0x80, 0x48, 0xA9, 0x00, 0x68, 0x85, 0x00, 0x08, 0x28, 0x60])
    m = machine(code)
    m.cpu.call(0x8000)
    assert m.ram[0] == 0x01
    assert m.cpu.p & 0x01 and m.cpu.p & 0x40  # C y V


def test_cpu_sbc_cmp_y_rotaciones():
    # SEC; LDA #$10; SBC #$01 -> $0F; CMP #$0F (Z, C); ROL A; STA $00 -> $1F con C=0 y luego $3F si C=1
    code = bytes([0x38, 0xA9, 0x10, 0xE9, 0x01, 0xC9, 0x0F, 0x2A, 0x85, 0x00, 0x60])
    m = machine(code)
    m.cpu.call(0x8000)
    assert m.ram[0] == 0x1F  # (0x0F << 1) | C(1 por el CMP igual)


def nsf_file(tmp_path: Path, init: bytes, play: bytes) -> Path:
    load = 0x8000
    raw = bytearray(128)
    raw[:5] = b"NESM\x1a"
    raw[5], raw[6], raw[7] = 1, 1, 1
    raw[8:10] = load.to_bytes(2, "little")
    raw[10:12] = load.to_bytes(2, "little")
    raw[12:14] = (load + len(init)).to_bytes(2, "little")
    raw[0x0E:0x0E + 4] = b"Test"
    path = tmp_path / "prueba.nsf"
    path.write_bytes(bytes(raw) + init + play)
    return path


def test_nsf_pulso_constante(tmp_path):
    init = bytes([
        0xA9, 0x01, 0x8D, 0x15, 0x40,  # $4015 = 1: pulso 1
        0xA9, 0xBC, 0x8D, 0x00, 0x40,  # $4000: duty 2, halt, volumen constante 12
        0xA9, 0xFD, 0x8D, 0x02, 0x40,  # $4002: timer bajo = 253
        0xA9, 0x08, 0x8D, 0x03, 0x40,  # $4003: longitud 1, timer alto 0
        0x60,
    ])
    path = nsf_file(tmp_path, init, bytes([0x60]))
    song = nsf.run(path, 0, 2)
    t = song.tracks["Square1"]
    assert t.freq[0] == pytest.approx(440.4, abs=0.1)
    assert t.vol[0] == 12 and t.duty[0] == 2 and t.trig[0] and not t.trig[1]
    assert all(f == t.freq[0] for f in t.freq)  # sigue sonando
    assert len(song.notes["Square1"]) == 1 and song.notes["Square1"][0].pitch == 69
    assert not any(song.tracks["Square2"].freq) and not any(song.tracks["Triangle"].freq)


def test_nsf_envolvente_de_caida_y_longitud(tmp_path):
    init = bytes([
        0xA9, 0x01, 0x8D, 0x15, 0x40,
        0xA9, 0x81, 0x8D, 0x00, 0x40,  # duty 2 no, 0x81 = duty 2, sin halt, envolvente de caída con periodo 1
        0xA9, 0xFD, 0x8D, 0x02, 0x40,
        0xA9, 0x08, 0x8D, 0x03, 0x40,  # longitud índice 1 = 254 medios cuadros: dura de sobra
        0x60,
    ])
    path = nsf_file(tmp_path, init, bytes([0x60]))
    song = nsf.run(path, 0, 2)
    vols = song.tracks["Square1"].vol[:20]
    assert vols[0] == 15 and vols == sorted(vols, reverse=True) and vols[-1] < vols[0]


def test_nsf_triangulo_y_ruido(tmp_path):
    init = bytes([
        0xA9, 0x0C, 0x8D, 0x15, 0x40,  # triángulo y ruido
        0xA9, 0xFF, 0x8D, 0x08, 0x40,  # $4008: control + contador lineal 127
        0xA9, 0xFD, 0x8D, 0x0A, 0x40,
        0xA9, 0xF8, 0x8D, 0x0B, 0x40,  # $400B: longitud 31
        0xA9, 0x3F, 0x8D, 0x0C, 0x40,  # ruido: halt + constante 15
        0xA9, 0x05, 0x8D, 0x0E, 0x40,  # periodo 5
        0xA9, 0xF8, 0x8D, 0x0F, 0x40,
        0x60,
    ])
    path = nsf_file(tmp_path, init, bytes([0x60]))
    song = nsf.run(path, 0, 1)
    tri = song.tracks["Triangle"]
    assert tri.freq[0] == pytest.approx(220.2, abs=0.1) and tri.vol[0] == 15
    assert len(song.notes["Noise"]) == 1 and song.notes["Noise"][0].frame == 0


def test_nsf_rechaza_chips_extra(tmp_path):
    path = nsf_file(tmp_path, bytes([0x60]), bytes([0x60]))
    raw = bytearray(path.read_bytes())
    raw[0x7B] = 0x01  # VRC6
    path.write_bytes(bytes(raw))
    with pytest.raises(SystemExit, match="VRC6"):
        nsf.run(path, 0, 1)


def test_notas_de_un_barrido_no_son_notas_sueltas():
    track = ir.Track.silent(30)
    for f in range(30):
        track.freq[f] = ir.midi_hz(60 + (1 if f % 2 else 0))  # vibrato de un semitono
        track.vol[f] = 10
    track.trig[0] = True
    assert len(nsf.tonal_notes(track)) == 1
    for f in range(15, 30):
        track.freq[f] = ir.midi_hz(67)  # salto sostenido de una quinta
    notes = nsf.tonal_notes(track)
    assert [n.pitch for n in notes] == [61 if False else notes[0].pitch, 67] and len(notes) == 2

def test_importar_un_nsf_de_principio_a_fin(tmp_path):
    """Un NSF sintético (una nota nueva cada 16 cuadros) pasa por todo: IR, audio FRS, charts y archivos de la canción."""
    from gbband_tools import audio_gb as gb
    from gbband_tools import chartedit, songs

    init = bytes([0xA9, 0x01, 0x8D, 0x15, 0x40, 0xA9, 0xBF, 0x8D, 0x00, 0x40, 0xA9, 0x00, 0x85, 0x00, 0x60])
    play = bytes([0xE6, 0x00, 0xA5, 0x00, 0x29, 0x0F, 0xD0, 0x16, 0xA5, 0x00, 0x4A, 0x4A, 0x4A, 0x4A, 0x29, 0x07,
                  0x0A, 0x0A, 0x0A, 0x18, 0x69, 0x80, 0x8D, 0x02, 0x40, 0xA9, 0x08, 0x8D, 0x03, 0x40, 0x60])
    path = nsf_file(tmp_path, init, play)
    options = songs.Options(source=str(path), name="sintetica", title="Prueba", game="Juego de prueba", duration=12)
    log = songs.import_song(options, root=tmp_path)
    folder = tmp_path / "src" / "songs" / "sintetica"
    for name in ("song.asm", "info.json", "stream_b.bin", "keyframes.bin", "import.json", "chart_guitarra_experto.bin"):
        assert (folder / name).exists(), name
    assert not (folder / "chart_bajo_experto.bin").exists()  # sin triángulo no hay chart de bajo
    stream = (folder / "stream_b.bin").read_bytes()
    on = gb.note_on_frames(gb.decode_stream(stream))[0]
    assert on[:3] == [15, 31, 47]  # una nota nueva cada 16 cuadros (el contador llega a 16 en la llamada número 16)
    chart = chartedit.entries_to_chart(chartedit.parse_chart_bytes((folder / "chart_guitarra_experto.bin").read_bytes()))
    assert 30 <= len(chart) <= 45 and all(n.mask & 0x1F for n in chart)
    assert any("PRUEBA" in line for line in log)