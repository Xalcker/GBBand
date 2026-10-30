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
STATE_TITLE, STATE_MENU, STATE_PLAY, STATE_LINK = 0, 1, 2, 7
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


def pair(rom_a: Path, rom_b: Path, mode_a: str = "cgb", mode_b: str = "dmg", drop_rate: float = 0.0):
    a = Runner(rom_a, mode_a, rom_a.with_suffix(".sym"))
    b = Runner(rom_b, mode_b, rom_b.with_suffix(".sym"))
    a.boot()
    b.boot()
    return a, b, LinkBridge(a, b, drop_rate)


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


def test_dos_consolas_iguales_casi_al_mismo_tiempo(rom):
    """Dos CGB idénticas que entran con un cuadro de diferencia: el azar de la búsqueda (rDIV y hFrame) las desempata.
    (Dos emuladores idénticos que entran en el mismo cuadro nunca se desempatan, porque hacen exactamente lo mismo;
    dos consolas de verdad nunca están en el mismo estado.)"""
    a, b, bridge = pair(rom, rom, "cgb", "cgb")
    with a, b:
        bridge.tick(10)
        tap(bridge, "right", a, b)
        a.pb.button_press("start")
        bridge.tick(1)
        b.pb.button_press("start")
        bridge.tick(2)
        a.pb.button_release("start")
        b.pb.button_release("start")
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


# ---- Menú y arranque sincronizado --------------------------------------------------------------------------------

def value(r: Runner, name: str) -> int:
    return r.read(name)[0]


def connect_to_menu(rom: Path, players: int, mode_a: str = "cgb", mode_b: str = "dmg", drop_rate: float = 0.0):
    """Conecta dos consolas y espera a que las dos estén en el menú. Devuelve (a, b, puente, jugador 1, jugador 2)."""
    a, b, bridge = pair(rom, rom, mode_a, mode_b, drop_rate)
    bridge.tick(10)
    enter_link(bridge, a, players)
    bridge.tick(25)
    enter_link(bridge, b, players)
    for _ in range(60):
        bridge.tick(5)
        if value(a, "wState") == value(b, "wState") == STATE_MENU:
            break
    else:
        raise TimeoutError("no llegaron al menú")
    bridge.tick(10)   # (al entrar al menú el LCD está apagado y no se leen los botones)
    m, s = (a, b) if value(a, "hLinkMaster") else (b, a)
    return a, b, bridge, m, s


def wait_until(bridge: LinkBridge, cond, frames: int) -> bool:
    for _ in range(frames):
        bridge.tick(1)
        if cond():
            return True
    return False


def start_together(bridge: LinkBridge, m: Runner, s: Runner) -> tuple[int, int]:
    """Los dos dicen "listo"; devuelve wT de cada uno 100 cuadros después de que los dos echaron a andar la canción."""
    tap(bridge, "start", s)
    tap(bridge, "start", m)
    both = lambda: all(value(r, "wState") == STATE_PLAY and value(r, "wPlaying") for r in (m, s))
    assert wait_until(bridge, both, 120), "la canción no empezó en las dos consolas"
    bridge.tick(100)
    return tuple(int.from_bytes(r.read("wT", 2), "little") for r in (m, s))


