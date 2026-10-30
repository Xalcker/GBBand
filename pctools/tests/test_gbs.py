"""Pruebas del SM83 (`sm83.py`) y del importador de GBS.

El SM83 se compara contra el CPU de PyBoy: se arma una ROM que prueba cada opcode con registros, banderas y memoria al
azar y guarda el resultado en la WRAM; las dos máquinas deben dejar la WRAM y la HRAM idénticas.
"""

import random
from pathlib import Path

import pytest

from gbband_tools import gbapu, gbs
from gbband_tools.sm83 import SM83, UNDEFINED

LOGO = bytes.fromhex("CEED6666CC0D000B03730083000C000D0008111F8889000EDCCC6EE6DDDDD999BBBB67636E0EECCCDDDC999FBBB9333E")
CODE, TABLE = 0x150, 0x7000  # la tabla al azar se copia a $C000-$CFFF
DUMPS, CASE_SIZE = 0xD000, 12  # por caso: AF BC DE HL SP (más 2 bytes sin usar)
CASES_PER_ROM = (0xE000 - DUMPS) // CASE_SIZE
SKIPPED = {0x10, 0x76, 0xF3, 0xFB} | UNDEFINED  # STOP, HALT, DI y EI no dejan nada que comparar


def le(value: int) -> list[int]:
    return [value & 0xFF, value >> 8 & 0xFF]


def make_case(op: int, rng: random.Random, at: int, dump: int) -> list[int]:
    """El código de un caso en `at`: carga registros al azar, ejecuta el opcode y guarda los registros en `dump`."""
    pointer = lambda: rng.randrange(0xC000, 0xCE00)
    any16 = lambda: rng.randrange(0x10000)
    af, bc, de, hl = any16(), any16(), any16(), any16()
    sp = rng.randrange(0xCE10, 0xCFF0)
    x, y, z = op >> 6 & 3, op >> 3 & 7, op & 7
    body: list[int]
    control = None  # "jr", "jp" (también CALL), "ret" o "hl": el opcode puede saltarse un LD A,$5A
    if op >= 0x100:  # $CB xx
        cb = op & 0xFF
        body = [0xCB, cb]
        if cb & 7 == 6:
            hl = pointer()
    else:
        body = [op]
        uses_hl = (x == 1 and 6 in (y, z)) or (x == 2 and z == 6) or op in (0x34, 0x35, 0x36, 0x22, 0x32, 0x2A, 0x3A)
        if uses_hl:
            hl = pointer()
        if op in (0x02, 0x0A):
            bc = pointer()
        if op in (0x12, 0x1A):
            de = pointer()
        if op in (0xE0, 0xF0):
            body.append(rng.randrange(0x80, 0xFF))
        elif op in (0xE2, 0xF2):
            bc = (bc & 0xFF00) | rng.randrange(0x80, 0xFF)
        elif op in (0xEA, 0xFA, 0x08):
            body += le(pointer())
        elif (x == 0 and z == 6) or (x == 3 and z == 6) or op in (0xE8, 0xF8):
            body.append(rng.randrange(256))
        elif x == 0 and z == 1 and not y & 1:
            body += le(any16())
        elif op == 0x18 or (x == 0 and z == 0 and y >= 4):
            body.append(2)
            control = "jr"
        elif op in (0xC3, 0xCD) or (x == 3 and z in (2, 4) and y < 4):
            body += [0, 0]
            control = "jp"
        elif op in (0xC9, 0xD9) or (x == 3 and z == 0 and y < 4):
            control = "ret"
        elif op == 0xE9:
            control = "hl"
    code: list[int] = [0x31, *le(sp)]
    size_before = 3 + (4 if control == "ret" else 0) + 5 + 3 + 3 + 3
    target = at + size_before + len(body) + (2 if control else 0)
    if control == "ret":
        code += [0x21, *le(target), 0xE5]  # LD HL,destino ; PUSH HL
    if control == "jp":
        body[1:3] = le(target)
    if control == "hl":
        hl = target
    code += [0x21, *le(af), 0xE5, 0xF1]  # LD HL,af ; PUSH HL ; POP AF
    code += [0x01, *le(bc), 0x11, *le(de), 0x21, *le(hl)]
    code += body
    if control:
        code += [0x3E, 0x5A]  # LD A,$5A (lo salta el salto tomado)
    assert at + len(code) == target
    code += [0x08, *le(dump + 10), 0x31, *le(dump + 10), 0xE5, 0xD5, 0xC5, 0xF5]  # LD (nn),SP ; LD SP,nn ; PUSH x4
    return code


