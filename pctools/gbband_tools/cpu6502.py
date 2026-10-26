"""Un 6502 de NES (sin modo decimal) lo bastante completo para correr el código de música de un NSF.

Solo los opcodes oficiales (151). Los ciclos son los base (sin la penalización por cruzar de página): el
importador solo los usa para no pasarse de un cuadro. El que lo use implementa `read(addr)` y `write(addr, value)`.
"""

from __future__ import annotations

# (modo, ciclos) por opcode; el modo dice cómo se calcula la dirección efectiva
IMP, ACC, IMM, ZP, ZPX, ZPY, ABS, ABX, ABY, IND, INX, INY, REL = range(13)

_OPS: dict[int, tuple[str, int, int]] = {}


def _op(code: int, name: str, mode: int, cycles: int) -> None:
    _OPS[code] = (name, mode, cycles)


for _name, _codes in {
    "ADC": (0x69, 0x65, 0x75, 0x6D, 0x7D, 0x79, 0x61, 0x71),
    "AND": (0x29, 0x25, 0x35, 0x2D, 0x3D, 0x39, 0x21, 0x31),
    "CMP": (0xC9, 0xC5, 0xD5, 0xCD, 0xDD, 0xD9, 0xC1, 0xD1),
    "EOR": (0x49, 0x45, 0x55, 0x4D, 0x5D, 0x59, 0x41, 0x51),
    "LDA": (0xA9, 0xA5, 0xB5, 0xAD, 0xBD, 0xB9, 0xA1, 0xB1),
    "ORA": (0x09, 0x05, 0x15, 0x0D, 0x1D, 0x19, 0x01, 0x11),
    "SBC": (0xE9, 0xE5, 0xF5, 0xED, 0xFD, 0xF9, 0xE1, 0xF1),
}.items():
    for _code, _mode, _cycles in zip(_codes, (IMM, ZP, ZPX, ABS, ABX, ABY, INX, INY), (2, 3, 4, 4, 4, 4, 6, 5)):
        _op(_code, _name, _mode, _cycles)
for _code, _mode, _cycles in zip((0x85, 0x95, 0x8D, 0x9D, 0x99, 0x81, 0x91), (ZP, ZPX, ABS, ABX, ABY, INX, INY), (3, 4, 4, 5, 5, 6, 6)):
    _op(_code, "STA", _mode, _cycles)
for _name, _codes in {
    "ASL": (0x0A, 0x06, 0x16, 0x0E, 0x1E), "LSR": (0x4A, 0x46, 0x56, 0x4E, 0x5E),
    "ROL": (0x2A, 0x26, 0x36, 0x2E, 0x3E), "ROR": (0x6A, 0x66, 0x76, 0x6E, 0x7E),
}.items():
    for _code, _mode, _cycles in zip(_codes, (ACC, ZP, ZPX, ABS, ABX), (2, 5, 6, 6, 7)):
        _op(_code, _name, _mode, _cycles)
for _name, _codes in {"DEC": (0xC6, 0xD6, 0xCE, 0xDE), "INC": (0xE6, 0xF6, 0xEE, 0xFE)}.items():
    for _code, _mode, _cycles in zip(_codes, (ZP, ZPX, ABS, ABX), (5, 6, 6, 7)):
        _op(_code, _name, _mode, _cycles)
for _code, _mode, _cycles in zip((0xA2, 0xA6, 0xB6, 0xAE, 0xBE), (IMM, ZP, ZPY, ABS, ABY), (2, 3, 4, 4, 4)):
    _op(_code, "LDX", _mode, _cycles)
for _code, _mode, _cycles in zip((0xA0, 0xA4, 0xB4, 0xAC, 0xBC), (IMM, ZP, ZPX, ABS, ABX), (2, 3, 4, 4, 4)):
    _op(_code, "LDY", _mode, _cycles)
for _code, _mode, _cycles in zip((0x86, 0x96, 0x8E), (ZP, ZPY, ABS), (3, 4, 4)):
    _op(_code, "STX", _mode, _cycles)
for _code, _mode, _cycles in zip((0x84, 0x94, 0x8C), (ZP, ZPX, ABS), (3, 4, 4)):
    _op(_code, "STY", _mode, _cycles)
for _code, _mode, _cycles in zip((0xE0, 0xE4, 0xEC), (IMM, ZP, ABS), (2, 3, 4)):
    _op(_code, "CPX", _mode, _cycles)
for _code, _mode, _cycles in zip((0xC0, 0xC4, 0xCC), (IMM, ZP, ABS), (2, 3, 4)):
    _op(_code, "CPY", _mode, _cycles)
_op(0x24, "BIT", ZP, 3)
_op(0x2C, "BIT", ABS, 4)
_op(0x4C, "JMP", ABS, 3)
_op(0x6C, "JMP", IND, 5)
_op(0x20, "JSR", ABS, 6)
for _code, _name in {0x10: "BPL", 0x30: "BMI", 0x50: "BVC", 0x70: "BVS", 0x90: "BCC", 0xB0: "BCS", 0xD0: "BNE", 0xF0: "BEQ"}.items():
    _op(_code, _name, REL, 2)
