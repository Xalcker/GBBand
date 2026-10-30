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


def _titulo_y_start(mode: str, basura: bool):
    """Pantalla del título a los 90 cuadros y estado tras presionar Start. Con `basura`, la HRAM se llena de valores
    al azar al llegar a Start (como en una consola real o en SameBoy; PyBoy la deja en ceros)."""
    import random

    with Runner(ROM, mode, ROM.with_suffix(".sym")) as r:
        if basura:
            rng = random.Random(7)

            def ensucia(_):
                for addr in range(0xFF80, 0xFFFF):
                    r.pb.memory[addr] = rng.randrange(256)

            r.pb.hook_register(0, r.symbols["Start"], ensucia, None)
        r.boot()
        r.tick(90)
        pantalla = r.pb.screen.ndarray.copy()
        scx = r.read("hScx")[0]
        r.pb.button("start")
        r.tick(30)
        return pantalla, scx, r.read("wState")[0]


# SameBoy llena la HRAM con basura al encender: sin limpiarla, el título salía corrido y no respondía
@pytest.mark.parametrize("mode", ["dmg", "cgb"])
def test_arranca_con_hram_sucia(mode):
    limpia, _, estado_limpia = _titulo_y_start(mode, basura=False)
    sucia, scx, estado_sucia = _titulo_y_start(mode, basura=True)
    assert scx == 0
    assert (limpia == sucia).all()
    assert estado_limpia == estado_sucia == 1  # STATE_MENU
