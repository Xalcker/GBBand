# Diseño de GBBand

GBBand es el equivalente para Game Boy Color (con compatibilidad Game Boy original) de
[NESBand](https://github.com/Xalcker/NESBand): un juego de ritmo estilo Guitar Hero / Rock Band. Este documento
resume lo que se hereda, lo que cambia y cómo está pensada la arquitectura. Las decisiones puntuales con su
motivo están en [decisiones.md](decisiones.md) y la tabla de VRAM en [vram.md](vram.md).

## Qué se hereda de NESBand

Reglas y diseño tal cual: 5 carriles (verde ←, rojo ↓, amarillo →, azul B, naranja A); nunca ← y → a la vez ni
amarillo + naranja; fácil 3 carriles, medio 4, difícil y experto 5; ventana de acierto, combo y puntaje;
estrellas por porcentaje del puntaje; vida y "sin fallo"; notas sostenidas; poder estelar con Select; silenciar
el instrumento al fallar; opciones (espejo, velocidad, caída de notas, práctica con marcas); récords; charts de
guitarra, teclado, bajo y batería; formato de chart de 2 bytes por entrada con las marcas `$40` y `$80`;
editor de charts y `check_playable`. **Todo se mide en cuadros.**

## Qué cambia

- Pantalla de 160×144 (20×18 tiles). Autopista de 80 px (5 carriles de 2 tiles) y escenario a los lados.
- **1 jugador por cartucho.** VS y Co-Op por cable link, cada quien en su consola (fase 5).
- Sin DPCM: la batería usa parches del canal de ruido.
- Mapper **MBC5+RAM+BATTERY** (2 MB de ROM, 8 KB de SRAM) en lugar de MMC3; RGBDS en lugar de cc65.
- Sin cambio de banco CHR ni IRQ por scanline estilo MMC3: se usan la Window, `LCDC.4` y los 2 bancos de
  VRAM del GBC.
- **Los charts no son idénticos a los del NES.** Con 104 px de recorrido (la mitad que el NES) la autopista cae
  a la mitad de velocidad: una fila de 8 px dura 12, 10, 8 y 6 cuadros (fácil a experto) y en NESBand eran
  6, 5, 4 y 3. El generador necesita un parámetro `min_lane_gap` por plataforma (separación mínima entre dos
  notas del mismo carril, en píxeles), así que los charts de GB salen un poco más ralos por carril.

## Pantalla (20×18 tiles)

```
columnas 0-4   escenario izquierdo        columnas 15-19  escenario derecho
columnas 5-14  autopista: 5 carriles x 2 tiles (x = 40 a 119)
filas 0-14     fondo con scroll (SCY)     filas 15-17     Window (WY=120, WX=7): HUD
aro de aciertos en la fila 13 (y ~ 104)
```

El fondo usa el mapa `$9800` (32×32): el scroll vertical da la vuelta exacta cada 32 filas. Las filas nuevas se
escriben justo fuera de pantalla, arriba. La Window usa `$9C00` y no se desplaza.

## Ciclo de cuadro

`main_loop` calcula y deja datos en buffers; la ISR de VBlank solo copia, en este orden: audio, OAM DMA,
cola de VRAM, SCY/WY/WX/paletas, lectura del control, `hFrame++`. **La ISR nunca cambia de banco**: el bucle
principal decodifica el stream de audio a un ring buffer en WRAM, con al menos 8 cuadros de adelanto.
Música, charts y ventana de acierto comparten el mismo `hFrame`.

## Mapa de memoria

ROM (2 MB = 128 bancos de 16 KB): banco 0 fijo (vectores, header, arranque, ISR, rutinas de banco, lógica
caliente); bancos 1-15 código no crítico y datos; bancos 16-111 en 32 slots de 3 bancos (ficha y charts, y 2
bancos de stream de audio); bancos 112-127 reservados.

WRAM: solo se usa `C000-DFFF` como un bloque único, **sin SVBK**, para que DMG y CGB tengan el mismo mapa.

| Dirección | Contenido |
|---|---|
| `C000-C3FF` | ring de audio: 16 slots de 64 B (cuenta, marca de wave RAM, wave RAM, hasta 23 pares registro/valor) |
| `C400-C49F` | OAM en sombra (origen del OAM DMA, byte alto `$C4`) |
| `C500-C5FF` | cola de VRAM |
| `C710-C726` | sombra de los registros del APU (dirección = `C700` + byte bajo del registro) |
| `C800-C827` | contadores de altas de nota (mismo índice) |
| `C900` en adelante | variables: autopista, juez, puntaje, estadísticas de las pruebas |
| `DF00-DFFF` | pila |

HRAM: variables rápidas (`hFrame` de 16 bits, `hPad`, `hPadNew`, aviso de VBlank, `hScy`, `hLcdc`...) y la copia de la
rutina de OAM DMA. El mapa exacto está en `src/wram.asm`.

## Cómo funciona la autopista (fase 2)

- **Tiempo.** Todo se mide en cuadros. La ISR de VBlank número `n` (`wT` = n) escribe el audio del cuadro `n - lead_in`,
  pone el `SCY` del cuadro `n` y lee el control; una nota del chart con cuadro `F` está en la línea de golpe en la ISR `F`
  y el audio de su nota se dispara en esa misma ISR (prueba de sincronía).
- **Posición.** Una nota está en el fondo de 256 px en `y = 104 - F * v` (v en px/cuadro, punto fijo 8.8), y `SCY(t) = -t * v`.
  Cada fila de tiles se arma una vez, 24 filas por debajo de la de arriba, cuando el scroll cruza un múltiplo de 8 px.
- **Gemas.** 5 formas distintas (◀ ▼ ▶ anillo rombo) de 16x8 px con 4 variantes de desplazamiento (colocación B).
- **Juez.** Cola de 8 notas pendientes `(cuadro, carriles)`; cada carril se acierta o se pierde por separado.
  Acierto: `|t - F| <= 6`; golpe sin nota cerca rompe el combo; fallar o golpear al aire calla el CH1 hasta el siguiente acierto.
- **Puntaje.** 50 x multiplicador por nota (x1 con 0-9 de combo, x2 con 10-19, x3 con 20-29, x4 desde 30).
- **Audio.** Stream FRS en 2 bancos; el bucle principal decodifica a un ring de 16 cuadros en WRAM y la ISR solo lee de ahí.

## Estado actual

- **Fase 1** (esqueleto): ROM "hola mundo", herramientas y pruebas. Hecha.
- **Fase 2** (rebanada vertical): menú de dificultad, una canción original de ~32 s (`audio/demo.py`), autopista con scroll,
  Window de HUD, 5 carriles, ventana de acierto en cuadros, puntaje, combo, silencio al fallar, ISR con ring de audio y
  cola de VRAM. Medida la colocación A contra B (ver [vram.md](vram.md)). Hecha; ver [decisiones.md](decisiones.md) para lo que queda pendiente.