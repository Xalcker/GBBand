# Decisiones

Decisiones menores que tomé yo, con su motivo. Las de gran tamaño se proponen aquí antes de implementarse.

## Fase 1

1. **RGBDS fijo en v1.0.4.** La sintaxis cambió entre 0.x y 1.0 (por eso se usa `DEF ... EQU`). `tools/` está en
   `.gitignore`: cada máquina baja su RGBDS (Windows: zip en `tools/rgbds/`; macOS: `brew install rgbds`).
2. **WRAM sin SVBK.** Se usa `C000-DFFF` como un solo bloque; DMG y CGB comparten mapa.
3. **ROM de 2 MB forzado con un mensaje en el banco 127.** `rgblink -p` solo rellena hasta el último banco usado y
   `rgbfix -p` hasta una potencia de 2. Poner un dato (el mensaje de prueba del MBC5) en el banco 127 hace que el
   enlazador genere los 128 bancos. Cuando existan las canciones, un archivo `rom_size.asm` hará este trabajo.
4. **Texto: tile = código ASCII.** La fuente (Bongo-8 Mono, CC0) ocupa los tiles `$20`-`$5A` y solo tiene
   mayúsculas, sin acentos. Se dibuja en color 3 (el más oscuro).
5. **Gráficos como texto.** `src/chr/*.tiles` (`.`, `0`-`3` por píxel) se convierte con `gbband build-gfx` a
   `build/chr/*.2bpp` más un PNG de contacto para revisarlos. El 2bpp del GB entrelaza los planos por fila
   (distinto del NES). El PNG se escribe con la biblioteca estándar, sin Pillow.
6. **`hIsCGB` guarda el valor crudo de A al arrancar** (`$11` en CGB, `$01` en la DMG original; otros modelos
   dan otros valores). Solo se compara contra `$11`.
7. **Comando de PC `gbband`** (`uv run gbband ...`), equivalente a `nesband`.
8. **Pruebas con PyBoy como juez principal y Mesen 2 como verificación cruzada.**
   - PyBoy 2.8.1 sin `bootrom=` corre la animación real del logo de la consola, así que los primeros cuadros no
     son del juego. El corredor espera con `Runner.boot()` hasta que `hFrame` cuenta un cuadro.
   - `cgb=False` fuerza DMG aunque el header sea compatible con CGB.
   - Mesen 2 2.1.1 en `--testrunner`: el script de Lua no corre con la carpeta del proyecto como directorio de
     trabajo, así que la salida va a una ruta absoluta (`GBBAND_OUT`). El tipo de memoria es
     `emu.memType.gameboyMemory` (no `gbMemory`). Se necesita `Debug.ScriptWindow.AllowIoOsAccess=true` en
     `tools/mesen/settings.json`. Un script que falla sin llamar a `emu.stop` deja a Mesen colgado.
9. **`-Solo` / `SOLO`** se aceptan pero no hacen nada hasta que exista la lista de canciones (fase 3).

## Fase 2

1. **Colocación B** (4 desplazamientos verticales por gema) por mediciones (ver `docs/vram.md`): error máximo 1.5 px contra
   4.5 px de A. El precio es una separación mínima de 16 px entre dos notas del mismo carril (21 / 18 / 14 / 11 cuadros de
   fácil a experto); el generador de charts la respeta con `min_lane_gap`. `-Colocacion A` (`COLOCACION=A`) deja la A.
2. **Los charts no son los de NESBand tal cual.** Velocidad de caída 120 px en 2.6 / 2.2 / 1.7 / 1.3 s (198, 234, 303 y 396
   en 8.8 px/cuadro); `layout.py` es el modelo en Python de lo que hace la ROM y la prueba `test_velocidades_de_la_rom` las
   mantiene iguales. Las demás reglas (ventana de ±6 cuadros, 50 x multiplicador, multiplicador por combo 10 / 20 / 30,
   estrellas por % de puntaje con umbrales 20 / 40 / 60 / 80 / 95) se copiaron de NESBand.
3. **Reloj de la canción.** `wT` cuenta ISRs de VBlank desde el inicio de la canción y lo incrementa la ISR al final.
   La nota del cuadro `F` está en la línea de golpe cuando la ISR `F` pone el scroll; el audio de ese cuadro y el control
   que lee esa ISR también son los de `F`. `lead_in` es el cuadro en que empieza el audio (200: las notas ya están cayendo).
