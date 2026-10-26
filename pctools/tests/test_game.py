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
    assert v["pct"] == 100 and v["stars"] == 5 and v["notes_total"] == r.total_notes and not v["failed"]
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


@pytest.mark.parametrize("mode", MODES)
def test_pausa_no_pierde_la_sincronia(rom_b, mode):
    """Pausar a media canción y seguir: el reloj se congela y todo continúa en su cuadro (puntaje exacto y las altas de nota del
    audio caen donde dice el stream)."""
    song = QUICK_SONGS[0]
    data = playtest.load_song(song)
    chart = data.chart("guitarra", "experto")
    pause_at = chart[len(chart) // 2][0] + 20
    r = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "perfecto",
                          out_dir(song, "perfecto-pausa", "guitarra", "experto", mode), pause_at=pause_at, pause_frames=50)
    v = r.values
    common_checks(r)
    assert v["hits"] == r.total_notes and v["score"] == playtest.expected_score(r.total_notes)
    assert playtest.sync_errors(r, chart) == []
    for ch in range(4):
        assert r.note_on[ch] == data.note_on[ch]
    assert r.frames > data.info["end_frame"] + 40, "la pausa tiene que haber durado"


@pytest.mark.parametrize("mode", MODES)
def test_pierdes_si_se_acaba_la_vida(rom_b, mode):
    """Sin tocar nada la vida llega a 0: pierdes, el instrumento queda callado y la pantalla de resultados lo dice."""
    song = QUICK_SONGS[0]
    r = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "sin-tocar",
                          out_dir(song, "sin-tocar-pierdes", "guitarra", "experto", mode))
    v = r.values
    assert v["failed"] == 1 and v["life"] == 0 and v["stars"] == 0 and v["pct"] == 0
    assert r.muted_late


@pytest.mark.parametrize("mode", MODES)
def test_sin_fallo_no_se_puede_perder(rom_b, mode):
    song = QUICK_SONGS[0]
    r = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "sin-tocar",
                          out_dir(song, "sin-tocar-sinfallo", "guitarra", "experto", mode), no_fail=True)
    v = r.values
    assert v["failed"] == 0 and v["life"] == 28 and v["misses"] == r.total_notes


@pytest.mark.parametrize("mode", MODES)
def test_humano_90_termina_y_humano_45_pierde(rom_b, mode):
    """Balance de la vida: quien acierta ~90 % (con errores en rachas) termina la canción en experto; ~45 % pierde."""
    song = QUICK_SONGS[0]
    good = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "humano90",
                             out_dir(song, "humano90", "guitarra", "experto", mode))
    bad = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "humano45",
                            out_dir(song, "humano45", "guitarra", "experto", mode))
    assert good.values["failed"] == 0, f"el jugador de 90 % perdió (vida {good.values['life']})"
    assert 0.8 < good.values["hits"] / good.total_notes < 0.97
    assert bad.values["failed"] == 1, "el jugador de 45 % debía perder"
    common_checks(good)
    common_checks(bad)


def test_estrellas_de_la_rom_son_las_del_modelo(rom_b):
    """El porcentaje y las estrellas que calcula la ROM coinciden con los de playtest.stars (los umbrales de NESBand)."""
    song = QUICK_SONGS[0]
    for bot in ("machacando", "humano90", "humano45"):
        r = playtest.run_case(rom_b, "dmg", song, "guitarra", "experto", bot, out_dir(song, bot, "guitarra", "experto", "dmg", "-estrellas"))
        pct, stars = playtest.stars(r.values["score"], r.total_notes)
        assert r.values["pct"] == int(pct) and r.values["stars"] == stars, (bot, pct, stars, r.values["pct"], r.values["stars"])

