"""Importar canciones: de una fuente (proyecto de FamiStudio o NSF) a src/songs/<nombre>/.

    uv run gbband import-song audio/tormenta.txt --name tormenta --title "Tormenta de Neon" --game GBBand
    uv run gbband import-song "songs_src/Juego.nsf" --track 2 --name juego_area1
    uv run gbband list-songs        (regenera build/list.asm, la lista de canciones que entran en la ROM)
    uv run gbband reimport          (todas, con las mismas opciones, tras mejorar el generador)

import-song genera en src/songs/<nombre>/:
    song.asm                          la ficha de la canción y sus tres bancos (ver src/song_format.inc)
    chart_<instrumento>_<dificultad>.bin   un chart por instrumento y dificultad
    stream_b.bin, stream_c.bin, keyframes.bin   el audio (stream FRS) y sus 4 keyframes
    info.json                         datos de la canción para las herramientas y las pruebas
    import.json                       las opciones de la importación (para `reimport`)
y se conservan, si existen, drums.json (papeles de la batería) y edits.json (ediciones a mano de los charts).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import audio_gb as gb
from . import chart as charts
from . import drums as drums_mod
from . import famitext, gbaudio, ir
from .chartedit import EDITS_FILE, apply_edits, load_edits, validate_chart

ROOT = Path(__file__).resolve().parents[2]
SONGS_DIR = ROOT / "src" / "songs"
BUILD_DIR = ROOT / "build"

TITLE_SONG = "titulo"   # la música de la pantalla de título: slot propio (banco TITLE_BANK), fuera de la lista del menú
TITLE_BANK = 112
LEAD_IN = 180 # cuadros de autopista antes de que empiece el audio (más que la anticipación de fácil, 156)
SLOT_BANK_SIZE = 16384
STREAM_CAPACITY = 2 * SLOT_BANK_SIZE
FICHA_SIZE = 112
TITLE_LEN, GAME_LEN = 20, 16
FONT_CHARS = set(" !\"#%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ")
INSTRUMENTS = [("guitarra", "Square1"), ("teclado", "Square2"), ("bajo", "Triangle"), ("bateria", None)]
ROLE_OF = {"guitarra": ("lead", "Square2"), "teclado": ("keys", "Square1"), "bajo": ("bass", None)}


def gb_text(text: str, limit: int) -> str:
    """Mayúsculas, sin acentos y solo con caracteres de la fuente del juego."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").upper()
    plain = "".join(c if c in FONT_CHARS else " " for c in plain)
    return " ".join(plain.split())[:limit]


def cache_ir(root: Path, name: str, song: ir.SongIR) -> None:
    """La IR queda en build/songs/<nombre>/ir.pkl para el editor de charts (importar un NSF tarda unos segundos)."""
    import pickle

    folder = root / "build" / "songs" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ir.pkl").write_bytes(pickle.dumps(song))


