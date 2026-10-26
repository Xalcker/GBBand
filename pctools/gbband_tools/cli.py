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


def cmd_import_song(args: argparse.Namespace) -> None:
    from . import songs

    gain = None
    if args.gain:
        names = {"ch1": "Square1", "ch2": "Square2", "ch3": "Triangle"}
        gain = {names[k.lower()]: float(v) for k, v in (item.split("=") for item in args.gain.split(","))}
    source = args.source.resolve()
    shown = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source)
    options = songs.Options(source=shown, name=args.name, title=args.title, game=args.game, track=args.track,
                            song=args.song, duration=args.duration, beat_frames=args.beat_frames, gain=gain)
    print("\n".join(songs.import_song(options)))
    songs.list_songs()


def cmd_list_songs(args: argparse.Namespace) -> None:
    from . import songs

    names = songs.list_songs(args.solo, args.release)
    if not args.quiet:
        print(f"{len(names)} canciones en build/list.asm: {', '.join(names)}")


def cmd_reimport(args: argparse.Namespace) -> None:
    from . import songs

    songs.reimport(args.names or None)
    songs.list_songs()


def main() -> None:
    parser = argparse.ArgumentParser(prog="gbband", description="Herramientas de PC de GBBand")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-gfx", help="convierte src/chr/*.tiles a build/chr/*.2bpp y PNG de contacto").set_defaults(func=cmd_build_gfx)
    sub.add_parser("build-font", help="regenera src/chr/font.tiles desde Bongo-8 (necesita Pillow)").set_defaults(func=cmd_build_font)
    p = sub.add_parser("import-song", help="importa una canción (proyecto de FamiStudio .txt o NSF) y genera sus charts y su audio")
    p.add_argument("source", type=Path)
    p.add_argument("--name", required=True, help="identificador (minúsculas, números y _)")
    p.add_argument("--title")
    p.add_argument("--game")
    p.add_argument("--track", type=int, help="pista como la numera el .m3u (desde 1)")
    p.add_argument("--song", type=int, default=0, help="índice de la canción dentro del archivo (desde 0)")
    p.add_argument("--duration", type=int, help="solo NSF: segundos a grabar")
    p.add_argument("--beat-frames", type=int, help="cuadros por tiempo, si la estimación automática falla")
    p.add_argument("--gain", help="ganancia de volumen por canal, por ejemplo ch1=1.0,ch2=0.8,ch3=1.0")
    p.set_defaults(func=cmd_import_song)
    p = sub.add_parser("list-songs", help="regenera build/list.asm (las canciones que entran a la ROM)")
    p.add_argument("--solo", nargs="*", help="solo las canciones que coincidan con estos patrones")
    p.add_argument("--release", action="store_true", help="solo las canciones versionadas en git")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_list_songs)
    p = sub.add_parser("reimport", help="vuelve a importar canciones con sus opciones originales")
    p.add_argument("names", nargs="*")
    p.set_defaults(func=cmd_reimport)
    sub.add_parser("build-gems", help="regenera src/chr/gems.tiles (gemas con sus variantes)").set_defaults(func=cmd_build_gems)
    sub.add_parser("measure-placement", help="mide las colocaciones A y B con los charts de NESBand").set_defaults(func=cmd_measure)
    smoke = sub.add_parser("smoke", help="corre un ROM en DMG y CGB y toma capturas")
    smoke.add_argument("rom")
    smoke.add_argument("--frames", type=int, default=120)
    smoke.add_argument("--out")
    smoke.set_defaults(func=cmd_smoke)
    args = parser.parse_args()
    args.func(args)
