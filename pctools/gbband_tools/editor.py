"""Editor visual de charts: una página HTML local (Canvas, sin dependencias) servida por `gbband edit-chart`.

La página muestra las notas de cada canal de la canción y el chart de un instrumento y dificultad. Los datos salen de
la misma tubería que `import-song` (songs.py): la IR de la canción, la rejilla de tiempos y los charts automáticos;
encima se aplican las ediciones de edits.json (chartedit.py).

"Escuchar" toca el MISMO stream de registros del APU que lleva la ROM (stream_b.bin y stream_c.bin): el servidor lo
decodifica a escrituras por cuadro y gbplayer.js las sintetiza. "Exportar a la ROM" guarda las ediciones y vuelve a
importar la canción (como `gbband reimport`), que reescribe charts, audio y ficha con las ediciones encima.
"""

from __future__ import annotations

import contextlib
import io
import json
import pickle
import re
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import audio_gb as gb
from . import ir, songs
from .chart import DIFFICULTIES, BeatGrid, ChartNote, chart_bytes
from .chartedit import (
    EDITS_FILE,
    apply_edits,
    chart_from_json,
    chart_problems,
    diff_charts,
    load_edits,
    save_edits,
    validate_chart,
)
from .drums import (
    ROLE_LABELS,
    ROLE_LANE,
    ROLES,
    check_assignment,
    drum_groups,
    load_drums,
    save_drums,
    suggest_assignment,
)
from .m3u import find_playlist

HTML_PATH = Path(__file__).with_name("editor.html")
HOME_PATH = Path(__file__).with_name("home.html")  # la página sin canción abierta
MENU_PATH = Path(__file__).with_name("menu.html")  # el menú Archivo, compartido por las dos
GBPLAYER_PATH = Path(__file__).with_name("gbplayer.js")  # el APU que toca la canción
ROOT = songs.ROOT
SONGS_DIR = songs.SONGS_DIR
SOURCE_SUFFIXES = (".nsf", ".nsfe", ".txt")


@dataclass
class SongSource:
    name: str
    song_dir: Path
    options: dict
    song: ir.SongIR
    grid: BeatGrid
    info: dict


def load_song_source(name: str, root: Path = ROOT) -> SongSource:
    """La IR de la canción `name`: de build/songs/<nombre>/ir.pkl (la deja la importación) o, si falta, de su fuente."""
    song_dir = root / "src" / "songs" / name
    options_file = song_dir / "import.json"
    if not options_file.exists():
        raise ValueError(f"{name} no tiene import.json: impórtala con import-song (o elige una de src/songs/)")
    options = json.loads(options_file.read_text(encoding="utf-8"))
    cache = root / "build" / "songs" / name / "ir.pkl"
    if cache.exists():
        song = pickle.loads(cache.read_bytes())
    else:
        song, _, _ = songs.load_source(root / options["source"], songs.Options(name=name, **options))
        songs.cache_ir(root, name, song)
    info = json.loads((song_dir / "info.json").read_text(encoding="utf-8"))
    return SongSource(name, song_dir, options, song, songs.beat_grid(song, options.get("beat_frames")), info)


def drum_assignment(src: SongSource, override: dict | None = None) -> tuple[dict, bool]:
    """La asignación de papeles de la batería: la que manda la página, la de drums.json o, si no hay,
    la sugerida. Devuelve (asignación, ¿es solo una sugerencia sin guardar?)."""
    if override is not None:
        check_assignment(override)
        return override, False
    saved = load_drums(src.song_dir)
    if saved is not None:
        return saved, False
    return suggest_assignment(drum_groups(src.song)), True


def auto_charts(src: SongSource, assignment: dict | None = None) -> dict[str, list[ChartNote]]:
    return songs.auto_charts(src.song, src.grid, drum_assignment(src, assignment)[0], songs.LEAD_IN)


def edited_charts(src: SongSource, auto: dict[str, list[ChartNote]], edits: dict | None = None) -> tuple[dict, list[str]]:
    """Los charts automáticos con las ediciones de edits.json encima, y los avisos de lo que no se pudo aplicar."""
    edits = load_edits(src.song_dir) if edits is None else edits
    warnings: list[str] = []
    result = {}
    for key, chart in auto.items():
        warn = lambda text, key=key: warnings.append(f"{key}: {text}")  # noqa: E731
        result[key] = apply_edits(chart, edits[key], warn) if edits.get(key) else chart
    return result, warnings


