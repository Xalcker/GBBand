"""Las notas de una fuente (NSF, VGM de Game Boy, GBS o FamiStudio) en JSON, para arreglarlas en otra consola.

    uv run gbband export-notes "songs_src/Juego.nsf" --track 2 --out notas.json

Sale de la misma IR que `import-song` (ver ir.py), así que las notas son las que verían los charts. Formato:

    {"title", "game", "frames",                         frames = duración en cuadros (60 por segundo)
     "channels": {"Square1": [[cuadro, cuadros, altura MIDI, volumen 0-15], ...], "Square2": [...], "Triangle": [...]},
     "drums": [[cuadro, papel, platillo], ...]}          papel: kick, snare, tom1, tom2 o tom3 (ver bandcore.drums)

El volumen de cada nota es el máximo de su canal mientras suena. La batería usa la asignación de drums.json si se
pasa `--drums` (por ejemplo, la de una canción ya importada y revisada en el editor); si no, la sugerencia automática.
GENBand la convierte a FM con audio/arreglo_fm.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import drums, ir, songs


def export_notes(source: Path, options: songs.Options, assignment: dict | None = None) -> dict:
    song, title, game = songs.load_source(source, options)
    channels = {}
    for name in ir.TONAL:
        vol = song.tracks[name].vol
        channels[name] = [
            [n.frame, n.duration, n.pitch, max(vol[n.frame : n.frame + max(1, n.duration)] or [0])]
            for n in song.notes.get(name, [])
        ]
    if assignment is None:
        assignment = drums.suggest_assignment(drums.drum_groups(song))
    hits = [[h.frame, h.role, h.cymbal] for h in drums.drum_hits(song, assignment)]
    return {"title": options.title or title, "game": options.game or game, "frames": song.length_frames,
            "channels": channels, "drums": hits, "log": song.log}


def write_notes(data: dict, out: Path) -> None:
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
