"""Titulo: la pista de la pantalla de titulo (La menor, 150 BPM, 8 compases que se repiten). Melodia en el pulso 1,
arpegios en el pulso 2, bajo en el triangulo y bateria en el ruido.

Uso (desde la raiz del repositorio):  uv run python audio/titulo.py
"""

from pathlib import Path

from compose import Cancion, Escala, Instrumento, arpegio, escribir

AQUI = Path(__file__).parent
LA_MENOR = Escala(["A", "B", "C", "D", "E", "F", "G"])

instrumentos = {
    "Guitarra": Instrumento([13, 13, 12, 12, 11, 11, 10, 10], [1]),
    "Teclado": Instrumento([9, 8, 8, 7, 6, 5, 4, 3], [2]),
    "Bajo": Instrumento(),
    "Bombo": Instrumento([15, 12, 9, 6, 3, 1, 0]),
    "Tarola": Instrumento([13, 11, 8, 6, 4, 2, 1, 0]),
    "Platillo": Instrumento([7, 4, 2, 0]),
    "Abierto": Instrumento([9, 7, 6, 5, 4, 3, 2, 1, 0]),
}

melodia = [
    "A4:2 C5:2 E5:4 A5:4 G5:2 E5:2",  # La menor
    "F5:4 A5:4 C6:4 A5:2 F5:2",  # Fa
    "G5:2 E5:2 C5:4 E5:4 G5:4",  # Do
    "D5:4 G5:4 B5:4 D6:2 B5:2",  # Sol
    "E5:2 A5:2 C6:4 B5:2 A5:2 E5:4",  # La menor
    "F5:2 A5:2 C6:4 A5:4 F5:4",  # Fa
    "G5:2 B5:2 D6:4 C6:2 B5:2 G5:4",  # Sol
    "A5:8 E5:4 A4:4",  # La menor (cierra y vuelve a empezar)
]
raices = ["A2", "F2", "C3", "G2", "A2", "F2", "G2", "A2"]
ARPEGIO = [0, 1, 2, 1, 0, 1, 2, 1]

pulso1 = ["@Guitarra " + melodia[0]] + melodia[1:]
pulso2 = ["@Teclado " + arpegio(raices[0], LA_MENOR, ARPEGIO, 2)] + [arpegio(r, LA_MENOR, ARPEGIO, 2) for r in raices[1:]]


def bajo_corcheas(r):
    alta = r[0] + str(int(r[1:]) + 1)
    return f"{r}:2 {r}:2 {alta}:2 {r}:2 {r}:2 {r}:2 {alta}:2 {r}:2"


bajo = [bajo_corcheas(r) for r in raices]
RITMO = "K.H.S.H.K.H.S.H."
RELLENO = "K.H.S.H.SSKKSSSS"
ruido = [RITMO] * 3 + [RELLENO] + [RITMO] * 3 + [RELLENO]

cancion = Cancion(
    "Titulo", 6, instrumentos,
    {"pulso1": pulso1, "pulso2": pulso2, "triangulo": bajo, "ruido": ruido},
    {"pulso1": "Guitarra", "pulso2": "Teclado", "triangulo": "Bajo", "ruido": "Bombo"},
)
escribir(cancion, AQUI / "titulo.txt")