def chart_json(chart: list[ChartNote]) -> list[dict]:
    return [{"frame": n.frame, "mask": n.mask, "end": n.end, "star": n.star, "cymbal": n.cymbal} for n in chart]


def lanes_for(key: str) -> int:
    """Carriles de la dificultad de un chart ("guitarra/facil" -> 3)."""
    difficulty = key.split("/")[1]
    return next(d.lanes for d in DIFFICULTIES if d.name == difficulty)


def problems_for(key: str, chart: list[ChartNote]) -> list[dict]:
    return chart_problems(chart, lanes_for(key), key.startswith("bateria/"))


def build_payload(src: SongSource) -> dict:
    """Todo lo que la página necesita, como JSON."""
    lead_in = songs.LEAD_IN
    assignment, suggested = drum_assignment(src)
    auto = auto_charts(src, assignment)
    charts, warnings = edited_charts(src, auto)
    return {
        "drums": {
            "groups": [{"key": g.key, "channel": g.channel, "tone": g.tone, "instrument": g.instrument,
                        "count": g.count, "avgDuration": round(g.avg_duration, 1)}
                       for g in drum_groups(src.song)],
            "assignment": assignment,
            "suggested": suggested,
            "roles": [{"id": role, "label": ROLE_LABELS[role], "lane": ROLE_LANE[role]} for role in ROLES],
        },
        "name": src.name,
        "title": src.info.get("title") or src.name,
        "game": src.info.get("game") or "",
        "leadIn": lead_in,
        "endFrame": lead_in + src.song.length_frames,
        "audioFrames": src.info["audio_frames"],
        "framesPerBeat": src.grid.frames_per_beat,
        "firstBeat": lead_in + src.grid.first_beat,
        # [cuadro, altura, duración] por canal; los cuadros ya cuentan la entrada de la autopista
        "channels": {
            channel: [[lead_in + n.frame, n.pitch, n.duration] for n in src.song.notes.get(channel, [])]
            for channel in ir.CHANNELS
        },
        "instruments": [{"name": name, "channel": channel} for name, channel in songs.INSTRUMENTS
                        if any(k.startswith(name + "/") for k in charts)],
        "difficulties": [{"name": d.name, "lanes": d.lanes} for d in DIFFICULTIES],
        "charts": {key: chart_json(chart) for key, chart in charts.items()},
        "auto": {key: chart_json(chart) for key, chart in auto.items()},
        "problems": {key: problems_for(key, chart) for key, chart in charts.items()},
        "warnings": warnings,
        "chartBytes": sum(len(chart_bytes(chart)) for chart in charts.values()),
        "editable": False,
    }


def player_payload(src: SongSource) -> dict:
    """El stream FRS de la ROM decodificado: [[cuadro de audio, wave RAM o null, [[registro, valor], ...]], ...]."""
    stream = (src.song_dir / "stream_b.bin").read_bytes() + (src.song_dir / "stream_c.bin").read_bytes()
    frames = []
    for index, fw in enumerate(gb.decode_stream(stream)):
        regs = [[gb.CHANNEL_BASE[ch] + r - 0xFF00, value] for ch, items in sorted(fw.channels.items()) for r, value in sorted(items.items())]
        if regs or fw.wave is not None:
            frames.append([index, list(fw.wave) if fw.wave is not None else None, regs])
    return {"frames": frames}


def save_edits_from_page(src: SongSource, charts: dict[str, list[ChartNote]],
                         assignment: dict | None = None) -> dict[str, list[dict]]:
    """Guarda en edits.json lo que difiere de los charts automáticos (y en drums.json la asignación de la
    batería, si la manda la página). Falla si algún chart no se puede tocar."""
    auto = auto_charts(src, assignment)
    if set(charts) != set(auto):
        raise ValueError(f"faltan o sobran charts: se esperaban {sorted(auto)}")
    edits = {}
    for key, chart in charts.items():
        validate_chart(key, chart)
        edits[key] = diff_charts(auto[key], chart)
    if assignment is None and load_drums(src.song_dir) is None and any(
            ops for key, ops in edits.items() if key.startswith("bateria/")):
        assignment = drum_assignment(src)[0]   # las ediciones de la batería van atadas a la asignación con que se hicieron
    if assignment is not None:
        save_drums(src.song_dir, assignment)
    save_edits(src.song_dir, edits)
    return edits


