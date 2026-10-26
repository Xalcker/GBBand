# VRAM, colocación de las notas y presupuestos (fases 2 y 3)

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
| **B** (4 desplazamientos: 0, 2, 4 y 6 px) | **1.50 px** (2.2 cuadros en fácil, 1.1 en experto) | 0.5 px | 70 | 16 px: 21, 18, 14 y 11 cuadros |

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

## Presupuestos medidos (fase 3: las 10 canciones, 4 instrumentos, DMG y CGB, 154 partidas)

Peor caso de todas las partidas con el bot perfecto, el que no toca y el que machaca (`resultado.txt` de cada caso):

| Concepto | Objetivo | Peor caso medido |
|---|---|---|
| Bytes copiados a VRAM por cuadro | ≤ 96 | **59** |
| La cola de VRAM termina dentro del VBlank | línea 10 de las 10 | **línea 6** (sin un solo desborde) |
| ISR completa, con el audio (resolución 64 M) | ≤ 1140 antes del audio | 1344 M (el audio va al final: no importa si pasa del VBlank) |
| Bucle principal (resolución 114 M) | ≤ 7000 (gameplay 5000 + filas y HUD 2000) | **4902** de 17556 |
| Cuadros atrasados | ≤ 2 | **0** |
| Sprites por línea / totales | ≤ 8 / ≤ 20 | 5 / 5 |
| Subdesbordes del audio | 0 | **0** |

Lo que costó llegar ahí (fase 3, con canciones de 5 canales y acordes):
- El audio con los cuatro canales a la vez (18 escrituras) tardaba hasta ~400 M y empujaba la cola de VRAM fuera del VBlank en
  *Cumbia del Cartucho* (CGB): **el audio pasó al final de la ISR** (decisiones.md, fase 3, punto 8).
- Ya no se copia todo el OAM por DMA cuando cambia un aro: se copian los 5 tiles (55 M contra 160 M).
- Una fila vacía del fondo no se escribe si no tenía gemas (en CGB ahorra 20 de los ~26 bytes de la mayoría de las filas).
- El HUD manda un grupo de dígitos por cuadro.
## Cómo se mide

- **Error visual:** `playtest.visual_errors` lee el mapa `$9800` y el `SCY` del hardware en el hook de fin de ISR.
- **Bytes de VRAM, ISR, bucle principal, sprites por línea:** contadores de la propia ROM (`wQMax`, `wIsrMax` con `DIV`,
  `wCpuMax` con `LY`, `wFlushLines`) y el OAM en sombra.
- **Qué es solo de emulador:** todo. En DMG real hay que revisar además que no haya basura al escribir VRAM cerca del
  final del VBlank (por eso `wOverrun`), y el balance de la ISR depende del `DIV` del emulador.
