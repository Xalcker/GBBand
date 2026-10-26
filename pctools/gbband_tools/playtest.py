"""Pruebas de juego: un bot toca la canción en el emulador (PyBoy, sin ventana) y se revisa lo que quedó en WRAM.

    run_case(rom, mode, difficulty, bot, out)  ->  resultado.txt y capturas en `out`

Los bots reciben el chart y deciden en qué cuadro apretar cada carril. Todo se mide en cuadros del juego: antes
de cada tick se mira `wT` (las ISR de VBlank que ya corrieron); un botón apretado en ese momento lo lee la ISR
del cuadro `wT`, que es el que juzga el juego.

Prueba de sincronía: cada nota del chart debe caer en el mismo cuadro en que el audio dispara la nota del CH1
(contador `wNoteOn` de la ISR: se compara cuadro por cuadro con lo que sabe el generador, notes.json).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pyboy.utils import WindowEvent

from . import layout
from .runner import Runner

ROOT = Path(__file__).resolve().parents[2]
SONGS_DIR = ROOT / "src" / "songs"
TITLE_SONG = "titulo"   # la música del título: va en su propio slot, fuera de la lista del menú
# Carriles: verde = izquierda, rojo = abajo, amarillo = derecha, azul = B, naranja = A.
# Desde un hook los eventos se mandan con retraso 1: `button_press` agregaría el evento a una lista que PyBoy
# vacía al final del tick (se perdería). Con retraso 1 lo lee la ISR de VBlank siguiente a la del hook.
PRESS = (WindowEvent.PRESS_ARROW_LEFT, WindowEvent.PRESS_ARROW_DOWN, WindowEvent.PRESS_ARROW_RIGHT,
         WindowEvent.PRESS_BUTTON_B, WindowEvent.PRESS_BUTTON_A)
RELEASE = (WindowEvent.RELEASE_ARROW_LEFT, WindowEvent.RELEASE_ARROW_DOWN, WindowEvent.RELEASE_ARROW_RIGHT,
           WindowEvent.RELEASE_BUTTON_B, WindowEvent.RELEASE_BUTTON_A)
HOLD_FRAMES = 3
STATE_PLAY = 2
STATE_PAUSE = 3
STATE_END = 4  # la pantalla de resultados
INSTRUMENTS = ("guitarra", "teclado", "bajo", "bateria")  # canal del APU de cada uno: CH1, CH2, CH3, CH4
LANE_MASK = 0x1F


def song_names() -> list[str]:
    """Las canciones de la ROM, en el orden de su lista (alfabético, como `gbband list-songs`)."""
    return sorted(p.parent.name for p in SONGS_DIR.glob("*/song.asm") if p.parent.name != TITLE_SONG)


@dataclass
class SongData:
    """Lo que las pruebas saben de una canción, leído de los archivos que generó el importador."""

    name: str
    info: dict
    charts: dict  # (instrumento, dificultad) -> [(cuadro, máscara de carriles)], sin las entradas de fin de cola
    tails: dict  # (instrumento, dificultad) -> {(cuadro, carril): cuadro en que termina su cola}
    note_on: dict  # canal 0-3 -> cuadros de la canción (con el lead-in) en que el stream dispara una nota

    def chart(self, instrument: str, difficulty: str) -> list[tuple[int, int]]:
        return self.charts[(instrument, difficulty)]


def load_song(name: str) -> SongData:
    from . import audio_gb as gb
    from .chartedit import entries_to_chart, parse_chart_bytes

    folder = SONGS_DIR / name
    info = json.loads((folder / "info.json").read_text(encoding="utf-8"))
    charts = {}
    tails = {}
    for path in folder.glob("chart_*.bin"):
        _, instrument, difficulty = path.stem.split("_")
        notes = entries_to_chart(parse_chart_bytes(path.read_bytes()), instrument == "bateria")
        charts[(instrument, difficulty)] = [(n.frame, n.mask & LANE_MASK) for n in notes]
        tails[(instrument, difficulty)] = {(n.frame, lane): n.end for n in notes if n.end and instrument != "bateria"
                                           for lane in lanes_of(n.mask)}
    stream = (folder / "stream_b.bin").read_bytes() + (folder / "stream_c.bin").read_bytes()
    on = gb.note_on_frames(gb.decode_stream(stream))
    return SongData(name, info, charts, tails, {ch: [info["lead_in"] + f for f in frames] for ch, frames in on.items()})


def select_in_menu(r: Runner, song: int, instrument: int, difficulty: int, no_fail: bool = False) -> None:
    """Sale del título y elige canción, instrumento, dificultad y fallo con los botones, como un jugador (y comprueba lo elegido)."""
    wait = lambda: r.tick(3)

    def tap(button: str) -> None:
        r.pb.button_press(button)
        r.tick(2)
        r.pb.button_release(button)
        r.tick(2)

    value = lambda name: r.read(name)[0]
    tap("start")  # el título
    assert value("wState") == 1, "el título no pasó al menú"
    for _ in range(40):
        if value("wSong") == song:
            break
        tap("right")
    assert value("wSong") == song, "no pude elegir la canción en el menú"
    tap("down")
    for _ in range(5):
        if value("wInstrument") == instrument:
            break
        tap("right")
    assert value("wInstrument") == instrument, "esa canción no tiene ese instrumento"
    tap("down")
    for _ in range(8):
        d = value("wDifficulty")
        if d == difficulty:
            break
        tap("right" if d < difficulty else "left")
    assert value("wDifficulty") == difficulty
    if no_fail:
        tap("down")
        tap("right")
        assert value("wNoFail") == 1
    wait()

OPTION_ROWS = {"mirror": 0, "speed": 1, "fall": 2, "practice": 3, "start": 4, "fx": 5}


def set_options(r: Runner, options: dict[str, int]) -> None:
    """Select abre la pantalla de opciones; con ↓ y ←/→ se pone cada valor, y B vuelve al menú (como un jugador)."""
    def tap(button: str) -> None:
        r.pb.button_press(button)
        r.tick(2)
        r.pb.button_release(button)
        r.tick(2)

    tap("select")
    assert r.read("wState")[0] == 6, "Select no abrió las opciones"
    r.tick(3)
    row = 0
    for name, value in sorted(options.items(), key=lambda kv: OPTION_ROWS[kv[0]]):
        while row < OPTION_ROWS[name]:
            tap("down")
            row += 1
        for _ in range(8):
            have = r.read("wOpt", 6)[OPTION_ROWS[name]]
            if have == value:
                break
            tap("right" if have < value else "left")
        assert r.read("wOpt", 6)[OPTION_ROWS[name]] == value, f"no pude poner {name}={value}"
    r.tick(3)
    tap("b")
    assert r.read("wState")[0] == 1, "B no volvió al menú"
    r.tick(3)


def mirror_chart(chart):
    """El chart como se ve con ESPEJO: verde <-> naranja y rojo <-> azul."""
    def flip(mask: int) -> int:
        return sum(1 << (4 - lane) for lane in range(5) if mask >> lane & 1)
    return [(frame, flip(mask)) for frame, mask in chart]


def expected_score(total_notes: int) -> int:
    """Puntaje de acertar `total_notes` notas seguidas: la nota i vale 50 por su multiplicador
    (1 con 0-9 de combo, 2 con 10-19, 3 con 20-29, 4 con 30 o más; el combo ya incluye la nota)."""
    return sum(50 * min(4, i // 10 + 1) for i in range(1, total_notes + 1))


STAR_THRESHOLDS = (20, 40, 60, 80, 95)  # % del puntaje máximo para 1 a 5 estrellas (igual que NESBand)


def stars(score: int, total_notes: int) -> tuple[float, int]:
    """(porcentaje del puntaje máximo, estrellas). Las estrellas salen del puntaje, no de las notas acertadas."""
    pct = 100 * score / expected_score(total_notes)
    return pct, sum(pct >= t for t in STAR_THRESHOLDS)


def lanes_of(mask: int) -> list[int]:
    return [b for b in range(5) if mask >> b & 1]


def build_rom(placement: str = "B", name: str = "") -> Path:
    """Compila el ROM con el script de build de este sistema. Devuelve la ruta del .gb."""
    base = f"gbband-{name}" if name else "gbband"
    if sys.platform == "win32":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "build.ps1"), "-Colocacion", placement]
        if name:
            cmd += ["-Nombre", name]
        env = None
    else:
        import os

        cmd = ["bash", str(ROOT / "build.sh")]
        env = dict(os.environ, COLOCACION=placement, NOMBRE=name)
    subprocess.run(cmd, check=True, cwd=ROOT, env=env, capture_output=True)
    return ROOT / "build" / f"{base}.gb"


# ---------------------------------------------------------------------------- bots

class Bot:
    """Decide, para el cuadro `t`, qué carriles se aprietan (los demás se sueltan tras HOLD_FRAMES)."""

    name = "bot"

    def __init__(self, chart: list[tuple[int, int]], seed: int = 1):
        self.chart = chart
        self.rng = random.Random(seed)

    def presses(self, t: int) -> list[int]:
        return []

    def release_at(self, t: int, lane: int) -> int:
        return t + HOLD_FRAMES


class PerfectBot(Bot):
    name = "perfecto"

    def __init__(self, chart, seed=1):
        super().__init__(chart, seed)
        self.plan: dict[int, list[int]] = {}
        for frame, mask in chart:
            self.plan.setdefault(frame, []).extend(lanes_of(mask))

    def presses(self, t):
        return self.plan.get(t, [])


class HoldBot(PerfectBot):
    """Perfecto que además sostiene las notas con cola hasta donde terminan."""

    name = "sostiene"
    tails: dict = {}

    def release_at(self, t, lane):
        return self.tails.get((t, lane), t + HOLD_FRAMES)


class IdleBot(Bot):
    name = "sin-tocar"


class MasherBot(Bot):
    """Machaca botones: cada 4 cuadros aprieta un grupo al azar de carriles."""

    name = "machacando"

    def presses(self, t):
        if t % 4:
            return []
        return [l for l in range(5) if self.rng.random() < 0.5]


class HumanBot(Bot):
    """Un jugador de carne y hueso: acierta una fracción de las notas con errores en rachas (de 1 a 3 notas seguidas), toca
    con hasta 3 cuadros de adelanto o atraso y de vez en cuando golpea al aire. Con semilla fija."""

    name = "humano"
    hit_rate = 0.9

    def __init__(self, chart, seed=1):
        super().__init__(chart, seed)
        self.plan: dict[int, list[int]] = {}
        miss_fraction = 1 - self.hit_rate
        start_miss = miss_fraction / (1 + self.hit_rate)  # cada racha pierde 2 notas en promedio: aciertos = (1 - q) / (1 + q)
        streak = 0
        previous = -100
        for frame, mask in chart:
            for lane in lanes_of(mask):
                if streak:
                    streak -= 1
                    continue
                if self.rng.random() < start_miss:
                    streak = self.rng.randint(0, 2)
                    continue
                when = frame + self.rng.randint(-3, 3)
                self.plan.setdefault(when, []).append(lane)
            if frame - previous > 40 and self.rng.random() < 0.03:  # un golpe al aire entre dos notas lejanas
                self.plan.setdefault(frame + 18, []).append(self.rng.randrange(5))
            previous = frame

    def presses(self, t):
        return self.plan.get(t, [])


class Human90Bot(HumanBot):
    name = "humano90"
    hit_rate = 0.9


class Human45Bot(HumanBot):
    name = "humano45"
    hit_rate = 0.45


BOTS = {"perfecto": PerfectBot, "sostiene": HoldBot, "sin-tocar": IdleBot, "machacando": MasherBot, "humano90": Human90Bot, "humano45": Human45Bot}


# ---------------------------------------------------------------------------- medición visual

BAR_TILE = 0xA6
BAR_TOP_L = {BAR_TILE + 1 + 4 * (v - 1): v for v in (1, 2, 3)}        # tile de arriba izquierda de la barra -> desplazamiento / 2
BAR_BOT_L = {BAR_TILE + 3 + 4 * (v - 1): v for v in (1, 2, 3)}


def visual_errors(r: Runner, chart: list[tuple[int, int]], s: int, t: int, scheme: str) -> list[float]:
    """Error (px, dibujada menos ideal) de cada gema visible del chart en el cuadro mostrado `t`.

    Lee el mapa del fondo de VRAM y el SCY real del hardware. Una gema del carril `l` se reconoce por su tile
    (TILE_GEM + 14 l + variante); el tile de arriba de una variante con desplazamiento k está en la fila de la gema
    y el de abajo en la siguiente. Se empareja cada nota con la gema del carril más cercana a su posición ideal."""
    scy = r.pb.memory[0xFF42]
    errors = []
    lane_gems: dict[int, list[float]] = {l: [] for l in range(5)}  # posiciones en pantalla de las gemas dibujadas
    top_idx = {0: 0, 2: 1, 3: 1, 6: 2, 7: 2, 10: 3, 11: 3}  # índice de tile de arriba -> variante
    bot_idx = {4: 1, 5: 1, 8: 2, 9: 2, 12: 3, 13: 3}
    for l in range(5):
        col = 5 + 2 * l
        for row in range(32):
            tile = r.pb.memory[0x9800 + row * 32 + col]
            k = tile - 0x60 - 14 * l
            if k in top_idx and k in (0, 2, 6, 10):  # la mitad izquierda de arriba
                bg_y = row * 8 + 2 * top_idx[k]
            elif k in bot_idx and k in (4, 8, 12):  # la mitad izquierda de abajo
                bg_y = (row - 1) * 8 + 2 * bot_idx[k]
            elif l == 4 and tile == BAR_TILE:       # el bombo (batería): barra que cruza los carriles
                bg_y = row * 8
            elif l == 4 and tile in BAR_TOP_L:
                bg_y = row * 8 + 2 * BAR_TOP_L[tile]
            elif l == 4 and tile in BAR_BOT_L:
                bg_y = (row - 1) * 8 + 2 * BAR_BOT_L[tile]
            else:
                continue
            lane_gems[l].append(float((bg_y - scy) % 256))
    for frame, mask in chart:
        for l in lanes_of(mask):
            ideal = layout.HIT_Y - (frame - t) * s / 256
            if not -4 <= ideal <= 116:
                continue
            near = [(abs((y - ideal + 128) % 256 - 128), y) for y in lane_gems[l]]
            if not near:
                errors.append(float("inf"))
                continue
            _, y = min(near)
            errors.append((y - ideal + 128) % 256 - 128)  # el fondo da la vuelta cada 256 px
    return errors


# ---------------------------------------------------------------------------- una partida

@dataclass
class Result:
    rom: str
    mode: str
    difficulty: str
    bot: str
    song: str = ""
    instrument: str = ""
    total_notes: int = 0
    frames: int = 0
    values: dict = field(default_factory=dict)
    note_on: dict = field(default_factory=dict)
    visual_max: float = 0.0
    visual_mean: float = 0.0
    visual_bias: float = 0.0
    ram: object = None
    visual_samples: int = 0
    visual_values: list = field(default_factory=list)
    max_sprites_line: int = 0
    muted_late: bool = False
    nr51_late: int = 0


NOTE_ON_REGS = (0x14, 0x19, 0x1E, 0x23)  # byte bajo de NR14, NR24, NR34 y NR44


def note_on_counts(r: Runner) -> list[int]:
    """Altas de nota por canal que contó la ISR (contadores de 8 bits por registro, en wNoteOnCnt)."""
    base = r.symbols["wNoteOnCnt"]
    return [r.read(base + reg)[0] for reg in NOTE_ON_REGS]


def digits(r: Runner, name: str, n: int) -> int:
    return int("".join(str(d) for d in r.read(name, n)))


def sprites_per_line(oam: bytes) -> int:
    lines = [0] * 256
    for i in range(0, 160, 4):
        y = oam[i]
        if 0 < y < 160 and oam[i + 1] > 0:
            for line in range(y - 16, y):
                if 0 <= line < 144:
                    lines[line] += 1
    return max(lines)


def tap(r: Runner, button: str) -> None:
    r.pb.button_press(button)
    r.tick(2)
    r.pb.button_release(button)
    r.tick(2)


def enter_initials(r: Runner, text: str) -> None:
    """En la pantalla de resultados de un récord: Start, escribe las iniciales con ↑/↓ (parte de AAA) y ←/→, y confirma con A."""
    tap(r, "start")
    assert r.read("wState")[0] == 5, "no apareció la pantalla de iniciales"
    for pos, letter in enumerate(text):
        for _ in range(ord(letter) - ord(bytes(r.read("wInitials", 3))[pos:pos + 1].decode())):
            tap(r, "up")
        if pos < 2:
            tap(r, "right")
    tap(r, "a")
    r.tick(6)


def run_case(rom: Path, mode: str, song: str, instrument: str, difficulty: str, bot_name: str, out: Path,
             visual: bool = False, shots: tuple[int, ...] = (40, 400, 1200), seed: int = 1, no_fail: bool = False,
             pause_at: int | None = None, pause_frames: int = 40, ram=None, initials: str | None = None, use_star: bool = False,
             options: dict[str, int] | None = None) -> Result:
    data = load_song(song)
    info = data.info
    chart = data.chart(instrument, difficulty)
    channel = INSTRUMENTS.index(instrument)
    s = layout.speed_8_8(difficulty)
    options = options or {}
    mirrored = bool(options.get("mirror")) and instrument != "bateria"
    tails = data.tails[(instrument, difficulty)]
    if mirrored:
        chart = mirror_chart(chart)
        tails = {(f, 4 - lane): end for (f, lane), end in tails.items()}
    bot = BOTS[bot_name](chart, seed)
    if isinstance(bot, HoldBot):
        bot.tails = tails
    result = Result(str(rom.name), mode, difficulty, bot_name, song, instrument,
                    total_notes=sum(len(lanes_of(m)) for _, m in chart))
    lead_in = info["lead_in"]
    observed_note_on: dict[int, list[int]] = {0: [], 1: [], 2: [], 3: []}
    errors: list[float] = []
    isr_hist: dict[int, int] = {}
    out.mkdir(parents=True, exist_ok=True)

    with Runner(rom, mode, rom.with_suffix(".sym"), ram) as r:
        r.boot()
        r.tick(5)
        select_in_menu(r, song_names().index(song), channel, layout.DIFFICULTIES.index(difficulty), no_fail)
        if options:
            set_options(r, options)
        assert bytes(r.read("wTitleBuf", 20)).decode("ascii").strip() == info["title"], "el menú no muestra el título de la canción"
        r.pb.button_press("start")
        r.tick(2)
        r.pb.button_release("start")
        for _ in range(30):
            r.tick(1)
            if r.read("wPlaying")[0]:
                break
        else:
            raise TimeoutError("la partida no empezó")

        real_per_step = (1, 4 / 3, 2, 0.8)[options.get("speed", 0)]
        releases: dict[int, int] = {}  # carril -> cuadro en que se suelta
        held: set[int] = set()
        state = {"prev_on": note_on_counts(r), "timeline": {}, "paused": False, "star_cool": 0, "max_energy": 0, "activations": 0, "was_active": 0, "last_t": -1,
                 "sfx_starts": 0, "sfx_prev": 0, "sfx_ids": set(), "max_scx": 0, "shake_frames": 0, "sfx_times": []}
        hframe = lambda: int.from_bytes(r.read("hFrame", 2), "little")

        def on_isr_end(_ctx) -> None:
            """Corre al final de cada ISR de VBlank: el estado es el de un cuadro completo. `wT` ya cuenta el
            cuadro que acaba de correr (n = wT - 1); aquí se decide qué botones lee la ISR del cuadro wT."""
            t = int.from_bytes(r.read("wT", 2), "little")
            n = t - 1
            now_h = hframe()
            for key in [k for k in state["timeline"] if k <= now_h]:   # Start (pausa y reanudar), en cuadros reales
                r.pb.send_input(state["timeline"].pop(key), 1)
            if pause_at is not None and not state["paused"] and r.read("wPlaying")[0] and t == pause_at:
                state["paused"] = True
                state["timeline"][now_h] = WindowEvent.PRESS_BUTTON_START
                state["timeline"][now_h + 2] = WindowEvent.RELEASE_BUTTON_START
                state["timeline"][now_h + pause_frames] = WindowEvent.PRESS_BUTTON_START
                state["timeline"][now_h + pause_frames + 2] = WindowEvent.RELEASE_BUTTON_START
            if r.read("wPlaying")[0] == 0:
                return
            energy, active = r.read("wStarEnergy")[0], r.read("wStarActive")[0]
            state["max_energy"] = max(state["max_energy"], energy)
            if active and not state["was_active"]:
                state["activations"] += 1
            state["was_active"] = active
            if use_star and not active and energy >= 32 and n >= state["star_cool"]:  # Select activa el poder estelar
                state["timeline"][now_h] = WindowEvent.PRESS_BUTTON_SELECT
                state["timeline"][now_h + 2] = WindowEvent.RELEASE_BUTTON_SELECT
                state["star_cool"] = n + 8
            sfx = r.read("wSfxLeft")[0]
            if sfx and not state["sfx_prev"]:
                state["sfx_starts"] += 1
                state["sfx_ids"].add(r.read("wSfxLast")[0])
                state["sfx_times"].append(now_h)
            state["sfx_prev"] = sfx
            scx = r.read("hScx")[0]
            state["max_scx"] = max(state["max_scx"], scx if scx < 128 else 256 - scx)
            state["shake_frames"] += 1 if r.read("wShake")[0] else 0
            cur = note_on_counts(r)
            for ch in range(4):
                if cur[ch] != state["prev_on"][ch]:
                    observed_note_on[ch] += [n] * ((cur[ch] - state["prev_on"][ch]) % 256)
            state["prev_on"] = cur
            isr = r.read("wIsrLast")[0]
            isr_hist[isr] = isr_hist.get(isr, 0) + 1
            if visual and n % 5 == 0 and lead_in - 150 < n < info["end_frame"] - 200:
                errors.extend(e for e in visual_errors(r, chart, s, n, "B") if e != float("inf"))
            if n == info["end_frame"] - 120:
                result.nr51_late = r.read("sh_NR51")[0]
                result.muted_late = bool(r.read("wMuted")[0])
                result.max_sprites_line = sprites_per_line(r.read(0xC400, 160))
            for tt in range(state["last_t"] + 1, t + 1):    # (a 125% un cuadro real puede traer dos pasos)
                for lane in bot.presses(tt):
                    if lane not in held:
                        r.pb.send_input(PRESS[lane], 1)
                        held.add(lane)
                    releases[lane] = bot.release_at(tt, lane)
            state["last_t"] = max(state["last_t"], t)
            for lane in [l for l, until in releases.items() if t >= until]:
                r.pb.send_input(RELEASE[lane], 1)
                held.discard(lane)
                del releases[lane]

        r.pb.hook_register(0, r.symbols["IsrEnd"], on_isr_end, None)
        frame_count = 0
        limit = int(info["end_frame"] * real_per_step) + 300
        shots_left = set(shots)
        while r.read("wState")[0] != STATE_END and frame_count < limit:
            r.tick(1)
            frame_count += 1
            now = int.from_bytes(r.read("wT", 2), "little")
            if now in shots_left:
                shots_left.discard(now)
                r.screenshot(out / f"t{now:04d}.png")
        for lane in list(held):
            r.pb.send_input(RELEASE[lane])
        r.tick(10)
        r.screenshot(out / "final.png")
        result.frames = frame_count
        result.note_on = observed_note_on
        v = result.values
        v["state"] = r.read("wState")[0]
        v["life"] = r.read("wLife")[0]
        v["failed"] = r.read("wFailed")[0]
        v["pct"] = r.read("wPct")[0]
        v["stars"] = r.read("wStars")[0]
        v["notes_total"] = int.from_bytes(r.read("wNotesTotal", 2), "little")
        v["new_record"] = r.read("wNewRecord")[0]
        v["sfx_starts"], v["sfx_ids"], v["max_scx"], v["shake_frames"] = state["sfx_starts"], state["sfx_ids"], state["max_scx"], state["shake_frames"]
        v["sfx_times"] = state["sfx_times"]
        v["max_energy"], v["star_activations"] = state["max_energy"], state["activations"]
        if initials:
            enter_initials(r, initials)
            v["rec_text"] = bytes(r.read("wRecText", 20)).decode("ascii")
            v["state_after"] = r.read("wState")[0]
        v["score"] = digits(r, "wScoreDigits", 6)
        v["max_combo"] = digits(r, "wMaxComboDigits", 3)
        v["combo"] = digits(r, "wComboDigits", 3)
        v["hits"] = digits(r, "wHitsDigits", 3)
        v["misses"] = digits(r, "wMissDigits", 3)
        v["air"] = r.read("wAirCount")[0]
        v["score_units"] = int.from_bytes(r.read("wScoreUnits", 2), "little")
        v["late"] = r.read("wLate")[0]
        v["underrun"] = r.read("wUnderrun")[0]
        v["vq_overflow"] = r.read("wQOverflow")[0]
        v["vq_max_bytes"] = r.read("wQMax")[0]
        v["overrun"] = r.read("wOverrun")[0]
        v["flush_lines"] = r.read("wFlushLines")[0]
        v["isr_max_m"] = r.read("wIsrMax")[0] * 64
        v["isr_hist"] = dict(sorted(isr_hist.items()))
        v["cpu_max_lines"] = r.read("wCpuMax")[0]
        cpu_frames = int.from_bytes(r.read("wCpuFrames", 2), "little")
        cpu_sum = int.from_bytes(r.read("wCpuSum", 4), "little")
        v["cpu_mean_lines"] = cpu_sum / max(cpu_frames, 1)

    result.ram = r.ram
    if errors:
        result.visual_max = max(abs(e) for e in errors)
        result.visual_mean = sum(abs(e) for e in errors) / len(errors)
        result.visual_bias = sum(errors) / len(errors)
        result.visual_samples = len(errors)
        result.visual_values = errors
    write_report(result, out)
    return result

def sync_errors(result: Result, chart: list[tuple[int, int]]) -> list[str]:
    """Notas del chart que no caen en el mismo cuadro que el alta de nota del canal de su instrumento."""
    channel = INSTRUMENTS.index(result.instrument)
    on = set(result.note_on[channel])
    return [f"nota del cuadro {f} sin alta de CH{channel + 1} en ese cuadro" for f, _ in chart if f not in on]


def write_report(result: Result, out: Path) -> None:
    v = result.values
    cpu_max_m = v["cpu_max_lines"] * 114
    cpu_mean_m = v["cpu_mean_lines"] * 114
    pct, star_count = stars(v["score"], result.total_notes)
    lines = [
        f"cancion={result.song} instrumento={result.instrument} rom={result.rom} modo={result.mode} dificultad={result.difficulty} bot={result.bot}",
        f"cuadros={result.frames} notas_chart={result.total_notes}",
        f"puntaje={v['score']} puntaje_esperado_perfecto={expected_score(result.total_notes)} porcentaje={pct:.1f} estrellas={star_count}",
        f"aciertos={v['hits']} fallos={v['misses']} golpes_al_aire={v['air']} combo_max={v['max_combo']}",
        f"pantalla de resultados: porcentaje={v['pct']} estrellas={v['stars']} fallaste={bool(v['failed'])} vida_final={v['life']}",
        f"atrasos={v['late']} underruns_audio={v['underrun']} desbordes_cola_vram={v['vq_overflow']}",
        "",
        "presupuestos (por cuadro):",
        f"  vram_bytes_max={v['vq_max_bytes']} (objetivo regular <= 96)",
        f"  vblank_lineas_usadas_hasta_terminar_la_cola_max={v['flush_lines']} de 10 (cada una = 114 M) desbordes_fuera_del_vblank={v['overrun']}",
        f"  isr_m_cycles_max={v['isr_max_m']} (VBlank ~1140; resolucion 64) distribucion(unidades de 64 M)={v['isr_hist']}",
        f"  cpu_bucle_principal_m_max={cpu_max_m} medio={cpu_mean_m:.0f} (gameplay <= 5000 + filas/HUD <= 2000; cuadro = 17556; resolucion 114)",
        f"  sprites_por_linea_max={result.max_sprites_line} (objetivo <= 8; limite del hardware 10)",
        "",
        "audio:",
        f"  altas_de_nota_por_canal={[len(result.note_on[c]) for c in range(4)]}",
        f"  nr51_cerca_del_final={result.nr51_late:#04x} instrumento_callado={result.muted_late}",
    ]
    if result.visual_samples:
        lines += [
            "",
            f"error visual de las gemas ({result.visual_samples} muestras): max={result.visual_max:.2f} px, "
            f"medio={result.visual_mean:.2f} px, sesgo={result.visual_bias:+.2f} px",
        ]
    (out / "resultado.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

SHADOW_FREQ = (0xC713, 0xC718, 0xC71D)   # sombras de NR13, NR23 y NR33


def run_practice(rom: Path, mode: str, song: str, instrument: str, difficulty: str, options: dict[str, int], cycles: int = 2,
                 marks: list[tuple[int, str]] | None = None, shots: tuple[int, ...] = (), probes: tuple[int, ...] = ()) -> dict:
    """Juega la práctica con un bot perfecto hasta que el bucle se repita `cycles` veces. Con `marks` = [(wT, "a"|"b")] pausa
    en ese cuadro y aprieta A (inicio) o B (fin). Devuelve lo que se observó en cada vuelta.
    Observa: cuadro de arranque del reloj (wT0), fin, aciertos, fallos, notas del chart dentro del bucle, estado de la ISR
    y las frecuencias de los canales de tono (sombras) en `probe_frames` de la canción, para comparar con una partida normal."""
    data = load_song(song)
    info = data.info
    chart_all = data.chart(instrument, difficulty)
    channel = INSTRUMENTS.index(instrument)
    out = {"loops": [], "states": set(), "late": 0, "overrun": 0, "freq": {}, "abs": {}, "shots": []}
    with Runner(rom, mode, rom.with_suffix(".sym")) as r:
        r.boot()
        r.tick(5)
        select_in_menu(r, song_names().index(song), channel, layout.DIFFICULTIES.index(difficulty))
        set_options(r, options)
        r.pb.button_press("start")
        r.tick(2)
        r.pb.button_release("start")
        state = {"last_t": None, "bot": None, "held": set(), "releases": {}, "loop_start": None, "prev_t": None,
                 "timeline": {}, "marks": list(marks or []), "loops": 0, "sample": None, "snap": {}}
        hframe = lambda: int.from_bytes(r.read("hFrame", 2), "little")

        def new_bot() -> None:
            p_start = int.from_bytes(r.read("wPracP", 2), "little") if r.read("wPracFromP")[0] else 0
            end = int.from_bytes(r.read("wEndFrame", 2), "little")
            chart = [(f, m) for f, m in chart_all if p_start <= f < end - 8]   # (las del último momento no alcanzan a juzgarse antes de repetir)
            state["bot"] = PerfectBot(chart, 1)
            state["window"] = (p_start, end)
            state["chart_n"] = sum(len(lanes_of(m)) for _, m in chart)
            state["last_t"] = None

        def on_isr(_ctx) -> None:
            now_h = hframe()
            for key in [k for k in state["timeline"] if k <= now_h]:
                r.pb.send_input(state["timeline"].pop(key), 1)
            out["states"].add(r.read("wState")[0])
            if not r.read("wPlaying")[0]:
                return
            t = int.from_bytes(r.read("wT", 2), "little")
            if state.get("await_restart") is not None:      # pausado para poner una marca: espera a que la práctica reinicie
                if t < state["await_restart"] - 100:
                    state["await_restart"] = None
                else:
                    return
            if state["bot"] is None or (state["prev_t"] is not None and t < state["prev_t"] - 5) or state["loop_start"] is None:
                if state["bot"] is not None and state["loop_start"] is not None:   # el bucle volvió a empezar
                    out["loops"].append({**state["snap"], "window": state["window"], "chart_n": state["chart_n"]})
                    state["loops"] += 1
                # (aquí wT ya es el de la vuelta nueva)
                new_bot()
                state["loop_start"] = t
            state["prev_t"] = t
            state["snap"] = {"combo": digits(r, "wComboDigits", 3), "misses": digits(r, "wMissDigits", 3),
                             "air": r.read("wAirCount")[0], "units": int.from_bytes(r.read("wScoreUnits", 2), "little")}
            if state["marks"] and t >= state["marks"][0][0] and not state["timeline"]:
                _, which = state["marks"].pop(0)
                btn_press = WindowEvent.PRESS_BUTTON_A if which == "a" else WindowEvent.PRESS_BUTTON_B
                btn_rel = WindowEvent.RELEASE_BUTTON_A if which == "a" else WindowEvent.RELEASE_BUTTON_B
                state["timeline"][now_h] = WindowEvent.PRESS_BUTTON_START
                state["timeline"][now_h + 2] = WindowEvent.RELEASE_BUTTON_START
                state["timeline"][now_h + 10] = btn_press
                state["timeline"][now_h + 12] = btn_rel
                state["prev_t"] = None
                state["bot"] = None
                state["loop_start"] = None
                state["await_restart"] = t
                return
            p_start, end = state["window"]
            if t in (p_start + 30, p_start + 90, p_start + 150, p_start + 400):
                out["freq"].setdefault(t, {})[state["loops"]] = tuple(r.read(n)[0] for n in SHADOW_FREQ)
            if t in probes and state["loops"] == 0:
                out["abs"][t] = tuple(r.read(n)[0] for n in SHADOW_FREQ)
            if state["last_t"] is None:
                state["last_t"] = t - 1
            for tt in range(state["last_t"] + 1, t + 1):
                for lane in state["bot"].presses(tt):
                    if lane not in state["held"]:
                        r.pb.send_input(PRESS[lane], 1)
                        state["held"].add(lane)
                    state["releases"][lane] = tt + 4
            state["last_t"] = t
            for lane in [l for l, until in state["releases"].items() if t >= until]:
                r.pb.send_input(RELEASE[lane], 1)
                state["held"].discard(lane)
                del state["releases"][lane]

        r.pb.hook_register(0, r.symbols["IsrEnd"], on_isr, None)
        guard = 0
        while state["loops"] < cycles and guard < 40000:
            r.tick(1)
            guard += 1
            if guard in shots:
                out["shots"].append(r.pb.screen.image.copy())
        out["late"] = r.read("wLate")[0]
        out["overrun"] = r.read("wOverrun")[0]
        out["final_state"] = r.read("wState")[0]
        out["frames_run"] = guard
        out["seek"] = (int.from_bytes(r.read("wPracP", 2), "little"), int.from_bytes(r.read("wEndFrame", 2), "little"),
                       r.read("wPracFromP")[0])
        out["mark_flags"] = (r.read("wMarkAOn")[0], r.read("wMarkBOn")[0])
    return out
