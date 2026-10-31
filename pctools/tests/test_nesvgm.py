"""Pruebas del importador de VGM del NES (`nesvgm.py`), con VGM sintéticos."""

import struct

from gbband_tools import ir, nesvgm


def nes_vgm(body: bytes, total: int) -> bytes:
    header = bytearray(0x100)
    header[0:4] = b"Vgm "
    struct.pack_into("<I", header, 0x08, 0x161)
    struct.pack_into("<I", header, 0x18, total)
    struct.pack_into("<I", header, 0x34, 0x100 - 0x34)
    struct.pack_into("<I", header, 0x84, 1789772)  # reloj del APU del NES
    return bytes(header) + body + b"\x66"


def write(reg: int, value: int) -> bytes:
    return bytes([0xB4, reg - 0x4000, value])


def wait(samples: int) -> bytes:
    return bytes([0x61]) + struct.pack("<H", samples)


def test_dos_notas_del_pulso(tmp_path):
    # La 440 (periodo 253) y luego Do 523 (periodo 213), medio segundo cada una; volumen constante 15, duty 50 %
    body = write(0x4015, 0x0F) + write(0x4000, 0xBF) + write(0x4001, 0x08)
    body += write(0x4002, 253) + write(0x4003, 0x08) + wait(22050)
    body += write(0x4002, 213) + write(0x4003, 0x08) + wait(22050)
    path = tmp_path / "nes.vgm"
    path.write_bytes(nes_vgm(body, 44100))
    song, vgm = nesvgm.run(path)
    notes = song.notes["Square1"]
    assert [n.pitch for n in notes] == [round(ir.hz_midi(1789773 / (16 * 254))), round(ir.hz_midi(1789773 / (16 * 214)))]
    assert notes[0].frame == 0 and abs(notes[1].frame - 30) <= 1
    assert song.length_frames == 60 and vgm.clocks["nes_apu"] == 1789772


def test_otro_chip_se_rechaza(tmp_path):
    raw = bytearray(nes_vgm(b"", 735))
    struct.pack_into("<I", raw, 0x84, 0)
    struct.pack_into("<I", raw, 0x80, 4194304)  # Game Boy
    path = tmp_path / "gb.vgm"
    path.write_bytes(bytes(raw))
    try:
        nesvgm.run(path)
    except SystemExit as exc:
        assert "NES" in str(exc)
    else:
        raise AssertionError("debió rechazarse")
