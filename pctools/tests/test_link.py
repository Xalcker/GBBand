"""Pruebas del cable link: dos PyBoy conectados con LinkBridge (ver linkbridge.py) buscan al otro y se saludan.

Lo que aquí se comprueba solo se probó en emulador: falta probarlo con dos consolas y un cable de verdad.
"""

import shutil
from pathlib import Path

import pytest

from gbband_tools import playtest
from gbband_tools.linkbridge import LinkBridge
from gbband_tools.runner import Runner

ROOT = Path(__file__).resolve().parents[2]
STATE_TITLE, STATE_LINK = 0, 7
LINK_SEARCH, LINK_OK, LINK_WRONG = 0, 1, 2
IE_SERIAL = 0x08


@pytest.fixture(scope="module")
def rom():
    return playtest.build_rom("B")


@pytest.fixture(scope="module")
def rom_other_songs(rom):
    """El mismo ROM con otro hash de la lista de canciones en el saludo (como un cartucho con otras canciones)."""
    sym = rom.with_suffix(".sym")
    symbols = {}
    for line in sym.read_text(encoding="utf-8").splitlines():
        place, _, name = line.partition(" ")
        if name and ":" in place:
            symbols[name.strip()] = int(place.split(":")[1], 16)
    data = bytearray(rom.read_bytes())
    data[symbols["HelloMsg"] + 2] ^= 0x01      # hash bajo de la lista de canciones
    other = rom.with_name("gbband-otras.gb")
    other.write_bytes(data)
    shutil.copy(sym, other.with_suffix(".sym"))
    return other


def pair(rom_a: Path, rom_b: Path, mode_a: str = "cgb", mode_b: str = "dmg"):
    a = Runner(rom_a, mode_a, rom_a.with_suffix(".sym"))
    b = Runner(rom_b, mode_b, rom_b.with_suffix(".sym"))
    a.boot()
    b.boot()
    return a, b, LinkBridge(a, b)


def tap(bridge: LinkBridge, button: str, *runners: Runner) -> None:
    for r in runners:
        r.pb.button_press(button)
    bridge.tick(2)
    for r in runners:
        r.pb.button_release(button)
    bridge.tick(2)


def enter_link(bridge: LinkBridge, r: Runner, players: int) -> None:
    """En el título, JUGADORES con ←/→ y Start."""
    for _ in range(players):
        tap(bridge, "right", r)
    assert r.read("wPlayers")[0] == players
    tap(bridge, "start", r)


def wait_states(bridge: LinkBridge, runners, frames: int) -> list[int]:
    for _ in range(frames // 10):
        bridge.tick(10)
        states = [r.read("wLinkState")[0] for r in runners]
        if all(s != LINK_SEARCH for s in states):
            return states
    return [r.read("wLinkState")[0] for r in runners]


@pytest.mark.parametrize("players, gap", [(1, 0), (1, 45), (2, 200)])
def test_se_conectan_y_se_reparten_los_papeles(rom, players, gap):
    """Una consola entra a la búsqueda y la otra después: se conectan, una es el jugador 1 (maestro) y la otra el 2."""
    a, b, bridge = pair(rom, rom)
    with a, b:
        bridge.tick(10)
        enter_link(bridge, a, players)
        bridge.tick(gap)
        enter_link(bridge, b, players)
        assert [r.read("wState")[0] for r in (a, b)] == [STATE_LINK, STATE_LINK]
        assert wait_states(bridge, (a, b), 300) == [LINK_OK, LINK_OK]
        masters = sorted(r.read("hLinkMaster")[0] for r in (a, b))
        assert masters == [0, 1], "debe haber exactamente un maestro"
        hello = a.read("HelloMsg", 4)
        for r in (a, b):
            assert r.read("wLinkPeer", 3) == hello[1:]
        # el cable sigue trabajando: un byte por cuadro
        before = bridge.exchanges()
        bridge.tick(30)
        assert bridge.exchanges() - before >= 28
        for r in (a, b):
            r.tick(1)
        a.screenshot(ROOT / "build" / "test-link" / f"conectado-{players}-{gap}-a.png")
        b.screenshot(ROOT / "build" / "test-link" / f"conectado-{players}-{gap}-b.png")


def test_dos_consolas_iguales_al_mismo_tiempo(rom):
    """Dos CGB que entran en el mismo cuadro (el azar sale igual): el cambio de papeles termina por desempatar."""
    a, b, bridge = pair(rom, rom, "cgb", "cgb")
    with a, b:
        bridge.tick(10)
        tap(bridge, "right", a, b)
        tap(bridge, "start", a, b)
        assert wait_states(bridge, (a, b), 1200) == [LINK_OK, LINK_OK]
        assert sorted(r.read("hLinkMaster")[0] for r in (a, b)) == [0, 1]


def test_canciones_distintas_no_se_conectan(rom, rom_other_songs):
    a, b, bridge = pair(rom, rom_other_songs)
    with a, b:
        bridge.tick(10)
        enter_link(bridge, a, 1)
        bridge.tick(20)
        enter_link(bridge, b, 1)
        assert wait_states(bridge, (a, b), 300) == [LINK_WRONG, LINK_WRONG]


@pytest.mark.parametrize("mode", ("dmg", "cgb"))
def test_titulo_muestra_y_cambia_jugadores(rom, mode):
    """El renglón JUGADORES del título (fila 8, columna 3) se ve y cambia con ←/→."""
    row = lambda r: bytes(r.read(0x9800 + 32 * 8 + 3, 14)).decode("ascii")
    with Runner(rom, mode, rom.with_suffix(".sym")) as r:
        r.boot()
        r.tick(10)
        assert row(r) == "< 1 JUGADOR  >"
        for button, text in (("right", "< 2 JUG. VS  >"), ("right", "<2 JUG. COOP >"), ("right", "< 1 JUGADOR  >"),
                             ("left", "<2 JUG. COOP >")):
            r.pb.button_press(button)
            r.tick(2)
            r.pb.button_release(button)
            r.tick(4)
            assert row(r) == text


def test_sin_nadie_del_otro_lado_sigue_buscando_y_b_cancela(rom):
    with Runner(rom, "dmg", rom.with_suffix(".sym")) as r:
        r.boot()
        r.tick(10)
        for button in ("left", "start"):    # ← da la vuelta hasta Co-Op
            r.pb.button_press(button)
            r.tick(2)
            r.pb.button_release(button)
            r.tick(2)
        assert r.read("wPlayers")[0] == 2 and r.read("wState")[0] == STATE_LINK
        roles = set()
        for _ in range(60):
            r.tick(10)
            roles.add(r.read("hLinkMaster")[0])
        assert r.read("wLinkState")[0] == LINK_SEARCH
        assert roles == {0, 1}, "sin respuesta debe turnarse entre esperar y llamar"
        r.pb.button_press("b")
        r.tick(2)
        r.pb.button_release("b")
        r.tick(4)
        assert r.read("wState")[0] == STATE_TITLE
        assert r.read(0xFFFF)[0] & IE_SERIAL == 0 and r.read("hLinkOn")[0] == 0