def conformance_rom(ops: list[int], seed: int) -> tuple[bytes, int]:
    """La ROM que prueba `ops` (un caso por opcode; $CBxx como $1xx) y la dirección del bucle final."""
    rng = random.Random(seed)
    rom = bytearray(0x8000)
    for vector in range(0, 0x40, 8):
        rom[vector] = 0xC9  # RST n: vuelve de inmediato
    rom[0x100:0x104] = bytes([0x00, 0xC3, *le(CODE)])
    rom[0x104:0x134] = LOGO
    rom[0x134:0x13C] = b"SM83TEST"
    rom[0x14D] = -sum(rom[0x134:0x14D]) - (0x14D - 0x134) & 0xFF
    rom[TABLE:TABLE + 0x1000] = bytes(rng.randrange(256) for _ in range(0x1000))
    code = [
        0xF3, 0xAF, 0xE0, 0xFF, 0x31, 0xFE, 0xFF,  # DI ; IE = 0 ; SP = $FFFE
        0x21, 0x80, 0xFF, 0x06, 0x7F, 0x22, 0x05, 0x20, 0xFC,  # HRAM en ceros
        0x21, 0x00, 0xC0, 0x01, 0x00, 0x20, 0xAF, 0x22, 0x0B, 0x78, 0xB1, 0x20, 0xF9,  # WRAM en ceros
        0x21, 0x00, 0xC0, 0x11, *le(TABLE), 0x01, 0x00, 0x10, 0x1A, 0x13, 0x22, 0x0B, 0x78, 0xB1, 0x20, 0xF8,  # tabla
    ]
    for index, op in enumerate(ops):
        code += make_case(op, rng, CODE + len(code), DUMPS + index * CASE_SIZE)
    end = CODE + len(code)
    code += [0x18, 0xFE]
    assert end < TABLE
    rom[CODE:CODE + len(code)] = bytes(code)
    return bytes(rom), end


def run_sm83(rom: bytes, end: int) -> bytes:
    mem = bytearray(0x10000)
    mem[:0x8000] = rom

    def write(addr: int, value: int) -> None:
        if addr >= 0x8000:
            mem[addr] = value

    cpu = SM83(mem.__getitem__, write)
    cpu.pc = CODE
    for _ in range(2_000_000):
        if cpu.pc == end:
            break
        cpu.step()
    assert cpu.pc == end
    return bytes(mem[0xC000:0xE000]) + bytes(mem[0xFF80:0xFFFF])


def run_pyboy(rom_path: Path, end: int) -> bytes:
    from pyboy import PyBoy

    pb = PyBoy(str(rom_path), window="null", cgb=False, sound_emulated=False, log_level="ERROR")
    try:
        for _ in range(2000):
            pb.tick(1, False)
            if pb.register_file.PC == end:
                break
        assert pb.register_file.PC == end
        return bytes(pb.memory[a] for a in range(0xC000, 0xE000)) + bytes(pb.memory[a] for a in range(0xFF80, 0xFFFF))
    finally:
        pb.stop(save=False)


def all_ops() -> list[int]:
    return [op for op in range(256) if op not in SKIPPED and op != 0xCB] + [0x100 + op for op in range(256)]


@pytest.mark.parametrize("part", range(3))
def test_sm83_igual_que_pyboy(tmp_path, part):
    ops = all_ops() * 2
    random.Random(83).shuffle(ops)
    chunk = ops[part * CASES_PER_ROM:(part + 1) * CASES_PER_ROM]
    rom, end = conformance_rom(chunk, seed=part)
    path = tmp_path / "sm83.gb"
    path.write_bytes(rom)
    ours, theirs = run_sm83(rom, end), run_pyboy(path, end)
    if ours != theirs:
        bad = []
        for index, op in enumerate(chunk):
            at = DUMPS - 0xC000 + index * CASE_SIZE
            if ours[at:at + CASE_SIZE] != theirs[at:at + CASE_SIZE]:
                name = f"CB {op & 0xFF:02X}" if op >= 0x100 else f"{op:02X}"
                bad.append(f"{name}: SM83 {ours[at + 2:at + 12].hex()} PyBoy {theirs[at + 2:at + 12].hex()}")
        first = next(i for i in range(len(ours)) if ours[i] != theirs[i])
        pytest.fail(f"difiere desde {0xC000 + first:#06x}; casos distintos:\n" + "\n".join(bad[:20]))


def test_sm83_ciclos_de_saltos():
    mem = bytearray(0x10000)
    mem[0:7] = bytes([0x20, 0x00, 0x28, 0x00, 0xC4, 0x00, 0x00])  # JR NZ (tomado) ; JR Z (no) ; CALL NZ,0 (tomado)
    cpu = SM83(mem.__getitem__, mem.__setitem__)
    assert [cpu.step(), cpu.step(), cpu.step()] == [12, 8, 24]


# ---- GBS -----------------------------------------------------------------------------------------------------------

LOAD = 0x0400


def gbs_file(tmp_path: Path, init: bytes, play: bytes, tma: int = 0, tac: int = 0, extra: bytes = b"") -> Path:
    raw = bytearray(0x70)
    raw[:4] = b"GBS\x01"
    raw[4], raw[5] = 2, 1
    raw[6:8] = LOAD.to_bytes(2, "little")
    raw[8:10] = LOAD.to_bytes(2, "little")
    raw[10:12] = (LOAD + len(init)).to_bytes(2, "little")
    raw[12:14] = (0xDFFF).to_bytes(2, "little")
    raw[14], raw[15] = tma, tac
    raw[0x10:0x14] = b"Test"
    raw[0x30:0x35] = b"Autor"
    path = tmp_path / "prueba.gbs"
    path.write_bytes(bytes(raw) + init + play + extra)
    return path


