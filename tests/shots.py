"""Capturas de todas las pantallas del juego (título, menú, partida, pausa y resultados) en DMG y CGB.

    uv run python tests/shots.py [canción] [carpeta]

Las deja en build/pantallas/<modo>-<pantalla>.png para revisarlas a simple vista.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pctools"))

from gbband_tools import playtest  # noqa: E402
from gbband_tools.runner import Runner  # noqa: E402


def main() -> None:
    song = sys.argv[1] if len(sys.argv) > 1 else "tormenta"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "pantallas"
    rom = ROOT / "build" / "gbband.gb"
    for mode in ("dmg", "cgb"):
        r = Runner(rom, mode, rom.with_suffix(".sym"))
        r.boot()
        r.tick(10)
        r.screenshot(out / f"{mode}-1-titulo.png")
        playtest.select_in_menu(r, playtest.song_names().index(song), 0, 3)
        r.tick(3)
        r.screenshot(out / f"{mode}-2-menu.png")
        r.pb.button_press("start")
        r.tick(2)
        r.pb.button_release("start")
        r.tick(900)
        r.screenshot(out / f"{mode}-3-partida.png")
        r.pb.button_press("start")
        r.tick(2)
        r.pb.button_release("start")
        r.tick(6)
        r.screenshot(out / f"{mode}-4-pausa.png")
        r.pb.button_press("start")
        r.tick(2)
        r.pb.button_release("start")
        for _ in range(8000):
            if r.read("wState")[0] == playtest.STATE_END:
                break
            r.tick(1)
        r.tick(8)
        r.screenshot(out / f"{mode}-5-resultados.png")
        r.close()
    print(f"capturas en {out}")


if __name__ == "__main__":
    main()
