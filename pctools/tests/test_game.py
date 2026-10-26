"""Pruebas de juego: un bot toca las canciones en PyBoy, en modo DMG y CGB.

Cada caso deja resultado.txt y capturas en build/test-<canción>-<bot>-<instrumento>-<dificultad>-<modo>/. Compila el
ROM al empezar (build.ps1 / build.sh), así que necesitan RGBDS.

Por omisión corren 3 canciones representativas (la demo, una con DPCM y una larga); con GBBAND_COMPLETA=1, las diez.
"""

import os
from pathlib import Path

import pytest

from gbband_tools import layout, playtest

ROOT = Path(__file__).resolve().parents[2]
MODES = ("dmg", "cgb")
LATE_LIMIT = 2
ALL_SONGS = playtest.song_names()
QUICK_SONGS = [s for s in ("demo", "carrera", "salto") if s in ALL_SONGS]
SONGS = ALL_SONGS if os.environ.get("GBBAND_COMPLETA") else QUICK_SONGS


def out_dir(song: str, bot: str, instrument: str, difficulty: str, mode: str, tag: str = "") -> Path:
    return ROOT / "build" / f"test-{song}{tag}-{bot}-{instrument}-{difficulty}-{mode}"


@pytest.fixture(scope="session")
def rom_b():
    return playtest.build_rom("B")


@pytest.fixture(scope="session")
def rom_a():
    return playtest.build_rom("A", "A")


def common_checks(result: playtest.Result) -> None:
    v = result.values
    assert v["late"] <= LATE_LIMIT, f"{v['late']} cuadros atrasados"
    assert v["underrun"] == 0, "el audio se quedó sin cuadros decodificados"
    assert v["vq_overflow"] == 0, "la cola de VRAM se llenó"
    assert v["overrun"] == 0, "la cola de VRAM terminó fuera del VBlank"
    assert v["vq_max_bytes"] <= 96, f"{v['vq_max_bytes']} bytes de VRAM en un cuadro (objetivo regular <= 96)"
    assert result.max_sprites_line <= 8, f"{result.max_sprites_line} sprites en una línea"
    assert v["state"] == playtest.STATE_END, "la canción no terminó"


def perfect_cases():
    cases = []
    for song in SONGS:
        data = playtest.load_song(song)
        for instrument in playtest.INSTRUMENTS:
            if (instrument, "experto") not in data.charts:
                continue
            diffs = layout.DIFFICULTIES if instrument == "guitarra" else ("experto",)
            for difficulty in diffs:
                for mode in MODES:
                    cases.append((song, instrument, difficulty, mode))
    return cases


@pytest.mark.parametrize("song,instrument,difficulty,mode", perfect_cases())
def test_perfecto(rom_b, song, instrument, difficulty, mode):
    """Acierta todo: puntaje exacto, 100 % de las notas, y cada nota del chart cae en el mismo cuadro en que el
    audio dispara la nota del canal de su instrumento (prueba de sincronía)."""
    visual = song == QUICK_SONGS[0] and instrument == "guitarra" and difficulty in ("facil", "experto") and mode == "dmg"
    r = playtest.run_case(rom_b, mode, song, instrument, difficulty, "perfecto",
                          out_dir(song, "perfecto", instrument, difficulty, mode), visual=visual)
    v = r.values
    common_checks(r)
    assert v["hits"] == r.total_notes and v["misses"] == 0 and v["air"] == 0
    assert v["max_combo"] == r.total_notes
    assert v["score"] == playtest.expected_score(r.total_notes)
    data = playtest.load_song(song)
    assert playtest.sync_errors(r, data.chart(instrument, difficulty)) == []
    for ch in range(4):
        assert r.note_on[ch] == data.note_on[ch], f"canal {ch + 1}: las altas de nota no caen en los cuadros del stream"
    assert not r.muted_late and r.nr51_late == 0xFF
    if visual:
        assert r.visual_samples > 300
        assert r.visual_max <= 1.5 + 1e-6, f"error visual {r.visual_max:.2f} px"


@pytest.mark.parametrize("instrument,channel_mask", [("guitarra", 0x11), ("teclado", 0x22), ("bajo", 0x44), ("bateria", 0x88)])
@pytest.mark.parametrize("mode", MODES)
def test_sin_tocar(rom_b, mode, instrument, channel_mask):
    """No toca nada: todo se pierde y el canal del instrumento queda callado (y solo ese)."""
    song = QUICK_SONGS[0]
    r = playtest.run_case(rom_b, mode, song, instrument, "experto", "sin-tocar",
                          out_dir(song, "sin-tocar", instrument, "experto", mode))
    v = r.values
    common_checks(r)
    assert v["hits"] == 0 and v["score"] == 0 and v["max_combo"] == 0
    assert v["misses"] == r.total_notes
    assert r.muted_late and r.nr51_late == 0xFF & ~channel_mask, f"NR51={r.nr51_late:#04x}"


@pytest.mark.parametrize("mode", MODES)
def test_machacando(rom_b, mode):
    """Machaca botones: acierta alguna nota de suerte, pero el combo nunca sube y el puntaje se queda abajo."""
    song = QUICK_SONGS[0]
    r = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "machacando",
                          out_dir(song, "machacando", "guitarra", "experto", mode))
    v = r.values
    common_checks(r)
    assert v["max_combo"] <= 5
    assert playtest.stars(v["score"], r.total_notes)[1] <= 2
    assert v["air"] > 0


def test_colocacion_a_contra_b(rom_a, rom_b):
    """Mide el error visual de las dos colocaciones con el ROM real (docs/vram.md)."""
    song = QUICK_SONGS[0]
    lines = []
    for scheme, rom in (("A", rom_a), ("B", rom_b)):
        for difficulty in ("facil", "experto"):
            r = playtest.run_case(rom, "dmg", song, "guitarra", difficulty, "perfecto",
                                  out_dir(song, "perfecto", "guitarra", difficulty, "dmg", f"-{scheme}"), visual=True)
            lines.append(f"{scheme} {difficulty}: max={r.visual_max:.2f} px medio={r.visual_mean:.2f} px muestras={r.visual_samples}")
            assert r.visual_max <= (1.5 if scheme == "B" else 4.5) + 1e-6
            if scheme == "B":
                assert r.values["hits"] == r.total_notes
    (ROOT / "build" / "colocacion-a-b.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