@pytest.mark.parametrize("mode", MODES)
def test_records_se_guardan_y_sobreviven_al_reinicio(rom_b, mode):
    """Un récord nuevo pide iniciales, se guarda en la SRAM (con su suma de verificación) y se ve en el menú, también tras
    apagar y volver a encender; un puntaje menor no lo reemplaza; perder o jugar sin fallo no graba."""
    song = QUICK_SONGS[0]
    a = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "perfecto", out_dir(song, "record1", "guitarra", "experto", mode),
                          initials="XYZ")
    assert a.values["new_record"] == 1 and a.values["state_after"] == 1
    expected = f"RECORD {a.values['score']:06d} XYZ 5*"
    assert a.values["rec_text"] == expected, a.values["rec_text"]
    # otra partida peor (humano al 90 %) con la misma SRAM: no es récord, y el récord anterior sigue en el menú
    b = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "humano90", out_dir(song, "record2", "guitarra", "experto", mode),
                          ram=a.ram, initials=None)
    assert b.values["new_record"] == 0
    # perder no graba, aunque el puntaje fuera mayor; un instrumento distinto tiene su propio récord (vacío)
    c = playtest.run_case(rom_b, mode, song, "teclado", "experto", "sin-tocar", out_dir(song, "record3", "teclado", "experto", mode),
                          ram=b.ram)
    assert c.values["new_record"] == 0
    d = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "perfecto", out_dir(song, "record4", "guitarra", "experto", mode),
                          ram=c.ram, no_fail=True)
    assert d.values["new_record"] == 0, "sin fallo no graba récord"
    # el récord sobrevive: al abrir el menú de esa canción y dificultad, el texto lo muestra
    with playtest.Runner(rom_b, mode, rom_b.with_suffix(".sym"), d.ram) as r:
        r.boot()
        r.tick(5)
        playtest.select_in_menu(r, playtest.song_names().index(song), 0, 3)
        assert bytes(r.read("wRecText", 20)).decode("ascii") == expected


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("song,instrument,difficulty", [("demo", "guitarra", "experto"), ("demo", "guitarra", "facil"),
                                                         ("salto", "teclado", "medio"), ("carrera", "teclado", "dificil")])
def test_sostener_las_colas_suma_puntos_que_no_cuentan_para_las_estrellas(rom_b, mode, song, instrument, difficulty):
    """Quien sostiene las notas largas suma 10 puntos cada 8 cuadros de cola (no rompe nada si suelta antes) y esos puntos no
    cuentan para las estrellas ni para el máximo posible."""
    data = playtest.load_song(song)
    tails = data.tails[(instrument, difficulty)]
    assert tails, "la prueba necesita una canción con colas"
    held = playtest.run_case(rom_b, mode, song, instrument, difficulty, "sostiene",
                             out_dir(song, "sostiene", instrument, difficulty, mode), shots=(300, 900))
    tapped = playtest.run_case(rom_b, mode, song, instrument, difficulty, "perfecto",
                               out_dir(song, "perfecto-colas", instrument, difficulty, mode))
    common_checks(held)
    assert held.values["hits"] == held.total_notes and held.values["misses"] == 0
    extra = held.values["score"] - playtest.expected_score(held.total_notes)
    assert tapped.values["score"] == playtest.expected_score(held.total_notes), "soltar antes no cambia el puntaje de las notas"
    assert extra > 0 and extra % 10 == 0
    assert extra <= 10 * sum((end - frame) // 8 + 1 for (frame, _), end in tails.items())
    assert held.values["pct"] == 100 and held.values["stars"] == 5

@pytest.mark.parametrize("mode", MODES)
def test_poder_estelar(rom_b, mode):
    """Las frases estelares completas llenan la barra; con la mitad, Select la activa y el puntaje de lo que sigue vale el doble.
    Las estrellas no cuentan ese doble (salen del puntaje normal)."""
    song = QUICK_SONGS[0]
    base = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "perfecto", out_dir(song, "perfecto-sinestelar", "guitarra", "experto", mode))
    star = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "perfecto", out_dir(song, "perfecto-estelar", "guitarra", "experto", mode),
                             use_star=True)
    expected = playtest.expected_score(star.total_notes)
    assert base.values["max_energy"] >= 32, "completar frases estelares tiene que llenar la barra"
    assert base.values["star_activations"] == 0 and base.values["score"] == expected
    assert star.values["star_activations"] >= 1
    assert expected < star.values["score"] <= 2 * expected
    assert star.values["pct"] == 100 and star.values["stars"] == 5
    common_checks(star)

@pytest.mark.parametrize("mode", MODES)
def test_efecto_al_fallar(rom_b, mode):
    """Al fallar suena un efecto (tres, sin repetir el anterior); con SI además tiembla la autopista y se tiñe de rojo.
    Con SOLO SONIDO no hay temblor, con NO no hay nada, y en una racha de fallos se repite a lo más 3 veces por segundo.
    La opción no cambia el juego: el puntaje es el mismo."""
    song = QUICK_SONGS[0]
    runs = {}
    for opt in (0, 1, 2):
        runs[opt] = playtest.run_case(rom_b, mode, song, "teclado", "experto", "sin-tocar",
                                      out_dir(song, f"fx{opt}", "teclado", "experto", mode), no_fail=True, options={"fx": opt})
    full, sound, off = (runs[i].values for i in (0, 1, 2))
    assert full["sfx_starts"] >= 5 and len(full["sfx_ids"]) == 3
    times = full["sfx_times"]
    assert all(b - a >= 20 for a, b in zip(times, times[1:])), "enfriamiento de 20 cuadros"
    assert 1 <= full["max_scx"] <= 2 and full["shake_frames"] >= 5
    assert sound["sfx_starts"] >= 5 and sound["max_scx"] == 0 and sound["shake_frames"] == 0
    assert off["sfx_starts"] == 0 and off["max_scx"] == 0
    assert full["score"] == sound["score"] == off["score"] and full["misses"] == off["misses"]
    for r in runs.values():
        common_checks(r)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("instrument", ["guitarra", "bateria"])