def export_to_rom(src: SongSource, charts: dict[str, list[ChartNote]], assignment: dict | None = None) -> str:
    """Guarda las ediciones y vuelve a importar la canción: charts, audio y ficha se reescriben con las ediciones encima."""
    save_edits_from_page(src, charts, assignment)
    log = songs.import_song(songs.Options(name=src.name, **json.loads((src.song_dir / "import.json").read_text(encoding="utf-8"))))
    songs.list_songs()
    return "\n".join(log)


def render_page(payload: dict, template: Path = HTML_PATH) -> str:
    data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    return (template.read_text(encoding="utf-8").replace("__MENU__", MENU_PATH.read_text(encoding="utf-8"), 1)
            .replace("__GBPLAYER__", GBPLAYER_PATH.read_text(encoding="utf-8"), 1).replace("__DATA__", data, 1))


# --- Menú Archivo: canciones disponibles, fuentes para importar y la canción abierta -----------

class App:
    """La canción abierta (o ninguna) del servidor. Un candado evita que dos acciones se pisen."""

    def __init__(self, src: SongSource | None = None):
        self.src = src
        self.lock = threading.RLock()


def list_songs() -> list[dict]:
    result = []
    for options in sorted(SONGS_DIR.glob("*/import.json")):
        info_file = options.parent / "info.json"
        info = json.loads(info_file.read_text(encoding="utf-8")) if info_file.exists() else {}
        result.append({"name": options.parent.name, "title": info.get("title", options.parent.name),
                       "game": info.get("game", ""), "edited": (options.parent / EDITS_FILE).exists()})
    return result


def list_sources() -> list[dict]:
    """Archivos que se pueden importar como canción nueva: los de songs_src/ (NSF) y los proyectos de audio/."""
    found = []
    for folder in (ROOT / "songs_src", ROOT / "audio"):
        for path in sorted(folder.glob("*")) if folder.is_dir() else []:
            if path.suffix.lower() in SOURCE_SUFFIXES:
                found.append({"path": path.relative_to(ROOT).as_posix(), "name": path.stem})
    return found


def resolve_source(text: str) -> Path:
    path = Path(text.strip().strip('"'))
    path = path if path.is_absolute() else ROOT / path
    if path.suffix.lower() not in SOURCE_SUFFIXES or not path.is_file():
        raise ValueError(f"no encontré un archivo .nsf, .nsfe o .txt en {path}")
    return path


def list_tracks(source: str) -> dict:
    """Las pistas del .m3u junto a un NSF (vacío si no hay)."""
    path = resolve_source(source)
    playlist = find_playlist(path) if path.suffix.lower() in (".nsf", ".nsfe") else None
    if not playlist:
        return {"game": None, "tracks": []}
    return {"game": playlist.game,
            "tracks": [{"number": t.number, "title": t.title, "seconds": t.seconds} for t in playlist.tracks.values()]}