INIT = bytes([
    0xEA, 0x01, 0xC0,  # LD ($C001),A: la canción que pidieron (A al llamar a init)
    0x3E, 0x80, 0xE0, 0x11,  # NR11: duty 50 %
    0x3E, 0xF0, 0xE0, 0x12,  # NR12: volumen 15 constante
    0xAF, 0xEA, 0x00, 0xC0,  # contador en 0
    0xC9,
])
# Cada 16 llamadas, una nota nueva en CH1: x = $780 + 8 * (contador / 16 mod 8)
PLAY = bytes([
    0xFA, 0x00, 0xC0, 0x3C, 0xEA, 0x00, 0xC0,  # contador + 1
    0xE6, 0x0F, 0xC0,  # RET NZ si no es múltiplo de 16
    0xFA, 0x00, 0xC0, 0xCB, 0x37, 0xE6, 0x07, 0x87, 0x87, 0x87, 0xC6, 0x80,
    0xE0, 0x13, 0x3E, 0x87, 0xE0, 0x14,  # NR13 y disparo
    0xC9,
])


def test_gbs_nota_cada_16_llamadas(tmp_path):
    song, header = gbs.run(gbs_file(tmp_path, INIT, PLAY), 1, 4)
    assert (header.title, header.author) == ("Test", "Autor")
    frames = [n.frame for n in song.notes["Square1"]]
    assert frames[:4] == [15, 31, 47, 63]
    assert song.tracks["Square1"].freq[15] == pytest.approx(131_072 / (2048 - 0x788))  # contador 16 -> x = $788
    assert song.tracks["Square1"].duty[15] == 2


def test_gbs_init_recibe_la_cancion(tmp_path):
    machine = gbs.GbsMachine(gbs.parse_header(gbs_file(tmp_path, INIT, PLAY).read_bytes()))
    machine.cpu.call(LOAD, a=1, sentinel=gbs.SENTINEL)
    assert machine.read(0xC001) == 1


def test_gbs_al_ritmo_del_timer(tmp_path):
    # TAC = 4096 Hz, TMA = 256 - 34: 120.5 llamadas por segundo, unas dos por cuadro -> una nota cada ~8 cuadros
    song, _ = gbs.run(gbs_file(tmp_path, INIT, PLAY, tma=256 - 34, tac=0x04), 0, 4)
    frames = [n.frame for n in song.notes["Square1"]]
    assert 7 <= frames[1] - frames[0] <= 9
    assert any("timer" in line for line in song.log)


def test_gbs_bancos_y_rst(tmp_path):
    bank2 = bytes(0x8000 - (LOAD + len(INIT) + len(PLAY))) + bytes([0x42])  # el byte $42 en $4000 del banco 2
    path = gbs_file(tmp_path, INIT, PLAY, extra=bank2)
    machine = gbs.GbsMachine(gbs.parse_header(path.read_bytes()))
    assert machine.read(0x4000) == 0
    machine.write(0x2000, 2)
    assert machine.read(0x4000) == 0x42
    machine.write(0x2100, 0)  # el banco 0 se lee como el 1
    assert machine.bank == 1
    # RST $08 salta a la dirección de carga + 8
    machine.write(0xC100, 0xCF)
    machine.cpu.pc = 0xC100
    machine.cpu.step()
    assert machine.cpu.pc == LOAD + 8


def test_gbs_rechaza_lo_que_no_es_gbs(tmp_path):
    path = tmp_path / "x.gbs"
    path.write_bytes(b"NESM\x1a" + bytes(200))
    with pytest.raises(ValueError, match="GBS"):
        gbs.parse_header(path.read_bytes())


def test_m3u_de_gbs_numera_desde_0(tmp_path):
    from gbband_tools import songs

    path = gbs_file(tmp_path, INIT, PLAY)
    path.with_suffix(".m3u").write_text("# Juego GBS\nprueba.gbs::GBS,0,Intro,0:00:03,,\nprueba.gbs::GBS,1,Nivel 1,0:00:04,,\n",
                                        encoding="utf-8")
    song, title, game = gbs.load(path, songs.Options(source=str(path), name="x", track=1))
    assert (title, game) == ("Nivel 1", "Juego GBS")
    assert song.length_frames == int(4 * gbapu.CPU_HZ / gbapu.FRAME_CYCLES)


def test_importar_un_gbs_de_principio_a_fin(tmp_path):
    from gbband_tools import audio_gb as gb
    from gbband_tools import songs

    path = gbs_file(tmp_path, INIT, PLAY)
    log = songs.import_song(songs.Options(source=str(path), name="gbs_sintetica", duration=12), root=tmp_path)
    folder = tmp_path / "src" / "songs" / "gbs_sintetica"
    for name in ("song.asm", "info.json", "stream_b.bin", "chart_guitarra_experto.bin"):
        assert (folder / name).exists(), name
    on = gb.note_on_frames(gb.decode_stream((folder / "stream_b.bin").read_bytes()))[0]
    assert on[:3] == [15, 31, 47]
    assert any("TEST" in line for line in log)
