# GBBand

Un juego de ritmo estilo Guitar Hero / Rock Band para **Game Boy Color**, compatible con la Game Boy original
(DMG). Es el equivalente de [NESBand](https://github.com/Xalcker/NESBand).

**Estado actual (fase 1 de 5):** esqueleto. Hay una ROM "hola mundo" de 2 MB (MBC5 con 8 KB de SRAM con batería)
que arranca en DMG y en GBC y detecta en cuál está, y las herramientas para compilarla y probarla. El juego
todavía no existe.

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
- **El tiempo se mide en cuadros.** La música y las notas comparten el mismo contador de cuadros, así que nunca
  se desfasan.

## Licencia

**GNU General Public License, versión 2 o (a tu elección) cualquier versión posterior** (GPL-2.0-or-later; ver
[LICENSE](LICENSE)). La fuente de las letras es *Bongo-8 Mono* de Caffinate (Nathan Scott), de dominio público
(CC0 1.0). La música de juegos comerciales no se incluye ni se distribuye.
