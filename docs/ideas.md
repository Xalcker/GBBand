# Ideas pendientes

- Fase 5: borde Super Game Boy, rumble de MBC5, impresión de récord con Game Boy Printer. (VS y Co-Op por cable link y el
  importador de VGM y GBS ya están.)
- Compresión del stream FRS (RLE de cuadros repetidos o LZ pequeño) si no caben las canciones largas.
- Opción de ganancia por canal para calibrar de oído el balance de volumen NES → GB.

## Que se note el acierto

Ya están la **llamarada al acertar** (sprites 15 a 19 sobre los aros, azul con el poder estelar; `FlameStart` en
`hud.asm`) y el **borrado de la gema acertada** (`GemEraseStart` en `highway.asm`). Falta:

- **Borrar también en la batería:** el bombo es una barra que cruza la fila y las gemas van encima; para borrar una gema
  habría que reescribir la fila entera con lo que quede sin tocar (la barra y las otras gemas), unos 20 bytes más por
  borrado.
