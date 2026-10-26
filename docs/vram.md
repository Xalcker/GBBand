# VRAM, colocación de las notas y presupuestos (fase 2)

Todas las cifras de esta página salen de ejecutar el ROM (`build/test-demo-*/resultado.txt`, `build/colocacion-a-b.txt`)
o de `uv run gbband measure-placement`. Lo medido en PyBoy 2.8.1 se cruzó con Mesen 2 2.1.1 solo en lo básico
(ver abajo). Nada está probado en hardware real.

## Tiles (modo `$8000`, fondo y sprites comparten los 256 tiles)

| Tiles | Uso |
|---|---|
| `$00`-`$09` | vacío, carril (izquierda y derecha), marco y paneles del escenario, bordes (`src/chr/ui.tiles`) |
| `$0A`-`$0D` | aro de los carriles (sprite 8x16, normal y apretado) |
| `$20`-`$5A` | fuente ASCII en mayúsculas (`font.tiles`): el tile es el código del carácter |
| `$60`-`$A5` | gemas: 5 carriles x 14 tiles (`gems.tiles`, generado por `gbband build-gems`) |
| `$A6`-`$FF` | libres (90 tiles) |

Total usado con la colocación **B**: 143 tiles (los de las gemas: 70). Con la **A** bastarían 83 (gemas: 10), y los
tiles `$62`-`$A5` salvo los de desplazamiento 0 quedarían libres. En DMG quedan además los 128 tiles del modo `$8800`
(`LCDC.4`) sin usar; en CGB, todo el banco 1 de VRAM (solo se usa para los atributos del mapa).
La hoja de contacto de todos los tiles se genera en `build/chr/tiles.png`.

Mapas: `$9800` = fondo con scroll (32x32, autopista y escenario); `$9C00` = Window (HUD de 2 filas, `WY=128`: puntaje y multiplicador, combo y máximo). Los aciertos y fallos solo salen en el resumen del final de la canción, escritos sobre la autopista.
CGB: atributos del mapa en el banco 1; paleta 0 = escenario y texto, paletas 1 a 5 = los 5 carriles (verde, rojo,
amarillo, azul, naranja). En DMG los carriles se distinguen por forma: ◀ ▼ ▶ anillo rombo.

## Colocación A contra B

Medida con el ROM compilado en las dos variantes (`build.ps1 -Colocacion A|B`), un bot perfecto, 1444 a 1933 gemas
medidas en DMG (lectura del mapa de VRAM y del `SCY` real contra la posición ideal de cada nota):

| | Error máximo | Error medio | Tiles de gemas | Separación mínima entre dos notas del mismo carril |
|---|---|---|---|---|
| **A** (una fila de tiles, 8 px) | **4.46 px** (6.7 cuadros en fácil, 3.3 en experto) | 2.0 px | 10 | 8 px: 12, 10, 8 y 6 cuadros (fácil a experto) |
| **B** (4 desplazamientos: 0, 2, 4 y 6 px) | **1.50 px** (2.2 cuadros en fácil, 1.1 en experto) | 0.5 px | 70 | 16 px: 24, 20, 16 y 12 cuadros |

El error de B es 1 px de la gema (a pasos de 2 px) más 0.5 px del `SCY` (que se redondea al píxel más cercano; truncarlo
sesgaba todo +0.5 px). La ventana de acierto es de ±6 cuadros: con A, en fácil, la nota puede verse 6.7 cuadros fuera de
su sitio (más que la ventana entera); con B, a 2.2 cuadros.

**El costo de B es la separación entre notas del mismo carril** (una gema B puede cruzar dos filas de tiles y dos gemas
no pueden compartir un tile). Con los charts reales de NESBand (10 canciones, guitarra, teclado y bajo,
`gbband measure-placement`), notas que se pisarían en B y habría que quitar o mover al generar el chart:

| Dificultad | Notas | Pisadas con A | Pisadas con B |
|---|---|---|---|
| Fácil | 4519 | 0 | 0 |
| Medio | 5871 | 0 | 166 (2.8 %) |
| Difícil | 7196 | 0 | 296 (4.1 %) |
| Experto | 7845 | 14 (0.2 %) | 181 (2.3 %) |

**Decisión: B.** El generador de charts de GB aplica `min_lane_gap` (en píxeles, ver `layout.py`) y, si el carril que
tocaba no está libre, usa el más cercano que sí lo esté. Con la canción de prueba, ninguna dificultad pierde notas.
`PLACEMENT_B=0` (`-Colocacion A`) deja la A como opción de compilación.

## Presupuestos medidos (bot perfecto, experto; `resultado.txt` de cada caso)

| Concepto | Objetivo | DMG | CGB |
|---|---|---|---|
| Bytes copiados a VRAM por cuadro (máximo) | ≤ 96 | 33 | 46 (fácil: 49) |
| La cola de VRAM termina dentro del VBlank | línea ≤ 153 | línea 6 de 10 del VBlank (sin desbordes) | línea 7 de 10 (sin desbordes) |
| ISR completa, máximo (resolución 64 M) | ≤ 1140 | 960 M | 1088 M |
| Bucle principal, máximo / medio | ≤ 7000 (gameplay 5000 + filas y HUD 2000) | 2964 / 903 M | 3192 / 940 M |
| Cuadros atrasados | ≤ 2 | 0 | 0 |
| Sprites por línea (máximo) | ≤ 8 | 5 | 5 |
| Sprites totales | ≤ 20 | 5 | 5 |
| Subdesbordes del audio (el bucle principal no alcanzó a decodificar) | 0 | 0 | 0 |

El máximo del cuadro de CPU (3192 M de 17556) deja ≥ 80 % de holgura. **Lo que sí está cerca del límite es la ISR** en los
cuadros donde suenan los cuatro canales a la vez (hasta 18 escrituras de registro) y hay que copiar la fila: la cola
de VRAM termina en la línea 7 de las 10 del VBlank. Para no crecer más allá:

- el HUD manda un grupo de dígitos por cuadro, no todos a la vez (con todos juntos la ISR pasaba de 1280 M);
- la sombra de registros del APU y los contadores de altas de nota se direccionan con un solo `ld e, c`;
- `wOverrun` cuenta cualquier ISR cuya cola termine fuera del VBlank y las pruebas exigen 0.

## Cómo se mide

- **Error visual:** `playtest.visual_errors` lee el mapa `$9800` y el `SCY` del hardware en el hook de fin de ISR.
- **Bytes de VRAM, ISR, bucle principal, sprites por línea:** contadores de la propia ROM (`wQMax`, `wIsrMax` con `DIV`,
  `wCpuMax` con `LY`, `wFlushLines`) y el OAM en sombra.
- **Qué es solo de emulador:** todo. En DMG real hay que revisar además que no haya basura al escribir VRAM cerca del
  final del VBlank (por eso `wOverrun`), y el balance de la ISR depende del `DIV` del emulador.
