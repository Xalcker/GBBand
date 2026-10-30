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
- **Los charts no son idénticos a los del NES.** Con 120 px de recorrido (la mitad que el NES) la autopista cae
  a la mitad de velocidad: una fila de 8 px dura 12, 10, 8 y 6 cuadros (fácil a experto) y en NESBand eran
  6, 5, 4 y 3. El generador necesita un parámetro `min_lane_gap` por plataforma (separación mínima entre dos
  notas del mismo carril, en píxeles), así que los charts de GB salen un poco más ralos por carril.

## Pantalla (20×18 tiles)

```
columnas 0-4   escenario izquierdo        columnas 15-19  escenario derecho
columnas 5-14  autopista: 5 carriles x 2 tiles (x = 40 a 119)
filas 0-15     fondo con scroll (SCY)     filas 16-17     Window (WY=128, WX=7): puntaje, multiplicador y combo
aro de aciertos en la fila 15 (y = 120), pegado a la Window como en NESBand
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
- **Posición.** Una nota está en el fondo de 256 px en `y = 120 - F * v` (v en px/cuadro, punto fijo 8.8), y `SCY(t) = -t * v`.
  Cada fila de tiles se arma una vez, 24 filas por debajo de la de arriba, cuando el scroll cruza un múltiplo de 8 px.
- **Gemas.** 5 formas distintas (◀ ▼ ▶ anillo rombo) de 16x8 px con 4 variantes de desplazamiento (colocación B).
- **Juez.** Cola de 8 notas pendientes `(cuadro, carriles)`; cada carril se acierta o se pierde por separado.
  Acierto: `|t - F| <= 6`; golpe sin nota cerca rompe el combo; fallar o golpear al aire calla el CH1 hasta el siguiente acierto.
- **Puntaje.** 50 x multiplicador por nota (x1 con 0-9 de combo, x2 con 10-19, x3 con 20-29, x4 desde 30).
- **Audio.** Stream FRS en 2 bancos; el bucle principal decodifica a un ring de 16 cuadros en WRAM y la ISR solo lee de ahí.

## Pipeline de canciones (fase 3)

```
fuente                          IR (ir.py)                       salidas (src/songs/<nombre>/)
proyecto de FamiStudio (.txt) --> famitext.py -+
                                               +--> SongIR --+--> chart.py + drums.py + chartedit.py --> chart_<instr>_<dif>.bin