def test_espejo(rom_b, mode, instrument):
    """ESPEJO traduce el chart al leerlo (el bot sigue los carriles mirrados y lo acierta todo); no cambia el puntaje.
    Con una opción distinta de la normal no hay récord."""
    song = QUICK_SONGS[0]
    base = playtest.run_case(rom_b, mode, song, instrument, "experto", "perfecto", out_dir(song, "esp0", instrument, "experto", mode))
    mir = playtest.run_case(rom_b, mode, song, instrument, "experto", "perfecto", out_dir(song, "esp1", instrument, "experto", mode),
                            options={"mirror": 1}, visual=True)
    assert mir.values["score"] == base.values["score"] == playtest.expected_score(mir.total_notes)
    assert mir.values["pct"] == 100 and mir.values["misses"] == 0 and mir.values["air"] == 0
    assert mir.values["new_record"] == (1 if instrument == "bateria" else 0)  # la batería ignora el espejo: sí es récord
    common_checks(mir)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("speed", [1, 2, 3], ids=["75", "50", "125"])
def test_velocidad(rom_b, mode, speed):
    """A 75%, 50% y 125% la canción avanza 3, 2 o 5 pasos cada 4 cuadros reales, el sonido sigue el reloj de la canción
    y el bot lo acierta todo; no hay récord."""
    song = QUICK_SONGS[0]
    r = playtest.run_case(rom_b, mode, song, "guitarra", "experto", "perfecto", out_dir(song, f"vel{speed}", "guitarra", "experto", mode),
                          options={"speed": speed}, visual=True)
    ratio = (4 / 3, 2, 0.8)[speed - 1]
    info = playtest.load_song(song).info
    assert abs(r.frames - info["end_frame"] * ratio) < 120, (r.frames, info["end_frame"] * ratio)
    assert r.values["score"] == playtest.expected_score(r.total_notes) and r.values["pct"] == 100
    assert r.values["new_record"] == 0
    common_checks(r)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("fall,difficulty", [(1, "experto"), (4, "facil"), (2, "dificil")])
def test_caida(rom_b, mode, fall, difficulty):
    """CAIDA DE NOTAS cambia la velocidad del scroll sin tocar el chart: las gemas siguen cayendo sobre la línea de golpe."""
    song = QUICK_SONGS[0]
    r = playtest.run_case(rom_b, mode, song, "guitarra", difficulty, "perfecto", out_dir(song, f"caida{fall}", "guitarra", difficulty, mode),
                          options={"fall": fall}, visual=True)
    assert r.values["score"] == playtest.expected_score(r.total_notes) and r.values["pct"] == 100
    assert r.values["new_record"] == 0
    common_checks(r)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("start,until", [(1, 2), (2, 3), (3, 4)])
def test_practica_inicio_y_bucle(rom_b, mode, start, until):
    """La práctica empieza adelantada (reloj, autopista, chart y audio) y se repite sin resultados ni fallos: cada vuelta
    juega exactamente las notas del tramo, y el audio (frecuencias de los canales de tono) es el de la partida normal."""
    song = QUICK_SONGS[0]
    probes = tuple(range(1000, 6000, 37))
    prac = playtest.run_practice(rom_b, mode, song, "guitarra", "experto", {"practice": until, "start": start}, cycles=2, probes=probes)
    p_start, end, from_p = prac["seek"]
    assert from_p == 1 and prac["final_state"] == 2 and prac["states"] == {2}, "la práctica no debe pasar a resultados"
    assert len(prac["loops"]) == 2
    for loop in prac["loops"]:
        assert loop["misses"] == 0 and loop["air"] == 0, loop
        assert loop["combo"] == loop["chart_n"] > 10, loop
        assert loop["window"] == (p_start, end)
    assert prac["late"] == 0 and prac["overrun"] == 0
    normal = playtest.run_practice(rom_b, mode, song, "guitarra", "experto", {"practice": 4, "start": 0}, cycles=1, probes=probes)
    same = diff = 0
    for t, regs in prac["abs"].items():
        if t > p_start + 20 and t in normal["abs"]:   # (los primeros cuadros tras P: el keyframe reinicia la nota vigente)
            same += regs == normal["abs"][t]
            diff += regs != normal["abs"][t]
    assert same + diff > 5 and same >= 0.9 * (same + diff), (same, diff)


