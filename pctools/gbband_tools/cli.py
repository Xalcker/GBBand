"""Línea de comandos: `uv run gbband <comando>`."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def cmd_build_gfx(args: argparse.Namespace) -> None:
    from . import gfx

    made = gfx.build_dir(ROOT / "src" / "chr", ROOT / "build" / "chr")
    for path in made:
        print(f"{path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


def cmd_build_font(args: argparse.Namespace) -> None:
    from . import fontgen

    ttf = ROOT / "assets" / "fonts" / "Bongo-8_Mono.ttf"
    text = fontgen.build_font_tiles(fontgen.glyphs_from_ttf(ttf), ttf.name)
    out = ROOT / "src" / "chr" / "font.tiles"
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{out.relative_to(ROOT)} generado")


def cmd_build_gems(args: argparse.Namespace) -> None:
    from . import gemgen

    out = ROOT / "src" / "chr" / "gems.tiles"
    out.write_text(gemgen.build_gems_tiles(), encoding="utf-8", newline="\n")
    print(f"{out.relative_to(ROOT)} generado")


def cmd_smoke(args: argparse.Namespace) -> None:
    from . import runner

    rom = Path(args.rom)
    runner.smoke(rom, Path(args.out) if args.out else ROOT / "build" / f"smoke-{rom.stem}", args.frames)


def cmd_measure(args: argparse.Namespace) -> None:
    from . import measure

    print(measure.measure(ROOT / "reference" / "NESBand"))


def main() -> None:
    parser = argparse.ArgumentParser(prog="gbband", description="Herramientas de PC de GBBand")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-gfx", help="convierte src/chr/*.tiles a build/chr/*.2bpp y PNG de contacto").set_defaults(func=cmd_build_gfx)
    sub.add_parser("build-font", help="regenera src/chr/font.tiles desde Bongo-8 (necesita Pillow)").set_defaults(func=cmd_build_font)
    sub.add_parser("build-gems", help="regenera src/chr/gems.tiles (gemas con sus variantes)").set_defaults(func=cmd_build_gems)
    sub.add_parser("measure-placement", help="mide las colocaciones A y B con los charts de NESBand").set_defaults(func=cmd_measure)
    smoke = sub.add_parser("smoke", help="corre un ROM en DMG y CGB y toma capturas")
    smoke.add_argument("rom")
    smoke.add_argument("--frames", type=int, default=120)
    smoke.add_argument("--out")
    smoke.set_defaults(func=cmd_smoke)
    args = parser.parse_args()
    args.func(args)