for _code, _name, _cycles in ((0xAA, "TAX", 2), (0x8A, "TXA", 2), (0xA8, "TAY", 2), (0x98, "TYA", 2), (0xBA, "TSX", 2),
                              (0x9A, "TXS", 2), (0xE8, "INX", 2), (0xCA, "DEX", 2), (0xC8, "INY", 2), (0x88, "DEY", 2),
                              (0x18, "CLC", 2), (0x38, "SEC", 2), (0x58, "CLI", 2), (0x78, "SEI", 2), (0xB8, "CLV", 2),
                              (0xD8, "CLD", 2), (0xF8, "SED", 2), (0xEA, "NOP", 2), (0x48, "PHA", 3), (0x68, "PLA", 4),
                              (0x08, "PHP", 3), (0x28, "PLP", 4), (0x60, "RTS", 6), (0x40, "RTI", 6), (0x00, "BRK", 7)):
    _op(_code, _name, IMP, _cycles)

# Opcodes no oficiales que algunos drivers usan como NOP
_NOPS = {0x1A, 0x3A, 0x5A, 0x7A, 0xDA, 0xFA}
_SKIP1 = {0x80, 0x82, 0x89, 0xC2, 0xE2, 0x04, 0x44, 0x64, 0x14, 0x34, 0x54, 0x74, 0xD4, 0xF4}
_SKIP2 = {0x0C, 0x1C, 0x3C, 0x5C, 0x7C, 0xDC, 0xFC}

C, Z, I, D, B, V, N = 0x01, 0x02, 0x04, 0x08, 0x10, 0x40, 0x80


