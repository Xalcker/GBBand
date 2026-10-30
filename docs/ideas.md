# Ideas pendientes

- Fase 5: importador GBS/VGM, borde Super Game Boy, rumble de MBC5, impresión de
  récord con Game Boy Printer. (VS y Co-Op por cable link ya están.)
- Compresión del stream FRS (RLE de cuadros repetidos o LZ pequeño) si no caben las canciones largas.
- Opción de ganancia por canal para calibrar de oído el balance de volumen NES → GB.

## Que se note el acierto

Hoy es difícil saber si acertaste: la gema acertada sigue bajando por la autopista y el aro solo cambia mientras el botón
está apretado. No hay límite técnico que lo impida; son dos piezas:

- **Llamarada al acertar** (como NESBand): un sprite de 8x16 con 2 o 3 cuadros de animación sobre el aro del carril
  durante ~8 cuadros, azul con el poder estelar. Los aros ya ocupan 5 sprites en la línea de golpe y el límite es 10 por
  línea, así que caben 5 llamaradas encima de los aros (o se cambia el tile del aro mientras dura). El OAM ya se copia
  completo en la ISR cuando cambia algo (`wOamDirty`), así que no agrega escrituras a la VRAM.
- **Borrar la gema acertada:** encolar 2 tiles en blanco (o los de la línea del carril) en su fila del mapa, y en la de
  abajo si la gema cae entre dos filas (colocación B). Son 2 a 4 bytes en la cola de VRAM por carril; hay que medir el
  peor cuadro (acorde de 3 notas con la fila nueva y el audio de 4 canales) con `wOverrun`.