@pytest.mark.parametrize("mode_a, mode_b", [("cgb", "dmg"), ("dmg", "cgb"), ("cgb", "cgb")])
def test_vs_el_2_sigue_al_1_y_empiezan_juntos(rom, mode_a, mode_b):
    a, b, bridge, m, s = connect_to_menu(rom, 1, mode_a, mode_b)
    with a, b:
        # el 1 elige la canción y la dificultad; el 2 las sigue y no las puede cambiar
        tap(bridge, "right", m)
        tap(bridge, "right", m)
        song = value(m, "wSong")
        assert song == 2
        for r in (m, s):
            tap(bridge, "down", r)
            tap(bridge, "down", r)
        tap(bridge, "left", m)
        diff = value(m, "wDifficulty")
        tap(bridge, "left", s)          # (en VS el 2 no cambia la dificultad)
        tap(bridge, "up", s)
        tap(bridge, "up", s)
        tap(bridge, "right", s)         # ni la canción
        assert wait_until(bridge, lambda: value(s, "wSong") == song and value(s, "wDifficulty") == diff, 60)
        # el 1 cambia de instrumento: en VS el 2 lo copia
        tap(bridge, "up", m)
        tap(bridge, "right", m)
        instr = value(m, "wInstrument")
        assert wait_until(bridge, lambda: value(s, "wInstrument") == instr, 60)
        tm, ts = start_together(bridge, m, s)
        assert abs(tm - ts) <= 1, f"empezaron {tm - ts} cuadros aparte"
        assert value(m, "wSong") == value(s, "wSong") == song
        # sin pausa con 2 jugadores
        tap(bridge, "start", m)
        bridge.tick(5)
        assert value(m, "wState") == STATE_PLAY
        assert value(m, "hLinkOn") == value(s, "hLinkOn") == 1 and value(m, "wLinkSilence") < 10
        for r in (a, b):
            r.tick(1)
        m.screenshot(ROOT / "build" / "test-link" / f"vs-juego-{mode_a}-{mode_b}-j1.png")
        s.screenshot(ROOT / "build" / "test-link" / f"vs-juego-{mode_a}-{mode_b}-j2.png")


@pytest.mark.parametrize("drop_rate", (0.1, 0.2))
def test_un_cable_que_pierde_bytes_no_atora_nada(rom, drop_rate):
    """Con una parte de las transferencias perdida al azar, el saludo, el menú (se repite) y la salida (se repite) siguen
    funcionando."""
    a, b, bridge, m, s = connect_to_menu(rom, 1, drop_rate=drop_rate)
    with a, b:
        hello = a.read("HelloMsg", 4)[1:]
        assert a.read("wLinkPeer", 3) == hello and b.read("wLinkPeer", 3) == hello
        for _ in range(3):
            tap(bridge, "right", m)
        song = value(m, "wSong")
        assert wait_until(bridge, lambda: value(s, "wSong") == song, 120)
        tm, ts = start_together(bridge, m, s)
        assert abs(tm - ts) <= 1
        assert bridge.lost > 10


def test_coop_no_se_puede_el_mismo_instrumento(rom):
    a, b, bridge, m, s = connect_to_menu(rom, 2)
    with a, b:
        assert value(m, "wInstrument") == value(s, "wInstrument") == 0
        bridge.tick(40)
        tap(bridge, "start", s)         # el mismo instrumento que el 1: no queda listo
        bridge.tick(5)
        assert value(s, "wReady") == 0
        tap(bridge, "down", s)
        tap(bridge, "right", s)
        assert value(s, "wInstrument") != value(m, "wInstrument")
        bridge.tick(40)
        for r in (a, b):
            r.tick(1)
        m.screenshot(ROOT / "build" / "test-link" / "coop-menu-j1.png")
        s.screenshot(ROOT / "build" / "test-link" / "coop-menu-j2.png")
        tm, ts = start_together(bridge, m, s)
        assert abs(tm - ts) <= 1


def test_si_uno_se_va_el_otro_vuelve_al_titulo(rom):
    a, b, bridge, m, s = connect_to_menu(rom, 1)
    with a, b:
        tap(bridge, "b", s)
        assert value(s, "wState") == STATE_TITLE and value(s, "hLinkOn") == 0
        assert wait_until(bridge, lambda: value(m, "wState") == STATE_TITLE, 200), "el 1 no notó que el 2 se fue"
        assert value(m, "hLinkOn") == 0 and value(m, "wPlayers") == 0
        assert value(m, 0xFFFF) & IE_SERIAL == 0