NSF --> cpu6502.py + nsf.py (APU) -------------+             +--> gbaudio.py --> audio_gb.py --> stream_b/c.bin + keyframes.bin
```

- **IR.** `SongIR` = las notas de los 5 canales (para los charts, con la misma forma que en NESBand) y, por cuadro y por
  canal tonal, frecuencia en Hz, volumen 0-15, duty y si arrancó una nota (para el audio). No sabe nada de la Game Boy.
- **Fuentes.** Un proyecto de texto de FamiStudio trae las notas exactas; se lee sin FamiStudio (envolventes de volumen
  y duty). Un NSF se ejecuta en un 6502 (`cpu6502.py`), se emula el APU (envolventes, longitudes, contador lineal, barrido) y
  se registra el estado de cada cuadro; las notas se derivan de él.
- **Charts.** El generador de NESBand (contorno, tiempos fuertes, acordes, colas, frases estelares, batería por papeles),
  más `enforce_lane_gap`: dos gemas del mismo carril necesitan 21 / 18 / 14 / 11 cuadros (fácil a experto) para no compartir
  tiles (ver vram.md). Un chart son pares de 2 bytes (cuadros desde la entrada anterior, carriles y marcas).
- **Audio.** `gbaudio.py`: Pulso 1/2 -> CH1/CH2, Triángulo -> CH3 con el triángulo de 32 pasos en la wave RAM, Ruido y DPCM
  -> CH4 con parches por papel (bombo, tarola, hi-hat, platillo, toms). Volumen: constante, envolvente por hardware o dos
  tramos con un reinicio de la nota; el error medio y máximo se reporta. Las notas fuera de rango suben de octava (se avisa).
  Tempo: 1 cuadro NES = 1 cuadro GB (0.6 % más lento).
- **Slot de canción.** 3 bancos: A = ficha (112 bytes) + 16 charts + 4 keyframes; B y C = stream FRS (hasta 32 KB). Las diez
  canciones originales usan de 6 a 13 KB de stream y de 6 a 11 KB en el banco A.
- **ROM.** `gbband list-songs` escribe `build/list.asm` (banco de cada canción y la tabla `SongTable`); el menú lee de la ficha
  el título, el juego y los instrumentos disponibles. El instrumento elegido decide qué chart se juega y qué canal del APU se
  calla al fallar (CH1 guitarra, CH2 teclado, CH3 bajo, CH4 batería).

## 2 jugadores por cable link (fase 5, en curso)

A diferencia de NESBand (pantalla dividida en una consola), aquí **cada jugador tiene su consola, su cartucho y su pantalla
completa**: cada Game Boy corre su propia partida con su autopista, y el cable solo lleva lo necesario para sincronizar y
compartir el marcador. No hace falta dividir la pantalla ni encoger los carriles.

**Conexión (hecha).** En el título, el renglón JUGADORES (`1 JUGADOR`, `2 JUG. VS`, `2 JUG. COOP`, con ←/→; el menú ya no
tiene lugar para otro renglón). Con 2, Start abre la pantalla de conexión (`link.asm`), que busca al otro hasta que B la
cancela. Cada byte del cable es parte de un mensaje: el tipo lleva el bit 7 en 1 y los datos (7 bits) en 0; `$00` es "nada
que mandar" y `$FF` lo que se lee sin nadie del otro lado, y los dos se ignoran entre mensajes. Para repartir papeles,
cada consola espera como esclavo (reloj externo) un rato al azar y, si nadie la llamó, llama como maestro (reloj interno);
mientras busca repite su saludo (`MSG_HELLO`: versión del protocolo y hash de 14 bits de la lista de canciones, que
`list-songs` deja en `SONG_LIST_HASH`). Quien recibe el saludo completo del otro queda conectado con el papel que tenía:
el maestro es el **jugador 1**. Si el saludo no coincide, sale `CANCIONES DISTINTAS`. El maestro manda un byte por cuadro
desde el bucle principal y el esclavo arma el siguiente en la ISR serie en cuanto llega uno.

**Menú.** El maestro elige canción (y en VS la dificultad, como en NESBand); cada quien elige su instrumento y dificultad en
su propia consola. En Co-Op no pueden tocar el mismo instrumento; en VS el jugador 2 copia al 1 por defecto. Start en el
maestro arranca cuando los dos están listos.

**Arranque sincronizado.** El maestro manda `EMPIEZA` y las dos consolas empiezan la canción en el VBlank siguiente al fin
de la transferencia. Los dos cristales difieren en unas ppm: en una canción de 4 minutos es menos de un cuadro. Cada cuadro
viaja también el número de cuadro para detectar desfase (si pasa de 2 cuadros, el esclavo repite o salta uno).

**Un paquete por cuadro.** El maestro inicia el intercambio en el bucle principal (no en la ISR de VBlank, que ya va justa;
ver `wOverrun`); la interrupción serie (vector `$0058`, hoy un `reti`) solo guarda el byte recibido y manda el siguiente.
A 8 KHz cada byte tarda ~1 ms, así que 4 a 6 bytes por cuadro cuestan menos del 10 % del cuadro y casi nada de CPU.

- **VS:** cada consola manda su puntaje (3 bytes BCD) y banderas (vida baja, perdió, poder estelar activo, instrumento
  callado). La pantalla muestra el puntaje del rival en la Window. Al final: `GANA J1 POR 001230`, `EMPATE` o, con fallo,
  `GANA J2 - J1 PERDIO` (la partida se corta). Cada quien guarda su récord en su cartucho.
- **Co-Op (banda):** el **maestro es la autoridad** del marcador de banda. El esclavo manda sus eventos del cuadro
  (aciertos, fallos, frase estelar, pedir poder o revivir) y el maestro devuelve el estado de banda (puntaje, combo,
  multiplicador, barra estelar). Así los dos ven lo mismo aunque el esclavo lo vea 1 cuadro tarde. La vida es de cada
  quien; con media barra estelar, Select revive al caído. Récord de banda aparte, como en NESBand.
- **Audio:** las dos consolas tocan la canción completa; cada una calla el canal del instrumento de quien esté fallando
  (el suyo o el del compañero, que llega en las banderas).

**Pruebas.** El cable de PyBoy no sirve para esto (su modo de memoria compartida necesita dos hilos que se esperan en
cada byte, y el puerto normal siempre lee `$FF`), así que `linkbridge.py` corre dos PyBoy a la par, un cuadro cada uno, y
pasa los bytes con hooks en `SerialSend`, `SerialArm`, `SerialOff` y `SerialGot`. El esclavo recibe hasta un cuadro tarde;
el protocolo no depende de eso. `tests/test_link.py` prueba la conexión con distintos tiempos de entrada, dos CGB que entran
en el mismo cuadro, cartuchos con canciones distintas y una consola sola. Falta probarlo a mano en SameBoy o BGB con dos
ventanas y con dos consolas de verdad (hasta entonces, **probado solo en emulador**).

**Orden:**

1. ~~Controlador serie, saludo y puente de dos PyBoy en las pruebas (pantalla de conexión).~~ Hecho.
2. Del saludo al menú, elección de canción por el maestro y arranque sincronizado.
3. VS completo (puntaje del rival, resultados, corte al perder).
4. Co-Op completo (marcador de banda, revivir, récord de banda).
5. Documentación y prueba a mano en emulador con dos ventanas.

## Estado actual

- **Fase 1** (esqueleto): ROM "hola mundo", herramientas y pruebas. Hecha.
- **Fase 2** (rebanada vertical): autopista, juez, puntaje y combo, stream FRS, ISR con ring de audio. Hecha.
- **Fase 3** (pipeline de canciones): IR, importador (FamiStudio y NSF), conversor al stream FRS, charts de 4 instrumentos, las
  diez canciones originales, editor de charts con "Escuchar". Hecha; ver [decisiones.md](decisiones.md) para lo que queda pendiente.
- **Fase 4** (el juego completo): título con música, menú, opciones (espejo, velocidad, caída, práctica con marcas, efecto al
  fallar), pausa, resultados con estrellas, récords en SRAM, vida y "sin fallo", notas sostenidas, poder estelar, medidores,
  bombo como barra, escenario con torres, reflectores y público al ritmo, color CGB. Hecha; ver decisiones.md (fase 4).
  Lo que sigue en la fase 5: importador GBS/VGM, link cable (2 jugadores) y el pulido de la release.