"""Corredor de pruebas: carga el ROM en PyBoy (sin ventana), avanza N cuadros y toma capturas.

API de PyBoy 2.8.1 usada aquí (verificada contra el código instalado, no de memoria):
  PyBoy(rom, window="null", cgb=True|False, symbols=ruta.sym), pb.tick(n, render), pb.screen.image (PIL),
  pb.memory[dirección] (también por bancos: pb.memory[banco, dirección]), pb.button(nombre), pb.stop().
`cgb=True` fuerza el modo Game Boy Color; `cgb=False` fuerza DMG aunque el header sea compatible con CGB.
"""

from __future__ import annotations

import io
from pathlib import Path

from pyboy import PyBoy

MODES = {"dmg": False, "cgb": True}


class Runner:
    """Un ROM corriendo en el emulador, en modo "dmg" o "cgb"."""

    def __init__(self, rom: Path, mode: str = "dmg", sym: Path | None = None, ram: "io.BytesIO | None" = None):
        if mode not in MODES:
            raise ValueError(f"modo desconocido {mode!r}: usa 'dmg' o 'cgb'")
        self.mode = mode
        self.symbols = parse_sym(sym) if sym else {}
        # La SRAM con batería: siempre un BytesIO (vacío = RAM nueva), así nunca se lee un .ram viejo junto al ROM
        self.ram = ram if ram is not None else io.BytesIO(bytes(8192))
        self.ram.seek(0)
        self.pb = PyBoy(str(rom), window="null", cgb=MODES[mode], sound_emulated=False, log_level="ERROR", ram_file=self.ram)
        self.pb.set_emulation_speed(0)  # sin límite de velocidad

    def tick(self, frames: int = 1, render: bool = True) -> None:
        self.pb.tick(frames, render)

    def boot(self, max_frames: int = 600) -> int:
        """Espera a que termine el arranque. PyBoy sin `bootrom=` corre la animación real del logo de la
        consola (más de 1 s en DMG y unos 3 s en CGB), así que los primeros cuadros no son del juego.
        Con símbolos, espera a que la ISR de VBlank del juego haya contado un cuadro (hFrame > 0).
        Devuelve los cuadros esperados."""
        waited = 0
        while waited < max_frames:
            self.pb.tick(1, False)
            waited += 1
            if "hFrame" in self.symbols and any(self.read("hFrame", 2)):
                return waited
        if "hFrame" in self.symbols:
            raise TimeoutError(f"el juego no arrancó en {max_frames} cuadros")
        return waited

    def read(self, name_or_addr: str | int, length: int = 1) -> bytes:
        addr = self.symbols[name_or_addr] if isinstance(name_or_addr, str) else name_or_addr
        return bytes(self.pb.memory[addr + i] for i in range(length))

    def screenshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pb.screen.image.save(path)

    def close(self) -> None:
        self.ram = io.BytesIO()   # (se guarda en un BytesIO nuevo; `save_ram` lo devuelve)
        self.pb.stop(save=True, ram_file=self.ram)

    def __enter__(self) -> "Runner":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def parse_sym(path: Path) -> dict[str, int]:
    """Lee el .sym de rgblink (líneas `BB:AAAA nombre`) y devuelve {nombre: dirección} sin el banco."""
    symbols = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        place, _, name = line.partition(" ")
        symbols[name.strip()] = int(place.split(":")[1], 16)
    return symbols


def smoke(rom: Path, out: Path, frames: int = 120) -> None:
    """Prueba de humo: corre el ROM en DMG y CGB, deja una captura de cada modo en `out`."""
    sym = rom.with_suffix(".sym")
    for mode in MODES:
        with Runner(rom, mode, sym if sym.exists() else None) as r:
            r.boot()
            r.tick(frames)
            r.screenshot(out / f"{rom.stem}-{mode}.png")
            print(f"{mode}: {frames} cuadros, captura en {out / f'{rom.stem}-{mode}.png'}")