class CPU6502:
    def __init__(self, read, write):
        self.read, self.write = read, write
        self.a = self.x = self.y = 0
        self.sp = 0xFD
        self.pc = 0
        self.p = I | 0x20
        self.cycles = 0

    # ---- pila y direcciones ----
    def push(self, value: int) -> None:
        self.write(0x100 + self.sp, value & 0xFF)
        self.sp = (self.sp - 1) & 0xFF

    def pull(self) -> int:
        self.sp = (self.sp + 1) & 0xFF
        return self.read(0x100 + self.sp)

    def fetch(self) -> int:
        value = self.read(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return value

    def fetch16(self) -> int:
        lo = self.fetch()
        return lo | self.fetch() << 8

    def address(self, mode: int) -> int:
        if mode == IMM:
            addr = self.pc
            self.pc = (self.pc + 1) & 0xFFFF
            return addr
        if mode == ZP:
            return self.fetch()
        if mode == ZPX:
            return (self.fetch() + self.x) & 0xFF
        if mode == ZPY:
            return (self.fetch() + self.y) & 0xFF
        if mode == ABS:
            return self.fetch16()
        if mode == ABX:
            return (self.fetch16() + self.x) & 0xFFFF
        if mode == ABY:
            return (self.fetch16() + self.y) & 0xFFFF
        if mode == IND:
            ptr = self.fetch16()
            return self.read(ptr) | self.read((ptr & 0xFF00) | ((ptr + 1) & 0xFF)) << 8  # el fallo de página del 6502
        if mode == INX:
            ptr = (self.fetch() + self.x) & 0xFF
            return self.read(ptr) | self.read((ptr + 1) & 0xFF) << 8
        if mode == INY:
            ptr = self.fetch()
            return ((self.read(ptr) | self.read((ptr + 1) & 0xFF) << 8) + self.y) & 0xFFFF
        raise ValueError(mode)

    # ---- banderas ----
    def nz(self, value: int) -> int:
        value &= 0xFF
        self.p = (self.p & ~(N | Z)) | (value & N) | (Z if value == 0 else 0)
        return value

    def flag(self, mask: int, on: bool) -> None:
        self.p = (self.p | mask) if on else (self.p & ~mask)

    def compare(self, register: int, value: int) -> None:
        self.flag(C, register >= value)
        self.nz(register - value)

    def adc(self, value: int) -> None:
        total = self.a + value + (self.p & C)
        self.flag(C, total > 0xFF)
        self.flag(V, bool(~(self.a ^ value) & (self.a ^ total) & 0x80))
        self.a = self.nz(total)

    def branch(self, taken: bool) -> int:
        offset = self.fetch()
        if not taken:
            return 0
        self.pc = (self.pc + (offset - 256 if offset & 0x80 else offset)) & 0xFFFF
        return 1

    # ---- un opcode ----
    def step(self) -> int:
        code = self.fetch()
        if code in _NOPS:
            return 2
        if code in _SKIP1:
            self.fetch()
            return 3
        if code in _SKIP2:
            self.fetch16()
            return 4
        entry = _OPS.get(code)
        if entry is None:
            raise ValueError(f"opcode {code:#04x} no soportado en {self.pc - 1:#06x}")
        name, mode, cycles = entry
        extra = 0
        if mode == REL:
            extra = self.branch({"BPL": not self.p & N, "BMI": bool(self.p & N), "BVC": not self.p & V, "BVS": bool(self.p & V),
                                 "BCC": not self.p & C, "BCS": bool(self.p & C), "BNE": not self.p & Z, "BEQ": bool(self.p & Z)}[name])
        elif mode == IMP:
            self.implied(name)
        elif name == "JSR":
            addr = self.address(mode)
            ret = (self.pc - 1) & 0xFFFF
            self.push(ret >> 8)
            self.push(ret)
            self.pc = addr
        elif name == "JMP":
            self.pc = self.address(mode)
        elif mode == ACC:
            self.a = self.shift(name, self.a)
        else:
            addr = self.address(mode)
            if name in ("STA", "STX", "STY"):
                self.write(addr, {"STA": self.a, "STX": self.x, "STY": self.y}[name])
            elif name in ("ASL", "LSR", "ROL", "ROR"):
                self.write(addr, self.shift(name, self.read(addr)))
            elif name in ("INC", "DEC"):
                self.write(addr, self.nz(self.read(addr) + (1 if name == "INC" else -1)))
            else:
                self.load_op(name, self.read(addr))
        self.cycles += cycles + extra
        return cycles + extra

    def load_op(self, name: str, value: int) -> None:
        if name == "LDA":
            self.a = self.nz(value)
        elif name == "LDX":
            self.x = self.nz(value)
        elif name == "LDY":
            self.y = self.nz(value)
        elif name == "ADC":
            self.adc(value)
        elif name == "SBC":
            self.adc(value ^ 0xFF)
        elif name == "AND":
            self.a = self.nz(self.a & value)
        elif name == "ORA":
            self.a = self.nz(self.a | value)
        elif name == "EOR":
            self.a = self.nz(self.a ^ value)
        elif name == "CMP":
            self.compare(self.a, value)
        elif name == "CPX":
            self.compare(self.x, value)
        elif name == "CPY":
            self.compare(self.y, value)
        elif name == "BIT":
            self.flag(Z, self.a & value == 0)
            self.p = (self.p & ~(N | V)) | (value & (N | V))
        else:
            raise ValueError(name)

    def shift(self, name: str, value: int) -> int:
        carry = self.p & C
        if name == "ASL":
            self.flag(C, bool(value & 0x80))
            value = value << 1
        elif name == "LSR":
            self.flag(C, bool(value & 1))
            value >>= 1
        elif name == "ROL":
            self.flag(C, bool(value & 0x80))
            value = value << 1 | carry
        else:
            self.flag(C, bool(value & 1))
            value = value >> 1 | carry << 7
        return self.nz(value)

    def implied(self, name: str) -> None:
        simple = {"TAX": ("x", "a"), "TXA": ("a", "x"), "TAY": ("y", "a"), "TYA": ("a", "y"), "TSX": ("x", "sp")}
        if name in simple:
            dst, src = simple[name]
            setattr(self, dst, self.nz(getattr(self, src)))
        elif name == "TXS":
            self.sp = self.x
        elif name in ("INX", "DEX"):
            self.x = self.nz(self.x + (1 if name == "INX" else -1))
        elif name in ("INY", "DEY"):
            self.y = self.nz(self.y + (1 if name == "INY" else -1))
        elif name in ("CLC", "SEC"):
            self.flag(C, name == "SEC")
        elif name in ("CLI", "SEI"):
            self.flag(I, name == "SEI")
        elif name in ("CLD", "SED"):
            self.flag(D, name == "SED")
        elif name == "CLV":
            self.flag(V, False)
        elif name == "PHA":
            self.push(self.a)
        elif name == "PLA":
            self.a = self.nz(self.pull())
        elif name == "PHP":
            self.push(self.p | B | 0x20)
        elif name == "PLP":
            self.p = (self.pull() & ~B) | 0x20
        elif name == "RTS":
            lo = self.pull()
            self.pc = ((lo | self.pull() << 8) + 1) & 0xFFFF
        elif name == "RTI":
            self.p = (self.pull() & ~B) | 0x20
            lo = self.pull()
            self.pc = lo | self.pull() << 8
        elif name == "BRK":
            raise ValueError("BRK en el código de la música")
        elif name == "NOP":
            pass
        else:
            raise ValueError(name)

    def call(self, address: int, a: int = 0, x: int = 0, y: int = 0, limit: int = 200_000) -> int:
        """Corre la subrutina en `address` (JSR) hasta que vuelva. Devuelve los ciclos que usó; falla si pasa de `limit`."""
        sentinel = 0x7FFF  # RTS de la subrutina vuelve a sentinel + 1
        self.a, self.x, self.y = a, x, y
        self.sp = 0xFD
        self.push((sentinel - 1) >> 8)
        self.push(sentinel - 1)
        self.pc = address
        start = self.cycles
        while self.pc != sentinel:
            self.step()
            if self.cycles - start > limit:
                raise TimeoutError(f"la rutina en {address:#06x} no vuelve (más de {limit} ciclos)")
        return self.cycles - start
