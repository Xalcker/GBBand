"""Cable link entre dos PyBoy, para las pruebas de 2 jugadores.

PyBoy 2.8.1 no conecta dos consolas de forma útil para las pruebas: su modo de memoria compartida necesita dos hilos que se
esperan en cada byte (con 30 s de límite) y el puerto serie normal siempre lee $FF. Aquí las dos consolas avanzan a la
par, un cuadro cada una, y el puente pasa los bytes con hooks en las rutinas de link.asm:

- `SerialSend`: el maestro empieza una transferencia con reloj interno (A = byte que sale). PyBoy la termina sola a los
  1024 ciclos y dispara la interrupción serie, que pasa por `SerialGot`.
- `SerialArm`: el esclavo dejó un byte armado con reloj externo (A = byte). PyBoy nunca la termina: lo hace el puente.
- `SerialOff`: se canceló lo armado o lo que estaba en curso.
- `SerialGot`: la ISR serie acaba de leer rSB (A = $FF en PyBoy). Si esta consola era el maestro, el puente cambia A por
  el byte armado del otro y, si el otro estaba armado, le entrega el del maestro y le levanta la interrupción serie. Si
  esta consola era el esclavo, A es el byte que el maestro le entregó.

Como cada consola corre un cuadro completo por turno, el esclavo recibe el byte hasta un cuadro después que en una
consola real. El protocolo de link.asm no depende de eso (un byte por cuadro y mensajes con tipo).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .runner import Runner

IF_SERIAL = 0x08


@dataclass
class _End:
    r: Runner
    sending: int | None = None          # byte del maestro en curso
    armed: int | None = None            # byte armado del esclavo
    pending: deque = field(default_factory=deque)   # bytes entregados al esclavo, por leer en su ISR
    sent: int = 0                       # transferencias completas como maestro


class LinkBridge:
    """Conecta dos Runner (con símbolos) y los avanza a la par."""

    def __init__(self, a: Runner, b: Runner):
        self.ends = [_End(a), _End(b)]
        for i, end in enumerate(self.ends):
            sym = end.r.symbols
            for name, cb in (("SerialSend", self._on_send), ("SerialArm", self._on_arm), ("SerialOff", self._on_off),
                             ("SerialGot", self._on_got)):
                end.r.pb.hook_register(0, sym[name], cb, i)

    def tick(self, frames: int = 1) -> None:
        for _ in range(frames):
            for end in self.ends:
                end.r.tick(1, False)

    def exchanges(self) -> int:
        return sum(end.sent for end in self.ends)

    def _a(self, i: int) -> int:
        return self.ends[i].r.pb.register_file.A

    def _on_send(self, i: int) -> None:
        end = self.ends[i]
        end.sending, end.armed = self._a(i), None

    def _on_arm(self, i: int) -> None:
        end = self.ends[i]
        end.armed, end.sending = self._a(i), None

    def _on_off(self, i: int) -> None:
        end = self.ends[i]
        end.armed = end.sending = None

    def _on_got(self, i: int) -> None:
        me, other = self.ends[i], self.ends[1 - i]
        regs = me.r.pb.register_file
        if me.sending is not None:
            out, me.sending = me.sending, None
            me.sent += 1
            if other.armed is not None:          # del otro lado hay un esclavo esperando: se cruzan los bytes
                regs.A, other.armed = other.armed, None
                other.pending.append(out)
                pb = other.r.pb
                pb.memory[0xFF0F] = pb.memory[0xFF0F] | IF_SERIAL
            else:                                 # nadie armado (o el otro también es maestro): se lee $FF
                regs.A = 0xFF
        elif me.pending:
            regs.A = me.pending.popleft()