4. **Autopista.** Cada fila de tiles se arma una vez, 24 filas por debajo de la de arriba (donde no se ve), cuando el scroll
   cruza un múltiplo de 8 px; al empezar se arman 26 con el LCD apagado. `SCY` es el scroll 8.8 redondeado al píxel más
   cercano. La parte de abajo de una gema que cruza dos filas se escribe como parche en la fila ya armada.
5. **Stream FRS.** En el stream, la wave RAM va justo después del encabezado y antes de los canales. NR50/NR51 no se
   decodifican a la ISR (el juego los maneja); un registro con esos bits solo se descarta. El ring buffer tiene 16 slots de
   64 bytes (cuenta, marca de wave RAM, 16 bytes de wave RAM, hasta 23 pares) y el bucle principal mantiene ≥ 14 cuadros
   decodificados por delante. La ISR escribe `NR51` cada cuadro: es del juego, no de la música (así se calla el instrumento).
6. **Silencio al fallar:** `NR51 = $EE` (CH1 fuera de ambos lados); al acertar vuelve a `$FF`. El instrumento de la fase 2
   es el CH1 (la melodía); los demás canales nunca se callan.
7. **Keyframes.** El generador ya los escribe (la ficha tiene 4 entradas: cuadro, banco y puntero del stream, registro),
   pero la ROM todavía no los usa: llegan con la práctica de la fase 4. Un keyframe reinicia la nota vigente de cada canal.
8. **Pruebas.** PyBoy: los hooks (`hook_register`) corren en el hilo del emulador y ven un cuadro completo si se
   enganchan al final de la ISR (`IsrEnd`); el tick de PyBoy puede terminar a la mitad de la ISR. Dentro de un hook
   `button_press` no sirve (PyBoy vacía la lista de eventos al final del tick): se usa `send_input(evento, 1)`, que
   lee la ISR del cuadro `wT`. Cada caso deja `build/test-demo-<bot>-<dificultad>-<modo>/resultado.txt` y capturas.
9. **Memoria.** WRAM: ring de audio `C000`, OAM `C400`, cola de VRAM `C500`, sombra del APU `C700` (dirección = `C700` + byte
   bajo del registro), contadores de altas de nota `C800`, variables desde `C900`. HRAM: variables y rutina de OAM DMA.
10. **Cola de VRAM.** Entradas `[cuenta | $80 = banco 1][dir lo][dir hi][datos]`, terminadas en 0; si se llena, los datos
    van a un buffer inofensivo y se cuenta (`wQOverflow`). Las pruebas exigen 0 desbordes.
11. **HUD de 2 filas.** La Window mide 2 filas (`WY=128`); aciertos y fallos salen solo al terminar la canción
    (`FIN DE LA CANCION`, `ACIERTOS`, `FALLOS`, escritos en filas de pantalla sobre la autopista). El HUD manda un grupo de
    dígitos por cuadro. La fase 4 los moverá a la pantalla de resultados.
12. **Pendiente de la fase 2 que no se hizo:** pausa y "después de pausar" de la prueba de sincronía (llegan con la pausa
    de la fase 4); bots "humano" (90 % / 45 %), opciones (espejo, velocidad, práctica) y charts de los otros instrumentos.

## Fase 3

1. **El NSF se importa sin FamiStudio** (la spec decía "vía FamiStudio, como NESBand"). El NSF se ejecuta en un 6502 propio
   (`cpu6502.py`, solo opcodes oficiales) y se registra el APU (`nsf.py`); las notas de los charts se derivan del estado por
   cuadro. Motivos: sin .NET ni descargas, funciona igual en Windows y macOS, y se prueba con NSF sintéticos escritos a mano
   (los reales tienen copyright). **No se probó con ningún NSF comercial real**: el 6502 y el APU están probados contra
   programas pequeños y contra el hardware documentado, nada más. Un NSF con el tempo mal estimado se corrige con `--beat-frames`.
   La importación de un proyecto de FamiStudio con envolventes de tono, arpegio o vibrato las ignora y lo avisa en el log.
2. **La fuente de las canciones originales es el proyecto de texto de FamiStudio** (`audio/*.txt`, que generan `audio/*.py`
   con `compose.py`, copiados de NESBand) y se lee con `famitext.py`.
