"""Pruebas de juego (fase 2): un bot toca la canción de prueba en PyBoy, en modo DMG y CGB.

Cada caso deja resultado.txt y capturas en build/test-demo-<bot>-<dificultad>-<modo>/ (el nombre de la canción
va primero, como en NESBand). Compila el ROM al empezar (build.ps1 / build.sh), así que necesitan RGBDS.
"""

from pathlib import Path

import pytest

from gbband_tools import layout, playtest

ROOT = Path(__file__).resolve().parents[2]
MODES = ("dmg", "cgb")
LATE_LIMIT = 2


def out_dir(bot: str, difficulty: str, mode: str, tag: str = "") -> Path:
    return ROOT / "build" / f"test-demo{tag}-{bot}-{difficulty}-{mode}"


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


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("difficulty", layout.DIFFICULTIES)
def test_perfecto(rom_b, mode, difficulty):
    """Acierta todo: puntaje exacto, 100 % de las notas, y cada nota del chart cae en el mismo cuadro en que el
    audio dispara la nota del CH1 (prueba de sincronía). Los otros 3 canales también suenan en su cuadro."""
    info = playtest.song_info()
    visual = difficulty in ("facil", "experto") and mode == "dmg"
    r = playtest.run_case(rom_b, mode, difficulty, "perfecto", out_dir("perfecto", difficulty, mode), visual=visual)
    v = r.values
    common_checks(r)
    assert v["hits"] == r.total_notes and v["misses"] == 0 and v["air"] == 0
    assert v["max_combo"] == r.total_notes
    assert v["score"] == playtest.expected_score(r.total_notes)
    chart = [(f, m) for f, m in info["charts"][difficulty]]
    assert playtest.sync_errors(r, chart, info["lead_in"]) == []
    for ch in range(4):
        expected = sorted(info["lead_in"] + f for f in info["note_on_audio_frames"][str(ch)])
        assert r.note_on[ch] == expected, f"canal {ch + 1}: las altas de nota no caen en los cuadros del stream"
    assert not r.muted_late and r.nr51_late == 0xFF
    if visual:
        assert r.visual_samples > 500
        assert r.visual_max <= 1.5 + 1e-6, f"error visual {r.visual_max:.2f} px"


@pytest.mark.parametrize("mode", MODES)
def test_sin_tocar(rom_b, mode):
    """No toca nada: todo se pierde y el instrumento (CH1) queda callado."""
    r = playtest.run_case(rom_b, mode, "experto", "sin-tocar", out_dir("sin-tocar", "experto", mode))
    v = r.values
    common_checks(r)
    assert v["hits"] == 0 and v["score"] == 0 and v["max_combo"] == 0
    assert v["misses"] == r.total_notes
    assert r.muted_late and r.nr51_late & 0x11 == 0, "CH1 debe estar fuera de ambos lados de NR51"
    assert r.nr51_late & 0xEE == 0xEE, "los otros canales no se callan"


@pytest.mark.parametrize("mode", MODES)
def test_machacando(rom_b, mode):
    """Machaca botones: acierta alguna nota de suerte, pero el combo nunca sube y el puntaje se queda abajo."""
    r = playtest.run_case(rom_b, mode, "experto", "machacando", out_dir("machacando", "experto", mode))
    v = r.values
    common_checks(r)
    assert v["max_combo"] <= 5
    assert playtest.stars(v["score"], r.total_notes)[1] <= 2
    assert v["air"] > 0


def test_colocacion_a_contra_b(rom_a, rom_b):
    """Mide el error visual de las dos colocaciones con el ROM real (docs/vram.md)."""
    lines = []
    for scheme, rom in (("A", rom_a), ("B", rom_b)):
        for difficulty in ("facil", "experto"):
            r = playtest.run_case(rom, "dmg", difficulty, "perfecto", out_dir("perfecto", difficulty, "dmg", f"-{scheme}"), visual=True)
            lines.append(f"{scheme} {difficulty}: max={r.visual_max:.2f} px medio={r.visual_mean:.2f} px muestras={r.visual_samples}")
            if scheme == "B":
                assert r.visual_max <= 1.5 + 1e-6
            else:
                assert r.visual_max <= 4.5 + 1e-6
            assert r.values["hits"] == r.total_notes
    (ROOT / "build" / "colocacion-a-b.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
