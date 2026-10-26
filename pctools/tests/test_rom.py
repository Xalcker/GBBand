"""Pruebas del ROM compilado (fase 1). Necesitan build/gbband.gb: corre build.ps1 / build.sh antes."""

from pathlib import Path

import pytest

from gbband_tools.runner import Runner

ROOT = Path(__file__).resolve().parents[2]
ROM = ROOT / "build" / "gbband.gb"

pytestmark = pytest.mark.skipif(not ROM.exists(), reason="falta build/gbband.gb (compila primero)")


def test_header():
    rom = ROM.read_bytes()
    assert len(rom) == 2 * 1024 * 1024
    assert rom[0x143] == 0x80  # compatible con CGB
    assert rom[0x147] == 0x1B  # MBC5+RAM+BATTERY
    assert rom[0x148] == 0x06  # 2 MB
    assert rom[0x149] == 0x02  # 8 KB de SRAM
    checksum = 0
    for byte in rom[0x134:0x14D]:
        checksum = (checksum - byte - 1) & 0xFF
    assert rom[0x14D] == checksum


# A al arrancar: $01 en DMG, $11 en CGB
@pytest.mark.parametrize("mode,esperado", [("dmg", 0x01), ("cgb", 0x11)])
def test_detecta_modo_y_cuenta_cuadros(mode, esperado):
    with Runner(ROM, mode, ROM.with_suffix(".sym")) as r:
        r.boot()
        r.tick(10)
        assert r.read("hIsCGB")[0] == esperado
        f1 = int.from_bytes(r.read("hFrame", 2), "little")
        r.tick(30)
        f2 = int.from_bytes(r.read("hFrame", 2), "little")
        # un cuadro de VBlank por tick: debe avanzar exactamente 30
        assert f2 - f1 == 30