def open_song(app: App, name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or not (SONGS_DIR / name / "import.json").exists():
        raise ValueError(f"no existe la canción {name}")
    app.src = load_song_source(name)


def import_new_song(app: App, body: dict) -> str:
    """Importa una canción nueva (como `gbband import-song`), la abre y devuelve el resumen de la importación."""
    name = str(body.get("name", "")).strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("el identificador son minúsculas, números y _ (empezando con letra)")
    if (SONGS_DIR / name).exists():
        raise ValueError(f"ya existe la canción {name}: ábrela, o elige otro identificador")
    source = resolve_source(str(body.get("source", "")))
    number = body.get("number")
    is_nsf = source.suffix.lower() in (".nsf", ".nsfe")
    has_playlist = is_nsf and find_playlist(source) is not None
    shown = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else str(source)
    options = songs.Options(
        source=shown, name=name, title=body.get("title") or None, game=body.get("game") or None,
        track=number if has_playlist else None,                      # el .m3u cuenta desde 1
        song=0 if has_playlist or number is None else number - 1,    # el archivo, desde 0
        duration=body.get("duration") or None, beat_frames=body.get("beat_frames") or None)
    try:
        log = songs.import_song(options)
    except SystemExit as error:
        raise ValueError(str(error.code)) from None
    songs.list_songs()
    open_song(app, name)
    return "\n".join(log)


class Handler(BaseHTTPRequestHandler):
    app: App  # lo fija serve()

    def log_message(self, format, *args):  # sin ruido en la terminal
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        url = urlparse(self.path)
        try:
            with self.app.lock:
                if url.path == "/":
                    if self.app.src is None:
                        page = render_page({"home": True}, HOME_PATH)
                    else:
                        page = render_page({**build_payload(self.app.src), "editable": True})
                    self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
                elif url.path == "/api/player":
                    if self.app.src is None:
                        raise ValueError("no hay canción abierta")
                    self._json(200, player_payload(self.app.src))
                elif url.path == "/api/songs":
                    self._json(200, {"songs": list_songs()})
                elif url.path == "/api/sources":
                    self._json(200, {"sources": list_sources()})
                elif url.path == "/api/tracks":
                    self._json(200, list_tracks(parse_qs(url.query).get("source", [""])[0]))
                else:
                    self._send(404, b"no encontrado", "text/plain; charset=utf-8")
        except (ValueError, KeyError, OSError) as error:
            self._json(400, {"error": str(error)})

    def do_POST(self) -> None:
        # Solo la propia página: otro origen (una web cualquiera) no puede escribir en el proyecto
        if self.headers.get("Origin") not in (None, f"http://{self.headers.get('Host')}"):
            self._json(403, {"error": "origen no permitido"})
            return
        app = self.app
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            with app.lock:
                if self.path == "/api/open":
                    open_song(app, str(body.get("name", "")))
                    self._json(200, {"message": f"abierta {app.src.name}"})
                elif self.path == "/api/close":
                    app.src = None
                    self._json(200, {"message": "cerrada"})
                elif self.path == "/api/import":
                    self._json(200, {"message": import_new_song(app, body)})
                elif self.path in ("/api/validate", "/api/save", "/api/export", "/api/drums"):
                    src = app.src
                    if src is None or body.get("song") != src.name:
                        raise ValueError("la canción de esta página ya no es la abierta: recarga la página")
                    if self.path == "/api/validate":
                        chart = chart_from_json(body["chart"])
                        self._json(200, {"problems": problems_for(body["key"], chart)})
                    elif self.path == "/api/drums":
                        # Otra asignación: los charts de batería se rehacen (con las ediciones ya guardadas encima)
                        assignment, _ = drum_assignment(src, body["assignment"])
                        auto = auto_charts(src, assignment)
                        charts, warnings = edited_charts(src, auto)
                        self._json(200, {
                            "charts": {k: chart_json(c) for k, c in charts.items() if k.startswith("bateria/")},
                            "auto": {k: chart_json(c) for k, c in auto.items() if k.startswith("bateria/")},
                            "problems": {k: problems_for(k, c) for k, c in charts.items() if k.startswith("bateria/")},
                            "warnings": warnings,
                        })
                    else:
                        charts = {key: chart_from_json(items) for key, items in body["charts"].items()}
                        assignment = body.get("drums")
                        if self.path == "/api/save":
                            edits = save_edits_from_page(src, charts, assignment)
                            self._json(200, {"message": f"guardado ({sum(len(ops) for ops in edits.values())} ediciones)"})
                        else:
                            with contextlib.redirect_stdout(io.StringIO()):
                                message = export_to_rom(src, charts, assignment)
                            app.src = load_song_source(src.name)
                            self._json(200, {"message": f"exportado a la ROM: charts, audio y ficha regenerados\n{message}"})
                else:
                    self._json(404, {"error": "no encontrado"})
        except (ValueError, KeyError, TypeError, SystemExit) as error:
            self._json(400, {"error": str(getattr(error, "code", error))})


def make_server(app: App, port: int) -> ThreadingHTTPServer:
    Bound = type("Bound", (Handler,), {"app": app})
    return ThreadingHTTPServer(("127.0.0.1", port), Bound)


def serve(name: str | None, port: int, open_browser: bool) -> None:
    app = App(load_song_source(name) if name else None)
    server = make_server(app, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Editor de charts{f' de {name!r}' if name else ''}: {url}  (Ctrl+C para cerrar)")
    if open_browser:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
