"""Proyectos de texto de FamiStudio ("famistudio-txt") a IR.

Las canciones originales de GBBand se componen en Python (audio/*.py) y se guardan como proyectos de texto de
FamiStudio (audio/*.txt), igual que en NESBand. Este módulo los lee SIN FamiStudio: solo hacen falta las notas y
las envolventes de volumen y duty de cada instrumento. Lo que no se entiende (envolventes de tono o de arpegio,
vibrato, deslizamientos, notas de liberación...) se ignora y se avisa en el log de la IR.

La jerarquía va por tabuladores:
    Project > DPCMSample, Instrument > Envelope, DPCMMapping ; Song > Channel > Pattern > Note ; PatternInstance
En el modo de tempo "FamiStudio", el Time de las notas está en cuadros.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import ir

_ATTR = re.compile(r'(\w+)="([^"]*)"')
_NOTE_NAME = re.compile(r"^([A-G])(#?)(-?\d)$")
_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CHANNEL_TYPES = ir.CHANNELS
KNOWN_ENVELOPES = {"Volume", "DutyCycle"}
KNOWN_NOTE_ATTRS = {"Time", "Value", "Duration", "Instrument", "DeltaCounter"}


def note_to_midi(value: str) -> int | None:
    match = _NOTE_NAME.match(value)
    if not match:
        return None  # "Stop", "Release", etc.
    letter, sharp, octave = match.groups()
    return 12 * (int(octave) + 1) + _PITCH_CLASS[letter] + (1 if sharp else 0)


@dataclass
class Instrument:
    name: str
    envelopes: dict[str, list[int]] = field(default_factory=dict)
    mappings: dict[int, str] = field(default_factory=dict)  # DPCM: nota MIDI -> nombre del sample


@dataclass
class TextSong:
    name: str
    attrs: dict[str, str]
    pattern_frames: list[int] = field(default_factory=list)
    notes: dict[str, list[tuple[int, int, int, str | None]]] = field(default_factory=dict)  # canal -> (cuadro, altura, duración, instrumento)
    stops: dict[str, list[int]] = field(default_factory=dict)  # canal -> cuadros con "Stop"

    @property
    def length_frames(self) -> int:
        return sum(self.pattern_frames)

    @property
    def frames_per_beat(self) -> int:
        return int(self.attrs["BeatLength"]) * int(self.attrs["NoteLength"])


@dataclass
class Project:
    attrs: dict[str, str]
    instruments: dict[str, Instrument]
    samples: dict[str, str]  # nombre -> datos hexadecimales
    songs: list[TextSong]
    ignored: set[str] = field(default_factory=set)


def parse_text(text: str) -> Project:
    project = Project({}, {}, {}, [])
    songs: list[TextSong] = []
    patterns: dict[str, list[tuple[int, int, int, str | None]]] = {}
    pattern_stops: dict[str, list[int]] = {}
    instances: list[tuple[int, str]] = []
    custom: dict[int, dict[str, str]] = {}
    channel = ""
    pattern = ""
    instrument: Instrument | None = None

    def finish_channel() -> None:
        if songs and channel:
            song = songs[-1]
            starts = _pattern_starts(song)
            notes, stops = [], []
            for index, name in sorted(instances):
                if index >= len(starts):
                    continue
                for time, pitch, duration, instrument_name in patterns.get(name, []):
                    notes.append((starts[index] + time, pitch, duration, instrument_name))
                for time in pattern_stops.get(name, []):
                    stops.append(starts[index] + time)
            song.notes[channel] = sorted(notes)
            song.stops[channel] = sorted(stops)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        tag = stripped.split(" ", 1)[0]
        attrs = dict(_ATTR.findall(stripped))
        if tag == "Project":
            project.attrs = attrs
            if attrs.get("TempoMode", "FamiStudio") != "FamiStudio":
                raise ValueError("El proyecto usa tempo de FamiTracker. Ábrelo en FamiStudio y conviértelo a tempo FamiStudio.")
        elif tag == "DPCMSample":
            project.samples[attrs["Name"]] = attrs.get("Data", "")
        elif tag == "Instrument":
            instrument = Instrument(attrs["Name"])
            project.instruments[instrument.name] = instrument
        elif tag == "Envelope" and instrument is not None and not songs:
            kind = attrs["Type"]
            if kind in KNOWN_ENVELOPES:
                values = [int(v) for v in attrs["Values"].split(",") if v != ""]
                instrument.envelopes[kind] = values
                if "Loop" in attrs or "Release" in attrs:
                    project.ignored.add(f"envolvente {kind} de {instrument.name} con Loop/Release (se mantiene el último valor)")
            else:
                project.ignored.add(f"envolvente {kind} de {instrument.name}")
        elif tag == "DPCMMapping" and instrument is not None:
            note = note_to_midi(attrs["Note"])
            if note is not None:
                instrument.mappings[note] = attrs["Sample"]
        elif tag == "Song":
            finish_channel()
            channel, patterns, pattern_stops, instances, custom = "", {}, {}, [], {}
            songs.append(TextSong(attrs.get("Name", f"Song {len(songs)}"), attrs))
        elif tag == "PatternCustomSettings":
            custom[int(attrs["Time"])] = attrs
        elif tag == "Channel":
            finish_channel()
            if channel == "" and songs and not songs[-1].pattern_frames:
                _compute_pattern_frames(songs[-1], custom)
            channel, patterns, pattern_stops, instances = attrs["Type"], {}, {}, []
        elif tag == "Pattern":
            pattern = attrs["Name"]
            patterns[pattern] = []
            pattern_stops[pattern] = []
        elif tag == "Note" and "Value" in attrs:
            pitch = note_to_midi(attrs["Value"])
            for key in attrs:
                if key not in KNOWN_NOTE_ATTRS:
                    project.ignored.add(f"atributo {key} de las notas")
            if pitch is not None:
                patterns[pattern].append((int(attrs["Time"]), pitch, int(attrs.get("Duration", "1")), attrs.get("Instrument")))
            elif attrs["Value"] == "Stop":
                pattern_stops[pattern].append(int(attrs["Time"]))
            else:
                project.ignored.add(f"notas {attrs['Value']}")
        elif tag == "PatternInstance":
            instances.append((int(attrs["Time"]), attrs["Pattern"]))
    finish_channel()
    project.songs = songs
    return project


def _compute_pattern_frames(song: TextSong, custom: dict[int, dict[str, str]]) -> None:
    length = int(song.attrs["Length"])
    for index in range(length):
        settings = custom.get(index, song.attrs)
        song.pattern_frames.append(int(settings["Length" if index in custom else "PatternLength"]) * int(settings["NoteLength"]))


def _pattern_starts(song: TextSong) -> list[int]:
    starts, total = [], 0
    for frames in song.pattern_frames:
        starts.append(total)
        total += frames
    return starts


# ---- IR ------------------------------------------------------------------------------------------------------

def envelope_value(values: list[int] | None, index: int, default: int) -> int:
    """Valor de una envolvente en el cuadro `index` de la nota (se mantiene el último valor al terminar)."""
    if not values:
        return default
    return values[min(index, len(values) - 1)]


def to_ir(project: Project, song_index: int = 0, game: str = "") -> ir.SongIR:
    """La IR de una canción del proyecto: notas exactas y el estado de cada canal tonal en cada cuadro."""
    song = project.songs[song_index]
    frames = song.length_frames
    result = ir.SongIR(song.name, game or project.attrs.get("Name", ""), frames, {}, {c: [] for c in ir.CHANNELS},
                       song.frames_per_beat, source="proyecto de FamiStudio")
    for what in sorted(project.ignored):
        result.warn(f"se ignoró: {what}")

    for channel in ir.CHANNELS:
        raw = song.notes.get(channel, [])
        stops = song.stops.get(channel, [])
        notes = [ir.Note(f, p, d, None, name) for f, p, d, name in raw]
        result.notes[channel] = notes
        if channel in ir.TONAL:
            result.tracks[channel] = _tonal_track(project, channel, raw, stops, frames)
    return result


def _tonal_track(project: Project, channel: str, notes, stops: list[int], frames: int) -> ir.Track:
    track = ir.Track.silent(frames)
    ends = sorted(stops)
    for i, (start, pitch, duration, name) in enumerate(notes):
        limit = start + duration
        if i + 1 < len(notes):
            limit = min(limit, notes[i + 1][0])  # la nota siguiente corta a la anterior
        for stop in ends:
            if start < stop < limit:
                limit = stop
        limit = min(limit, frames)
        instrument = project.instruments.get(name or "")
        volume = instrument.envelopes.get("Volume") if instrument else None
        duty = instrument.envelopes.get("DutyCycle") if instrument else None
        freq = ir.midi_hz(pitch)
        for k, frame in enumerate(range(start, limit)):
            vol = 15 if channel == "Triangle" else envelope_value(volume, k, 15)
            track.freq[frame] = freq
            track.vol[frame] = vol
            track.duty[frame] = envelope_value(duty, k, 2)
            track.trig[frame] = k == 0
    return track
