# GBBand

Un juego de ritmo estilo Guitar Hero / Rock Band para **Game Boy Color**, compatible con la Game Boy original
(DMG). Es el equivalente de [NESBand](https://github.com/Xalcker/NESBand).

**Estado actual (fase 2 de 5):** hay una rebanada jugable. Un menú de dificultad (fácil, medio, difícil,
experto) y una canción original de ~32 s con su música (stream de registros del APU, un registro por cuadro). Las notas
caen por una autopista de 5 carriles, se aciertan con ←, ↓, →, B y A (ventana de ±6 cuadros), suman puntaje y combo, y
el instrumento se calla si fallas. Corre en Game Boy original (DMG) y en Game Boy Color con el mismo ROM de 2 MB. Aún no
hay título, opciones, resultados con estrellas, récords ni más canciones (ver la hoja de ruta de [docs/diseno.md](docs/diseno.md)).

## Sobre este proyecto

Todo el código de GBBand lo escribe una IA (Claude). Yo solo pongo las ideas y no sé SM83 ni Game Boy.

**Aviso:** GBBand es un proyecto de aficionados, sin relación con Nintendo, ni con Guitar Hero ni Rock Band.
"Game Boy" solo indica la plataforma para la que está hecho.

## Instalación

### Windows

1. **RGBDS v1.0.4** ([releases](https://github.com/gbdev/rgbds/releases/tag/v1.0.4), `rgbds-win64.zip`):
   descomprímelo en `tools/rgbds/` (debe quedar `tools/rgbds/rgbasm.exe`).
2. **Mesen 2** ([releases](https://github.com/SourMesen/Mesen2/releases), `Mesen_2.1.1_Windows.zip`): `Mesen.exe`
   en `tools/mesen/`. Es el depurador (carga el `.sym`).
3. **uv** para las herramientas de Python: [instrucciones](https://docs.astral.sh/uv/getting-started/installation/).
   `uv sync` crea el entorno (incluye PyBoy, el corredor de pruebas).

`tools/` está en `.gitignore`: cada máquina baja sus propias herramientas.

### macOS

```bash
brew install rgbds uv powershell
uv sync
```

Mesen 2: baja `Mesen_<versión>_macOS_*.zip` de [releases](https://github.com/SourMesen/Mesen2/releases) y déjalo
en `tools/mesen/`.

## Cómo jugar (fase 2)

En el menú, ←/→ elige la dificultad y Start empieza. Carriles: verde ←, rojo ↓, amarillo →, azul B, naranja A.
Fácil usa 3 carriles, medio 4 y difícil y experto 5. Al terminar la canción, Start vuelve al menú.

## Compilar y probar

```bash
.\build.ps1          # Windows
./build.sh           # macOS / Linux
```

El resultado es `build/gbband.gb` (con `build/gbband.sym` para el depurador). Opciones: `-Release` (`--release`)
deja `build/release/gbband-v<versión>.gb` con su `.sha256`; la compilación es reproducible. `-Nombre` (`NOMBRE=`)
deja otra copia sin pisar la normal.

```bash
.\tests\run_tests.ps1          # Windows
./tests/run_tests.sh           # macOS / Linux
```

Las pruebas (unos 15 s) compilan el ROM y corren un bot en PyBoy, en modo DMG y en CGB: uno perfecto en las 4
dificultades (puntaje exacto, 100 %, cada nota del chart cae en el mismo cuadro que el audio de su nota, 0 cuadros
atrasados), otro que no toca nada (todo falla y el instrumento queda callado), otro que machaca botones (combo ≤ 5, ≤ 2
estrellas), y la comparación de colocaciones de las gemas. Dejan `resultado.txt` y capturas en `build/test-demo-<bot>-<dificultad>-<modo>/`.
Para ver la canción compilada en Mesen: `tools\mesen\Mesen.exe build\gbband.gb`.

## Conceptos clave (para ir aprendiendo)

- **Cuadros.** La pantalla se dibuja 59.73 veces por segundo. Entre un cuadro y otro hay un ratito, el *VBlank*,
  en el que se puede escribir en la memoria de video sin que salga basura. El juego se divide igual que NESBand:
  el bucle principal calcula y deja todo en buffers, y la interrupción de VBlank solo copia.
- **Tiles y mapas.** La pantalla es una cuadrícula de 20×18 tiles de 8×8 píxeles. El mapa del fondo dice qué tile
  va en cada casilla; para mover el fondo basta cambiar un registro (el *scroll*).
- **Window.** Una capa del fondo que no se desplaza. Aquí es la franja de abajo con el marcador.
- **Bancos (MBC5).** El procesador solo ve 32 KB de cartucho a la vez; el mapper deja fijos los primeros 16 KB y
  cambia lo que se ve en los otros 16 KB escribiendo el número de banco en una dirección especial. Por eso la
  interrupción nunca cambia de banco: podría interrumpir al código que está leyendo de ahí.
- **DMG y CGB.** Es el mismo ROM. Al arrancar, el registro A vale `$11` en una Game Boy Color; el juego lo guarda y
  decide si usa paletas de color o los 4 tonos de gris.
- **Scroll en vez de dibujar.** Las notas no se mueven: el fondo se desplaza un poco cada cuadro (`SCY`) y la fila nueva
  se arma justo arriba, donde todavía no se ve. El fondo mide 32 filas y da la vuelta exacta.
- **Gemas con 4 posiciones.** Una nota no cae siempre en múltiplos de 8 píxeles: cada gema tiene 4 variantes dibujadas
  más abajo 0, 2, 4 o 6 píxeles, así se ve en su sitio con menos de 2 píxeles de error.
- **Audio como lista de escrituras.** La música no se sintetiza en el juego: es una lista de "escribe este valor en este
  registro del chip de sonido" por cada cuadro, preparada en la PC. El bucle principal la lee y la deja en un buffer;
  la interrupción de VBlank solo copia del buffer al chip (nunca lee del cartucho).
- **El tiempo se mide en cuadros.** La música y las notas comparten el mismo contador de cuadros, así que nunca
  se desfasan.

## Licencia

**GNU General Public License, versión 2 o (a tu elección) cualquier versión posterior** (GPL-2.0-or-later; ver
[LICENSE](LICENSE)). La fuente de las letras es *Bongo-8 Mono* de Caffinate (Nathan Scott), de dominio público
(CC0 1.0). La música de juegos comerciales no se incluye ni se distribuye.
