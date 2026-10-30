"""Un SM83 (el CPU de la Game Boy) lo bastante completo para correr el código de música de un GBS.

Todos los opcodes documentados, con el prefijo $CB; los 11 que no existen fallan. Los ciclos son ciclos T (4 por ciclo
de máquina), con los extra de los saltos tomados; el importador solo los usa para no pasarse del tiempo entre dos
llamadas a la rutina de reproducción. No hay interrupciones: HALT y STOP no esperan nada. El que lo use implementa
`read(addr)` y `write(addr, value)`; `rst_base` mueve los vectores de RST (un GBS los pone en su dirección de carga).
Se compara contra el CPU de PyBoy en `tests/test_gbs.py`.
"""

from __future__ import annotations

Z, N, H, C = 0x80, 0x40, 0x20, 0x10
B_, C_, D_, E_, H_, L_, HL_, A_ = range(8)  # índice de registro en los opcodes; 6 es (HL)
UNDEFINED = {0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD}


class SM83:
    def __init__(self, read, write, rst_base: int = 0):
        self.read, self.write = read, write
        self.rst_base = rst_base
        self.r = [0] * 8  # B C D E H L - A
        self.f = 0
        self.sp = 0xFFFE
        self.pc = 0
        self.ime = False
        self.cycles = 0
        self.ops = [self._decode(op) for op in range(256)]

    # ---- registros ---------------------------------------------------------------------------------------------

    def get(self, i: int) -> int:
        return self.read(self.r[4] << 8 | self.r[5]) if i == HL_ else self.r[i]

    def put(self, i: int, value: int) -> None:
        if i == HL_:
            self.write(self.r[4] << 8 | self.r[5], value & 0xFF)
        else:
            self.r[i] = value & 0xFF

    def pair(self, p: int) -> int:
        """BC, DE, HL, SP (p = 0 a 3)."""
        if p == 3:
            return self.sp
        return self.r[2 * p] << 8 | self.r[2 * p + 1]

    def set_pair(self, p: int, value: int) -> None:
        value &= 0xFFFF
        if p == 3:
            self.sp = value
        else:
            self.r[2 * p], self.r[2 * p + 1] = value >> 8, value & 0xFF

    def fetch(self) -> int:
        value = self.read(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return value

    def fetch16(self) -> int:
        lo = self.fetch()
        return self.fetch() << 8 | lo

    def push(self, value: int) -> None:
        self.sp = (self.sp - 1) & 0xFFFF
        self.write(self.sp, value >> 8)
        self.sp = (self.sp - 1) & 0xFFFF
        self.write(self.sp, value & 0xFF)

    def pop(self) -> int:
        lo = self.read(self.sp)
        hi = self.read((self.sp + 1) & 0xFFFF)
        self.sp = (self.sp + 2) & 0xFFFF
        return hi << 8 | lo

    def cond(self, cc: int) -> bool:
        """NZ, Z, NC, C."""
        flag = self.f & (Z if cc < 2 else C)
        return bool(flag) == bool(cc & 1)

    # ---- aritmética ----------------------------------------------------------------------------------------------

    def alu(self, kind: int, v: int) -> None:
        """ADD ADC SUB SBC AND XOR OR CP con A."""
        a = self.r[A_]
        if kind in (0, 1):
            carry = 1 if kind == 1 and self.f & C else 0
            res = a + v + carry
            self.f = (0 if res & 0xFF else Z) | (H if (a & 15) + (v & 15) + carry > 15 else 0) | (C if res > 0xFF else 0)
            self.r[A_] = res & 0xFF
        elif kind in (2, 3, 7):
            carry = 1 if kind == 3 and self.f & C else 0
            res = a - v - carry
            self.f = N | (0 if res & 0xFF else Z) | (H if (a & 15) - (v & 15) - carry < 0 else 0) | (C if res < 0 else 0)
            if kind != 7:
                self.r[A_] = res & 0xFF
        elif kind == 4:
            self.r[A_] = res = a & v
            self.f = (0 if res else Z) | H
        else:
            self.r[A_] = res = a ^ v if kind == 5 else a | v
            self.f = 0 if res else Z

    def cb_shift(self, kind: int, v: int) -> int:
        """RLC RRC RL RR SLA SRA SWAP SRL; deja Z según el resultado."""
        carry_in = 1 if self.f & C else 0
        if kind == 0:
            out, res = v >> 7, (v << 1 | v >> 7) & 0xFF
        elif kind == 1:
            out, res = v & 1, (v >> 1 | v << 7) & 0xFF
        elif kind == 2:
            out, res = v >> 7, (v << 1 | carry_in) & 0xFF
        elif kind == 3:
            out, res = v & 1, v >> 1 | carry_in << 7
        elif kind == 4:
            out, res = v >> 7, (v << 1) & 0xFF
        elif kind == 5:
            out, res = v & 1, v >> 1 | v & 0x80
        elif kind == 6:
            out, res = 0, (v << 4 | v >> 4) & 0xFF
        else:
            out, res = v & 1, v >> 1
        self.f = (0 if res else Z) | (C if out else 0)
        return res

    def add_sp(self) -> int:
        """SP + e (con signo), con las banderas de ADD SP,e y LD HL,SP+e."""
        e = self.fetch()
        sp = self.sp
        self.f = (H if (sp & 15) + (e & 15) > 15 else 0) | (C if (sp & 0xFF) + e > 0xFF else 0)
        return (sp + (e - 256 if e > 127 else e)) & 0xFFFF

    # ---- decodificación ------------------------------------------------------------------------------------------

    def _decode(self, op: int):
        """Una función por opcode que lo ejecuta y devuelve sus ciclos de máquina."""
        x, y, z = op >> 6, op >> 3 & 7, op & 7
        p, q = y >> 1, y & 1
        if op in UNDEFINED:
            def undefined():
                raise ValueError(f"opcode ${op:02X} no existe (en {self.pc - 1:#06x})")
            return undefined
        if x == 1:
            if op == 0x76:
                return lambda: 1  # HALT: sin interrupciones no hay nada que esperar
            cost = 2 if HL_ in (y, z) else 1
            def ld():
                self.put(y, self.get(z))
                return cost
            return ld
        if x == 2:
            cost = 2 if z == HL_ else 1
            def alu_r():
                self.alu(y, self.get(z))
                return cost
            return alu_r
        if op == 0xCB:
            return self.prefixed
        table = {
            0x00: lambda: 1,
            0x10: self.stop,
            0x08: self.ld_nn_sp,
            0x18: self.jr,
            0x07: lambda: self.rot_a(0), 0x0F: lambda: self.rot_a(1), 0x17: lambda: self.rot_a(2), 0x1F: lambda: self.rot_a(3),
            0x27: self.daa, 0x2F: self.cpl, 0x37: self.scf, 0x3F: self.ccf,
            0x02: lambda: self.st_a(self.pair(0)), 0x12: lambda: self.st_a(self.pair(1)),
            0x22: lambda: self.st_a(self.hl_step(1)), 0x32: lambda: self.st_a(self.hl_step(-1)),
            0x0A: lambda: self.ld_a(self.pair(0)), 0x1A: lambda: self.ld_a(self.pair(1)),
            0x2A: lambda: self.ld_a(self.hl_step(1)), 0x3A: lambda: self.ld_a(self.hl_step(-1)),
            0xC3: self.jp, 0xC9: self.ret, 0xD9: self.reti, 0xCD: self.call_nn, 0xE9: self.jp_hl,
            0xE0: lambda: self.st_a(0xFF00 | self.fetch()) + 1, 0xF0: lambda: self.ld_a(0xFF00 | self.fetch()) + 1,
            0xE2: lambda: self.st_a(0xFF00 | self.r[C_]), 0xF2: lambda: self.ld_a(0xFF00 | self.r[C_]),
            0xEA: lambda: self.st_a(self.fetch16()) + 2, 0xFA: lambda: self.ld_a(self.fetch16()) + 2,
            0xE8: self.add_sp_e, 0xF8: self.ld_hl_sp, 0xF9: self.ld_sp_hl,
            0xF3: self.di, 0xFB: self.ei,
        }
        if op in table:
            return table[op]
        if x == 0:
            if z == 0:  # JR cc
                return lambda: self.jr() if self.cond(y - 4) else self.skip(1, 2)
            if z == 1:
                if q == 0:
                    def ld_rr():
                        self.set_pair(p, self.fetch16())
                        return 3
                    return ld_rr
                def add_hl():
                    hl, v = self.pair(2), self.pair(p)
                    res = hl + v
                    self.f = (self.f & Z) | (H if (hl & 0xFFF) + (v & 0xFFF) > 0xFFF else 0) | (C if res > 0xFFFF else 0)
                    self.set_pair(2, res)
                    return 2
                return add_hl
            if z == 3:
                step = 1 if q == 0 else -1
                def inc_rr():
                    self.set_pair(p, self.pair(p) + step)
                    return 2
                return inc_rr
            if z in (4, 5):
                cost = 3 if y == HL_ else 1
                up = z == 4
                def inc_r():
                    v = self.get(y)
                    if up:
                        res = (v + 1) & 0xFF
                        half = (v & 15) == 15
                    else:
                        res = (v - 1) & 0xFF
                        half = (v & 15) == 0
                    self.put(y, res)
                    self.f = (self.f & C) | (0 if res else Z) | (H if half else 0) | (0 if up else N)
                    return cost
                return inc_r
            if z == 6:
                cost = 3 if y == HL_ else 2
                def ld_n():
                    self.put(y, self.fetch())
                    return cost
                return ld_n
        if x == 3:
            if z == 0:  # RET cc
                return lambda: self.ret() + 1 if self.cond(y) else 2
            if z == 1:  # POP
                def pop():
                    v = self.pop()
                    if p == 3:
                        self.r[A_], self.f = v >> 8, v & 0xF0
                    else:
                        self.set_pair(p, v)
                    return 3
                return pop
            if z == 2:  # JP cc
                return lambda: self.jp() if self.cond(y) else self.skip(2, 3)
            if z == 4:  # CALL cc
                return lambda: self.call_nn() if self.cond(y) else self.skip(2, 3)
            if z == 5:  # PUSH
                def push():
                    self.push(self.r[A_] << 8 | self.f if p == 3 else self.pair(p))
                    return 4
                return push
            if z == 6:
                def alu_n():
                    self.alu(y, self.fetch())
                    return 2
                return alu_n
            if z == 7:
                target = y * 8
                def rst():
                    self.push(self.pc)
                    self.pc = (self.rst_base + target) & 0xFFFF
                    return 4
                return rst
        raise AssertionError(f"opcode ${op:02X} sin decodificar")

    def skip(self, size: int, cost: int) -> int:
        self.pc = (self.pc + size) & 0xFFFF
        return cost

    def stop(self) -> int:
        self.fetch()
        return 1

    def ld_nn_sp(self) -> int:
        addr = self.fetch16()
        self.write(addr, self.sp & 0xFF)
        self.write((addr + 1) & 0xFFFF, self.sp >> 8)
        return 5

    def jr(self) -> int:
        e = self.fetch()
        self.pc = (self.pc + (e - 256 if e > 127 else e)) & 0xFFFF
        return 3

    def jp(self) -> int:
        self.pc = self.fetch16()
        return 4

    def jp_hl(self) -> int:
        self.pc = self.pair(2)
        return 1

    def call_nn(self) -> int:
        target = self.fetch16()
        self.push(self.pc)
        self.pc = target
        return 6

    def ret(self) -> int:
        self.pc = self.pop()
        return 4

    def reti(self) -> int:
        self.ime = True
        return self.ret()

    def di(self) -> int:
        self.ime = False
        return 1

    def ei(self) -> int:
        self.ime = True
        return 1

    def hl_step(self, step: int) -> int:
        hl = self.pair(2)
        self.set_pair(2, hl + step)
        return hl

    def st_a(self, addr: int) -> int:
        self.write(addr, self.r[A_])
        return 2

    def ld_a(self, addr: int) -> int:
        self.r[A_] = self.read(addr)
        return 2

    def rot_a(self, kind: int) -> int:
        self.r[A_] = self.cb_shift(kind, self.r[A_])
        self.f &= C  # RLCA y compañía siempre dejan Z en 0
        return 1

    def daa(self) -> int:
        a, f = self.r[A_], self.f
        if f & N:
            if f & C:
                a -= 0x60
            if f & H:
                a -= 6
        else:
            if f & C or a > 0x99:
                a += 0x60
                f |= C
            if f & H or (a & 15) > 9:
                a += 6
        a &= 0xFF
        self.r[A_] = a
        self.f = (f & (N | C)) | (0 if a else Z)
        return 1

    def cpl(self) -> int:
        self.r[A_] ^= 0xFF
        self.f |= N | H
        return 1

    def scf(self) -> int:
        self.f = (self.f & Z) | C
        return 1

    def ccf(self) -> int:
        self.f = (self.f & (Z | C)) ^ C
        return 1

    def add_sp_e(self) -> int:
        self.sp = self.add_sp()
        return 4

    def ld_hl_sp(self) -> int:
        self.set_pair(2, self.add_sp())
        return 3

    def ld_sp_hl(self) -> int:
        self.sp = self.pair(2)
        return 2

    def prefixed(self) -> int:
        op = self.fetch()
        x, y, z = op >> 6, op >> 3 & 7, op & 7
        v = self.get(z)
        if x == 0:
            self.put(z, self.cb_shift(y, v))
        elif x == 1:
            self.f = (self.f & C) | H | (0 if v >> y & 1 else Z)
            return 3 if z == HL_ else 2
        elif x == 2:
            self.put(z, v & ~(1 << y))
        else:
            self.put(z, v | 1 << y)
        return 4 if z == HL_ else 2

    # ---- ejecución -----------------------------------------------------------------------------------------------

    def step(self) -> int:
        op = self.read(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        cycles = self.ops[op]() * 4
        self.cycles += cycles
        return cycles

    def call(self, address: int, a: int = 0, limit: int = 1_000_000, sentinel: int = 0xFFFF) -> int:
        """Corre la subrutina en `address` (CALL) hasta que vuelva a `sentinel`. Devuelve los ciclos T que usó; falla si
        pasa de `limit`. Los registros y el SP quedan como estaban (el que llama los prepara)."""
        self.r[A_] = a
        self.push(sentinel)
        self.pc = address
        start = self.cycles
        ops, read = self.ops, self.read
        while self.pc != sentinel:
            op = read(self.pc)
            self.pc = (self.pc + 1) & 0xFFFF
            self.cycles += ops[op]() * 4
            if self.cycles - start > limit:
                raise TimeoutError(f"la rutina en {address:#06x} no vuelve (más de {limit} ciclos)")
        return self.cycles - start
