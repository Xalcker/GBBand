# Ideas pendientes

- Fase 5: importador GBS/VGM, borde Super Game Boy, rumble de MBC5, impresión de
  récord con Game Boy Printer. (VS y Co-Op por cable link ya están.)
- Compresión del stream FRS (RLE de cuadros repetidos o LZ pequeño) si no caben las canciones largas.
- Opción de ganancia por canal para calibrar de oído el balance de volumen NES → GB.

## Que se note el acierto

Hoy la gema acertada sigue bajando por la autopista. La **llamarada al acertar** ya está (sprites 15 a 19 sobre los aros,
3 cuadros de animación en 12 cuadros, azul con el poder estelar; ver `FlameStart` en `hud.asm`). Falta:

- **Borrar la gema acertada:** encolar 2 tiles en blanco (o los de la línea del carril) en su fila del mapa, y en la de
  abajo si la gema cae entre dos filas (colocación B). Son 2 a 4 bytes en la cola de VRAM por carril; hay que medir el
  peor cuadro (acorde de 3 notas con la fila nueva y el audio de 4 canales) con `wOverrun`.