def write_lf(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


@dataclass
class Options:
    source: str
    name: str
    title: str | None = None
    game: str | None = None
    track: int | None = None
    song: int = 0
    duration: int | None = None
    beat_frames: int | None = None
    gain: dict | None = None

    def to_json(self) -> dict:
        return {"source": self.source, "track": self.track, "song": self.song, "title": self.title, "game": self.game,
                "duration": self.duration, "beat_frames": self.beat_frames, "gain": self.gain}


def load_source(path: Path, options: Options) -> tuple[ir.SongIR, str, str]:
    """La IR de la fuente, y su título y juego por omisión."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        project = famitext.parse_text(path.read_text(encoding="utf-8"))
        song = project.songs[options.song]
        return famitext.to_ir(project, options.song, options.game or ""), song.name, project.attrs.get("Name", "")
    if suffix in (".nsf", ".nsfe"):
        from . import nsf

        return nsf.load(path, options)
    raise SystemExit(f"{path.name}: solo se importan proyectos de texto de FamiStudio (.txt) y NSF (.nsf)")


def truncated(song: ir.SongIR, frames: int) -> ir.SongIR:
    """La misma canción cortada en `frames` cuadros (las notas que empiezan después se quitan)."""
    cut = ir.SongIR(song.name, song.game, min(frames, song.length_frames), song.tracks,
                    {c: [n for n in notes if n.frame < frames] for c, notes in song.notes.items()},
                    song.frames_per_beat, song.source, list(song.log))
    return cut


def auto_charts(song: ir.SongIR, grid: charts.BeatGrid, assignment: dict | None, lead_in: int = LEAD_IN,
                stats: dict | None = None) -> dict[str, list[charts.ChartNote]]:
    """Los charts que genera el importador (sin las ediciones a mano), por clave "instrumento/dificultad". La batería sale
    de la asignación de papeles (drums.json) y solo existe si algún golpe tiene papel."""
    result: dict[str, list[charts.ChartNote]] = {}
    hits = drums_mod.drum_hits(song, assignment) if assignment else []
    for instrument, channel in INSTRUMENTS:
        notes = song.notes.get(channel, []) if channel else []
        if not notes and not (instrument == "bateria" and hits):
            continue
        for difficulty in charts.DIFFICULTIES:
            if instrument == "bateria":
                chart = drums_mod.build_drum_chart(hits, difficulty.name, grid, lead_in, stats)
            else:
                role, partner = ROLE_OF[instrument]
                chart = charts.build_chart(notes, difficulty, grid, lead_in, role, song.notes.get(partner, []), stats)
            result[f"{instrument}/{difficulty.name}"] = chart
    return result


def beat_grid(song: ir.SongIR, beat_frames: int | None) -> charts.BeatGrid:
    """La rejilla de tiempos: la del proyecto de FamiStudio es confiable; la de un NSF se estima de los ataques."""
    if song.frames_per_beat and not beat_frames:
        return charts.estimate_beat([0], song.frames_per_beat)
    return charts.estimate_beat([n.frame for ch in song.notes.values() for n in charts.merge_attacks(ch)], beat_frames)


def import_song(options: Options, root: Path = ROOT) -> list[str]:
    name = options.name
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise SystemExit("--name debe ser minúsculas, números y _ (empezando con letra)")
    source = (root / options.source) if not Path(options.source).is_absolute() else Path(options.source)
    out_dir = root / "src" / "songs" / name
    song, default_title, default_game = load_source(source, options)
    title = gb_text(options.title or default_title or name, TITLE_LEN)
    game = gb_text(options.game or default_game, GAME_LEN)
    summary: list[str] = []
    grid = beat_grid(song, options.beat_frames)

    # El trabajo manual sobrevive: asignación de la batería y ediciones de los charts
    kept = {n: (out_dir / n).read_text(encoding="utf-8") for n in (EDITS_FILE, drums_mod.DRUMS_FILE) if (out_dir / n).exists()}
    edits = load_edits(out_dir)
    assignment = drums_mod.load_drums(out_dir)
    drum_notes_exist = any(song.notes.get(c) for c in ir.DRUM_CHANNELS)
    if assignment is None and drum_notes_exist:
        assignment = drums_mod.suggest_assignment(drums_mod.drum_groups(song))
        kept[drums_mod.DRUMS_FILE] = drums_mod.dump_drums(assignment)
        summary.append("  drums.json: asignación automática de la batería (revísala en el editor)")

    # Audio: si el stream no cabe en los 2 bancos del slot, se graba menos
    max_frames = None
    for _ in range(8):
        current = truncated(song, max_frames) if max_frames else song
        result = gbaudio.convert(current, assignment, options.gain, max_frames)
        n = len(result.frames) - 1
        keyframe_at = [0, n // 4, n // 2, 3 * n // 4]
        stream, offsets = gb.encode_stream(result.frames, break_at={k + 1 for k in keyframe_at})
        if len(stream) <= STREAM_CAPACITY:
            break
        new_frames = int(n * STREAM_CAPACITY * 0.96 / len(stream))
        summary.append(f"  No cabe con {n / 60:.0f} s ({len(stream)} de {STREAM_CAPACITY} bytes): pruebo con {new_frames / 60:.0f} s")
        max_frames = new_frames
    else:
        raise SystemExit("No logré que el audio de la canción cupiera en 2 bancos")
    song = truncated(song, n) if max_frames else song
    cache_ir(root, name, song)

    # Charts
    lead_in = LEAD_IN
    chart_files: dict[str, bytes] = {}
    instrument_mask = 0
    stats: dict = {}
    automatic = auto_charts(song, grid, assignment, lead_in, stats)
    for index, (instrument, channel) in enumerate(INSTRUMENTS):
        counts = []
        for difficulty in charts.DIFFICULTIES:
            key = f"{instrument}/{difficulty.name}"
            if key not in automatic:
                continue
            chart = automatic[key]
            if edits.get(key):
                chart = apply_edits(chart, edits[key], warn=lambda text, key=key: summary.append(f"  AVISO edits.json ({key}): {text}"))
            validate_chart(key, chart)
            chart_files[f"chart_{instrument}_{difficulty.name}.bin"] = charts.chart_bytes(chart)
            counts.append(f"{difficulty.name} {len(chart)}")
        if counts:
            instrument_mask |= 1 << index
            summary.append(f"  {instrument:9} ({channel or 'ruido y DPCM'}): " + ", ".join(counts))
        else:
            summary.append(f"  {instrument:9} -")
    if not instrument_mask:
        raise SystemExit("La canción no tiene notas en ningún canal")
    if stats.get("moved") or stats.get("dropped"):
        summary.append(f"  separación de gemas del mismo carril: {stats.get('moved', 0)} notas pasaron a otro carril, "
                       f"{stats.get('dropped', 0)} se quitaron (de ~{sum(len(c) for c in chart_files.values()) // 2} entradas)")
    # Keyframes y tamaño del banco A
    records = [gbaudio.keyframe_record(result, song, at) for at in keyframe_at]
    key_bytes = b"".join(records)
    bank_a = FICHA_SIZE + sum(len(c) for c in chart_files.values()) + len(key_bytes)
    if bank_a > SLOT_BANK_SIZE:
        raise SystemExit(f"La ficha y los charts ({bank_a} bytes) no caben en un banco de 16 KB")

    # Escribir todo
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in list(out_dir.glob("chart_*.bin")) + [out_dir / "song.asm", out_dir / "info.json"]:
        if old.exists():
            old.unlink()
    for file_name, data in chart_files.items():
        (out_dir / file_name).write_bytes(data)
    (out_dir / "stream_b.bin").write_bytes(stream[:SLOT_BANK_SIZE])
    (out_dir / "stream_c.bin").write_bytes(stream[SLOT_BANK_SIZE:] or b"\xff")
    (out_dir / "keyframes.bin").write_bytes(key_bytes)
    for file_name, text in kept.items():
        write_lf(out_dir / file_name, text)
    end_frame = lead_in + n + 60
    write_lf(out_dir / "song.asm", song_asm(name, title, game, end_frame, lead_in, grid, instrument_mask, chart_files,
                                              [(at, offsets[at + 1]) for at in keyframe_at], [len(r) for r in records]))
    log = song.log + result.log
    info = {
        "name": name, "title": title, "game": game, "lead_in": lead_in, "end_frame": end_frame, "audio_frames": n,
        "beat": grid.frames_per_beat, "first_beat": lead_in + grid.first_beat, "instrument_mask": instrument_mask,
        "stream_bytes": len(stream), "bank_a_bytes": bank_a, "keyframes": keyframe_at,
        "audio": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in result.stats.items()},
        "log": log,
    }
    write_lf(out_dir / "info.json", json.dumps(info, indent=1, ensure_ascii=False) + "\n")
    write_lf(out_dir / "import.json", json.dumps(options.to_json(), indent=2, ensure_ascii=False) + "\n")

    header = [f"Canción '{title}' ({game}) -> src/songs/{name}/",
              f"  duración: {n} cuadros ({n / 60:.1f} s); tempo: {grid.frames_per_beat} cuadros por tiempo "
              f"({3600 / grid.frames_per_beat:.0f} BPM), primer tiempo en el cuadro {lead_in + grid.first_beat}",
              f"  stream de audio: {len(stream)} de {STREAM_CAPACITY} bytes; banco A: {bank_a} de {SLOT_BANK_SIZE}"]
    stats_line = (f"  volumen de los pulsos: {result.stats['pulse_notes']} notas, error medio {result.stats['envelope_error_mean']:.2f} "
                  f"pasos, máximo {result.stats['envelope_error_max']:.1f}; {result.stats['retriggers']} reinicios de nota extra")
    return header + [stats_line] + summary + [f"  AVISO audio: {line}" for line in log]


def song_asm(name: str, title: str, game: str, end_frame: int, lead_in: int, grid: charts.BeatGrid, instrument_mask: int,
             chart_files: dict[str, bytes], keyframes: list[tuple[int, int]], key_sizes: list[int]) -> str:
    lines = [
        "; Generado por `gbband import-song` - no editar a mano",
        "; SONG_BANK lo define la lista de canciones (build/list.asm) antes de incluir este archivo",
        "",
        f'SECTION "Cancion {name} A", ROMX[$4000], BANK[SONG_BANK]',
        f"Song_{name}::",
        '    db "GBBS", 1',
        f'    db "{title:<{TITLE_LEN}}"',
        f'    db "{game:<{GAME_LEN}}"',
        f"    dw {end_frame}, {lead_in}",
        f"    db {grid.frames_per_beat}",
        f"    dw {lead_in + grid.first_beat}",
        f"    db %{instrument_mask:08b}, 3",
    ]
    for slot in range(16):
        instrument, difficulty = INSTRUMENTS[slot // 4][0], charts.DIFFICULTIES[slot % 4].name
        file_name = f"chart_{instrument}_{difficulty}.bin"
        lines.append(f"    dw Song_{name}_{instrument}_{difficulty}" if file_name in chart_files else "    dw 0")
    lines.append("    dw $4000")
    for k, (frame, offset) in enumerate(keyframes):
        lines += [f"    dw {frame}", f"    db SONG_BANK + 1 + {offset // SLOT_BANK_SIZE}",
                  f"    dw ${0x4000 + offset % SLOT_BANK_SIZE:04X}", f"    dw Song_{name}_keyframe{k}"]
    lines.append("")
    for file_name in sorted(chart_files):
        label = file_name[len("chart_"):-len(".bin")]
        lines += [f"Song_{name}_{label}:", f'    INCBIN "songs/{name}/{file_name}"']
    lines.append("")
    offset = 0
    for k, size in enumerate(key_sizes):
        lines += [f"Song_{name}_keyframe{k}:", f'    INCBIN "songs/{name}/keyframes.bin", {offset}, {size}']
        offset += size
    lines += [
        "",
        f'SECTION "Cancion {name} B", ROMX[$4000], BANK[SONG_BANK + 1]',
        f'    INCBIN "songs/{name}/stream_b.bin"',
        "",
        f'SECTION "Cancion {name} C", ROMX[$4000], BANK[SONG_BANK + 2]',
        f'    INCBIN "songs/{name}/stream_c.bin"',
        "",
    ]
    return "\n".join(lines)


# ---- lista de canciones --------------------------------------------------------------------------------------------

def tracked_songs(root: Path = ROOT) -> set[str]:
    """Las canciones que git versiona (las originales): solo esas entran a la ROM de release."""
    import subprocess

    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "src/songs"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {m.group(1) for line in out.splitlines() if (m := re.fullmatch(r"src/songs/([^/]+)/song\.asm", line))}


def list_songs(solo: list[str] | None = None, release: bool = False, root: Path = ROOT) -> list[str]:
    """Escribe build/list.asm con las canciones de src/songs/*/song.asm (orden alfabético; el lugar de cada una en
    la lista es su slot). `solo` son patrones (como -Solo de build.ps1) y `release` deja solo las versionadas en git."""
    import fnmatch

    names = sorted(p.parent.name for p in (root / "src" / "songs").glob("*/song.asm") if p.parent.name != TITLE_SONG)
    if release:
        tracked = tracked_songs(root)
        names = [n for n in names if n in tracked]
    if solo:
        patterns = [p for chunk in solo for p in re.split(r"[,\s]+", chunk) if p]
        names = [n for n in names if any(fnmatch.fnmatch(n, p) for p in patterns)]
        if not names:
            raise SystemExit(f"Ninguna canción coincide con {', '.join(patterns)}")
    if not names:
        raise SystemExit("No hay canciones en src/songs/")
    if len(names) > 32:
        raise SystemExit(f"Hay {len(names)} canciones y el cartucho tiene 32 slots: compila un subconjunto con -Solo <patrón>")
    lines = ["; Generado por `gbband list-songs` - lista de canciones de la ROM, en orden alfabético",
             "; Cada canción ocupa 3 bancos desde el 16 (ver src/song_format.inc)", f"DEF NUM_SONGS EQU {len(names)}", ""]
    for slot, n in enumerate(names):
        lines += [f"REDEF SONG_BANK EQU FIRST_SONG_BANK + BANKS_PER_SONG * {slot}", f'INCLUDE "songs/{n}/song.asm"', ""]
    lines += ['SECTION "Tabla de canciones", ROM0', "SongTable::"]
    lines += [f"    db FIRST_SONG_BANK + BANKS_PER_SONG * {slot}  ; {n}" for slot, n in enumerate(names)]
    has_title = (root / "src" / "songs" / TITLE_SONG / "song.asm").exists()
    if has_title:                                                       # la música del título, en su propio slot
        lines += ["", f"REDEF SONG_BANK EQU {TITLE_BANK}", f'INCLUDE "songs/{TITLE_SONG}/song.asm"']
    (root / "build").mkdir(exist_ok=True)
    # lo que el código necesita saber antes de incluir la lista (se incluye al principio de main.asm)
    defs = ["; Generado por `gbband list-songs`"] + ([f"DEF HAS_TITLE_MUSIC EQU 1", f"DEF TITLE_BANK EQU {TITLE_BANK}"] if has_title else [])
    write_lf(root / "build" / "list_defs.inc", "\n".join(defs) + "\n")
    write_lf(root / "build" / "list.asm", "\n".join(lines) + "\n")
    return names


def reimport(names: list[str] | None = None, root: Path = ROOT) -> None:
    songs_dir = root / "src" / "songs"
    names = names or sorted(p.parent.name for p in songs_dir.glob("*/import.json"))
    for name in names:
        options_file = songs_dir / name / "import.json"
        if not options_file.exists():
            raise SystemExit(f"{name} no tiene import.json: impórtala una vez con import-song")
        data = json.loads(options_file.read_text(encoding="utf-8"))
        print(f"=== {name}")
        print("\n".join(import_song(Options(name=name, **data), root)))