3. **Batería.** Los charts y el sonido salen de la misma asignación de papeles (`drums.json`, la de NESBand para las
   originales; para una canción nueva, la sugerida automáticamente). El sonido de cada golpe es un parche del canal de
   ruido (CH4) por papel: bombo (cae de tono en 4 cuadros), tarola, hi-hat cerrado y abierto, platillo y 3 toms. Dos golpes en
   el mismo cuadro: se queda el de más prioridad (bombo > tarola > platillo > tom > hi-hat) y se avisa. **Los timbres de
   la batería, los volúmenes y la ganancia de cada canal están elegidos a ojo y se calibran de oído.** No existe DPCM: los
   samples se sustituyen por esos parches.
4. **El audio se parte en tramos solo si hace falta.** Un pulso nunca cambia de volumen sin reiniciarse: cada nota se ajusta a
   volumen constante, envolvente por hardware (caída monótona) o dos tramos con un reinicio. Las diez originales dan un error
   medio de 0.07 a 0.94 pasos de volumen (máximo 2.6 en *Salto Mortal*); el log dice cuántas notas pasan de 1.5 pasos.
5. **Ficha de la canción.** Título de 20 caracteres, juego de 16 (la spec decía 16 para ambos: "Marcha del Cartucho" y "Noche sin
   Estrellas" miden 19) y el cuadro del primer tiempo para el escenario de la fase 4 (`src/song_format.inc`).
6. **Lead-in de 180 cuadros** (más que la anticipación de fácil, 156): la primera nota ya está cayendo cuando empieza el audio.
7. **Lista de canciones.** `build/list.asm` (en `build/`, no en git) se regenera en cada compilación: alfabético, el lugar de
   cada canción es su slot y su banco es 16 + 3 x slot. `-Release` incluye solo las canciones versionadas en git; `-Solo` filtra.
8. **ISR reordenada (sale de lo que dice la spec):** OAM, cola de VRAM, scroll y LCDC, y **después** el audio (la spec pedía
   el audio primero, "para que su jitter sea constante"). Motivo, medido: con los cuatro canales sonando a la vez el audio tarda
   hasta ~400 M y empujaba la cola de VRAM fuera del VBlank en las canciones más cargadas (`wOverrun`), cosa que en una DMG real
   pierde escrituras. El audio no tiene fecha límite y su corrimiento (unas decenas de microsegundos) es inaudible.
9. **Menos trabajo en la ISR.** El OAM DMA completo (160 M) solo se hace al armar la pantalla; después solo se copian los 5
   tiles de los aros. Una fila vacía del fondo no se escribe si la vuelta anterior no dejó gemas en esa fila (`wRowFlags`).
10. **Las colas ($40 y $80) y las frases estelares ($20) ya vienen en los charts**, pero la ROM todavía las ignora (una cola es
    una nota normal y el fin de cola se salta): se dibujan y se juegan en la fase 4. `enforce_lane_gap` mira solo las gemas;
    habrá que reimportar cuando las colas ocupen tiles.
11. **Pruebas.** `GBBAND_COMPLETA=1` corre las diez canciones (243 pruebas, unos 140 s); sin ella, tres (unas 90). El bot de
    cada caso elige canción, instrumento y dificultad con el menú, como un jugador, y comprueba el título mostrado.
12. **El editor** reutiliza la página de NESBand: sus canales siguen siendo Square 1/2, Triángulo, Ruido y DPCM (la IR), pero
    "Escuchar" toca el stream de la ROM (4 canales; Ruido y DPCM comparten el CH4). `Exportar a la ROM` reimporta la canción.
13. **Pendiente de la fase 3:** `preview` (WAV de cada pista de un NSF sin .m3u: de momento se importa con `--song N` y se
    escucha en el editor), importador GBS/VGM (fase 5), keyframes y práctica (fase 4), y la prueba de sincronía después de pausar.
14. **Efecto al fallar (de NESBand v0.3.2, pendiente en la fase 4).** Al fallar (nota que se pasó o golpe al aire) suena uno de
    tres efectos (clank, thud, bwomp) sin repetir el anterior, en un canal de pulso que no sea el del instrumento que falla
    (ese canal se calla al fallar). La autopista tiembla (SCX de 1-2 px) y la paleta se tiñe de rojo 6 cuadros, con 14 de
    enfriamiento (a lo más 3 por segundo). Opción EFECTO AL FALLAR (SI / SOLO SONIDO / NO) en la pantalla de opciones; no
    cuenta como opción que bloquee récords. Los efectos viven en `audio/efectos.txt`. Además, de la misma versión: el
    marcador (puntaje y combo) ocupa todo el ancho de la autopista y el público de la franja no deja huecos junto a ella.