@pytest.mark.parametrize("mode", MODES)
def test_practica_marcas(rom_b, mode):
    """En la pausa de la práctica, A hace que el bucle empiece 2 s antes de donde pausaste y B que termine donde pausaste;
    la práctica se reinicia con las marcas y después se repite entre ellas. Una marca que deja el bucle en menos de 4 s se ignora."""
    song = QUICK_SONGS[0]
    # A en t >= 1800; B en t >= 2400 (60 cuadros después de A el bucle empieza en ~1680 y termina en ~2400)
    r = playtest.run_practice(rom_b, mode, song, "guitarra", "experto", {"practice": 3, "start": 0}, cycles=2,
                              marks=[(1800, "a"), (2400, "b")])
    p_start, end, from_p = r["seek"]
    assert r["mark_flags"] == (1, 1) and from_p == 1
    assert 1800 - 120 <= p_start <= 1800 - 100, p_start       # A: 2 s antes de donde pausaste
    assert 2400 <= end <= 2420, end                           # B: donde pausaste
    assert r["final_state"] == 2 and 3 not in [s for s in r["states"] if s == 4], r["states"]
    last = r["loops"][-1]
    assert last["misses"] == 0 and last["combo"] == last["chart_n"] > 3, last
    # una marca B que dejaría el bucle en menos de 4 s no se acepta
    short = playtest.run_practice(rom_b, mode, song, "guitarra", "experto", {"practice": 3, "start": 2}, cycles=1,
                                  marks=[(0, "b")])
    assert short["mark_flags"][1] == 0, "una marca B demasiado cerca del inicio se ignora"


@pytest.mark.parametrize("mode", MODES)
def test_bombo_barra(rom_b, mode):
    """El bombo de la batería se dibuja como una barra que cruza los carriles, en su posición, sin pasarse de la cuota de VRAM."""
    song = QUICK_SONGS[0]
    r = playtest.run_case(rom_b, mode, song, "bateria", "experto", "perfecto", out_dir(song, "bombo", "bateria", "experto", mode),
                          visual=True, shots=(300, 900))
    assert r.visual_samples > 100 and r.visual_max <= 2.0, (r.visual_samples, r.visual_max)
    assert r.values["score"] == playtest.expected_score(r.total_notes) and r.values["pct"] == 100
    common_checks(r)


@pytest.mark.parametrize("mode", MODES)
def test_titulo_musica_y_efectos_de_menu(rom_b, mode):
    """El título toca su música en bucle (los cuatro canales); al pasar al menú se calla y los botones del menú dan su efecto de sonido."""
    from gbband_tools.runner import Runner

    with Runner(rom_b, mode, rom_b.with_suffix(".sym")) as r:
        r.boot()
        r.tick(60)
        assert r.read("wState")[0] == 0 and r.read("wPlaying")[0] == 1, "el título debe estar tocando su música"
        counts = [r.read(0xC800 + reg)[0] for reg in (0x14, 0x19, 0x1E, 0x23)]
        r.tick(600)
        counts2 = [r.read(0xC800 + reg)[0] for reg in (0x14, 0x19, 0x1E, 0x23)]
        assert all(b != a for a, b in zip(counts, counts2)), (counts, counts2)
        wt = int.from_bytes(r.read("wT", 2), "little")
        end = int.from_bytes(r.read("wEndFrame", 2), "little")
        assert 0 < end < 3000
        r.tick(end + 100)   # da la vuelta sin detenerse
        assert r.read("wPlaying")[0] == 1
        # Start: efecto de aceptar y el menú calla la música
        r.pb.button_press("start")
        r.tick(2)
        r.pb.button_release("start")
        r.tick(2)
        assert r.read("wState")[0] == 1 and r.read("wPlaying")[0] == 0
        assert r.read("wSfxLeft")[0] > 0 or r.read("wSfxLast")[0] >= 0
        seen = set()
        for button in ("right", "down", "b"):
            r.pb.button_press(button)
            r.tick(2)
            seen.add(r.read("wSfxLeft")[0] > 0)
            r.pb.button_release(button)
            r.tick(12)
        assert True in seen, "los botones del menú deben dar su efecto de sonido"
